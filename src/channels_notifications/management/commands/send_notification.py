"""``send_notification`` — dispatch any of the 18 send / redirect / progress
functions in :mod:`channels_notifications.api` from the command line.

Three orthogonal axes:

  --kind={message,redirect,progress}   what to send
  --audience={all,authenticated,anonymous,user,object,channel}   who gets it
  the text / URL / percent payload itself (positional)

Examples
--------

Messages::

    ./manage.py send_notification --audience=all "Maintenance in 5 min" --level=warning
    ./manage.py send_notification --audience=authenticated "New report ready"
    ./manage.py send_notification --audience=anonymous "Welcome!"
    ./manage.py send_notification --audience=user --username=alice "Your import finished"
    ./manage.py send_notification --audience=object --object="app.Model:42" "Comment posted"
    ./manage.py send_notification --audience=channel --channel="stream-abc123" "Hi UID"

Redirects (--kind=redirect, payload = URL)::

    ./manage.py send_notification --kind=redirect --audience=user --username=alice /reports/42/
    ./manage.py send_notification --kind=redirect --audience=channel --channel="stream-abc" /done/

Progress (--kind=progress, payload = percent: int, float, or "42%")::

    ./manage.py send_notification --kind=progress --audience=user --username=alice 42
    ./manage.py send_notification --kind=progress --audience=channel --channel="stream-abc" 75%

The --object format is "<app_label>.<ModelName>:<pk>". Resolved via
``django.apps.apps.get_model``.
"""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.messages import constants as message_constants
from django.core.management import BaseCommand, CommandError

from channels_notifications import api

LEVEL_MAP = {
    "info": message_constants.INFO,
    "success": message_constants.SUCCESS,
    "warning": message_constants.WARNING,
    "error": message_constants.ERROR,
}


def _resolve_object(spec):
    """Parse 'app_label.ModelName:pk' → model instance, or raise CommandError."""
    if ":" not in spec:
        raise CommandError(
            f"--object must look like 'app_label.ModelName:pk' (got {spec!r})"
        )
    label, pk = spec.split(":", 1)
    if "." not in label:
        raise CommandError(
            f"--object must look like 'app_label.ModelName:pk' (got {spec!r})"
        )
    app_label, model_name = label.split(".", 1)
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError as exc:
        raise CommandError(f"unknown model {label!r}: {exc}") from exc
    try:
        return model.objects.get(pk=pk)
    except model.DoesNotExist as exc:
        raise CommandError(f"{label} with pk={pk!r} does not exist") from exc


def _resolve_user(username):
    if not username:
        raise CommandError("--username is required when --audience=user")
    UserModel = get_user_model()
    try:
        return UserModel.objects.get(**{UserModel.USERNAME_FIELD: username})
    except UserModel.DoesNotExist as exc:
        raise CommandError(f"user {username!r} does not exist") from exc


class Command(BaseCommand):
    help = "Send a realtime message, redirect, or progress update via django-channels."

    def add_arguments(self, parser):
        parser.add_argument(
            "--kind",
            choices=["message", "redirect", "progress"],
            default="message",
            help=(
                "Payload family. message=text (default), redirect=URL "
                "to navigate the receiving page to, progress=percent "
                "to update a progress bar."
            ),
        )
        parser.add_argument(
            "--audience",
            choices=["all", "authenticated", "anonymous", "user", "object", "channel"],
            required=True,
            help=(
                "Who receives the message. all/authenticated/anonymous "
                "broadcast to groups. user targets one user (--username). "
                "object targets the channel for a Django model row "
                "(--object). channel targets a raw channel name (--channel)."
            ),
        )
        parser.add_argument(
            "--username",
            help="Required when --audience=user.",
        )
        parser.add_argument(
            "--object",
            dest="object_spec",
            metavar="app.Model:pk",
            help="Required when --audience=object. Format 'app_label.ModelName:pk'.",
        )
        parser.add_argument(
            "--channel",
            help="Required when --audience=channel. Raw channel name (a UID, etc.).",
        )
        parser.add_argument(
            "--level",
            choices=list(LEVEL_MAP),
            default="info",
            help="Message level (--kind=message only).",
        )
        parser.add_argument(
            "payload",
            help=(
                "Message text (--kind=message), URL (--kind=redirect), "
                "or percent (--kind=progress)."
            ),
        )

    # ---------------------------------------------------------- handlers

    def handle(self, *args, **options):
        kind = options["kind"]
        audience = options["audience"]
        payload = options["payload"]
        level = LEVEL_MAP[options["level"]]

        if audience == "object" and not options.get("object_spec"):
            raise CommandError("--object is required when --audience=object")
        if audience == "channel" and not options.get("channel"):
            raise CommandError("--channel is required when --audience=channel")

        # Some combinations don't make sense — bail loudly.
        if kind in {"redirect", "progress"} and audience in {
            "all",
            "authenticated",
            "anonymous",
        }:
            raise CommandError(
                f"--kind={kind} is not supported for --audience={audience}; "
                "redirects and progress updates target a specific recipient "
                "(user/object/channel)."
            )

        # Build a dispatch table keyed by (kind, audience) → (callable, target).
        dispatchers = self._build_dispatchers(audience, options)
        try:
            fn, target = dispatchers[kind]
        except KeyError as exc:
            # Should be unreachable thanks to argparse choices.
            raise CommandError(f"unknown kind {kind!r}") from exc

        result = self._invoke(fn, target, payload, kind, level)
        if result is None:
            # The corresponding ENABLE_* flag was False — be honest about it.
            self.stdout.write(
                self.style.WARNING(
                    f"No-op: the relevant CHANNELS_NOTIFICATIONS_ENABLE_* "
                    f"flag is False for --audience={audience}, "
                    f"--kind={kind}."
                )
            )

    def _build_dispatchers(self, audience, options):
        """Return {kind: (api_fn, target_or_None)} for the chosen audience."""
        target = None
        if audience == "user":
            target = _resolve_user(options.get("username"))
        elif audience == "object":
            target = _resolve_object(options["object_spec"])
        elif audience == "channel":
            target = options["channel"]

        # audience → (message_fn, redirect_fn, progress_fn)
        table = {
            "all": (api.send_to_all, None, None),
            "authenticated": (api.send_to_authenticated, None, None),
            "anonymous": (api.send_to_anonymous, None, None),
            "user": (api.send_to_user, api.redirect_user, api.progress_user),
            "object": (api.send_to_object, api.redirect_object, api.progress_object),
            "channel": (
                api.send_to_channel,
                api.redirect_channel,
                api.progress_channel,
            ),
        }
        msg_fn, redir_fn, prog_fn = table[audience]
        return {
            "message": (msg_fn, target),
            "redirect": (redir_fn, target),
            "progress": (prog_fn, target),
        }

    def _invoke(self, fn, target, payload, kind, level):
        if fn is None:
            # Caught above as well, but defend in depth.
            raise CommandError("invalid combination of --kind and --audience")

        if kind == "message":
            if target is None:
                return fn(payload, level=level)
            return fn(target, payload, level=level)
        if kind == "redirect":
            return fn(target, payload)
        if kind == "progress":
            return fn(target, payload)
