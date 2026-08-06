"""``send_notification`` — dispatch any of the 18 send / redirect / progress
functions in :mod:`channels_broadcast.api` from the command line.

Three orthogonal axes:

  --kind={message,redirect,progress}   what to send
  --audience={all,authenticated,anonymous,user,object,channel}   who gets it
  the text / URL / percent payload itself (positional)

If a required field is missing AND stdin is a TTY, the command prompts
interactively. Run with no arguments at all to see the full wizard.

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

Interactive::

    ./manage.py send_notification
    Audience:
      1) all
      2) authenticated
      ...
    Choose [1-6]: 4
    Username: alice
    Level:
      1) info (default)
      ...
    Message text: Your import finished
"""

import sys

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.messages import constants as message_constants
from django.core.management import BaseCommand, CommandError

from channels_broadcast import api

LEVEL_MAP = {
    "info": message_constants.INFO,
    "success": message_constants.SUCCESS,
    "warning": message_constants.WARNING,
    "error": message_constants.ERROR,
}

AUDIENCE_CHOICES = ["all", "authenticated", "anonymous", "user", "object", "channel"]
KIND_CHOICES = ["message", "redirect", "progress"]

PAYLOAD_LABELS = {
    "message": "Message text",
    "redirect": "Redirect URL",
    "progress": 'Progress percent (e.g. "42" or "42%")',
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


# ----------------------------------------------------------- interactive helpers


def _is_tty() -> bool:
    """Return True if we can prompt interactively."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _require_tty(field_name: str):
    """Raise a helpful CommandError when interactive prompting isn't possible."""
    raise CommandError(
        f"{field_name} is required (pass it as a flag, or run interactively "
        "from a TTY to get a prompt)."
    )


def _input(prompt: str) -> str:
    """Indirection over input() so tests can monkeypatch one place."""
    return input(prompt)


def _prompt_choice(label: str, choices: list[str], default: str | None = None) -> str:
    """Numbered-menu prompt. Returns one of ``choices``.

    Empty input picks ``default`` if provided; otherwise re-asks. ``q`` or
    EOF cancels the whole command.
    """
    while True:
        print(f"{label}:", file=sys.stderr)
        for i, c in enumerate(choices, 1):
            tail = " (default)" if c == default else ""
            print(f"  {i}) {c}{tail}", file=sys.stderr)
        try:
            raw = _input(
                f"Choose [1-{len(choices)}{', enter=' + default if default else ''}]: "
            ).strip()
        except EOFError as exc:
            raise CommandError("cancelled (EOF on stdin)") from exc

        if not raw and default is not None:
            return default
        if raw.lower() in {"q", "quit", "exit"}:
            raise CommandError("cancelled by user")
        # Accept either the number or the name itself.
        if raw in choices:
            return raw
        try:
            idx = int(raw)
        except ValueError:
            print(f"  ! {raw!r} is not a valid choice — try again.", file=sys.stderr)
            continue
        if 1 <= idx <= len(choices):
            return choices[idx - 1]
        print(f"  ! out of range — try 1-{len(choices)}.", file=sys.stderr)


def _prompt_string(label: str, *, allow_empty: bool = False) -> str:
    try:
        value = _input(f"{label}: ")
    except EOFError as exc:
        raise CommandError("cancelled (EOF on stdin)") from exc
    if not allow_empty and not value.strip():
        raise CommandError(f"{label} cannot be empty")
    return value


# --------------------------------------------------------------- command


class Command(BaseCommand):
    help = "Send a realtime message, redirect, or progress update via django-channels."

    def add_arguments(self, parser):
        parser.add_argument(
            "--kind",
            choices=KIND_CHOICES,
            default=None,
            help=(
                "Payload family. message=text (default), redirect=URL "
                "to navigate the receiving page to, progress=percent "
                "to update a progress bar. If omitted, prompted "
                "interactively when stdin is a TTY (defaults to message)."
            ),
        )
        parser.add_argument(
            "--audience",
            choices=AUDIENCE_CHOICES,
            default=None,
            help=(
                "Who receives the message. all/authenticated/anonymous "
                "broadcast to groups. user targets one user (--username). "
                "object targets the channel for a Django model row "
                "(--object). channel targets a raw channel name (--channel). "
                "If omitted, prompted interactively when stdin is a TTY."
            ),
        )
        parser.add_argument("--username", help="Required when --audience=user.")
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
            default=None,
            help="Message level (--kind=message only). Default: info.",
        )
        parser.add_argument(
            "payload",
            nargs="?",
            default=None,
            help=(
                "Message text (--kind=message), URL (--kind=redirect), "
                "or percent (--kind=progress). If omitted, prompted "
                "interactively when stdin is a TTY."
            ),
        )

    # ---------------------------------------------------------- handlers

    def handle(self, *args, **options):
        kind = self._resolve_kind(options)
        audience = self._resolve_audience(options)

        # Validate combinations before prompting for any more details —
        # the user shouldn't have to type a URL only to then learn that
        # redirect-to-all isn't supported.
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

        target = self._resolve_target(audience, options)
        level = self._resolve_level(options, kind)
        payload = self._resolve_payload(options, kind)

        fn = self._dispatch_fn(audience, kind)
        # The api.* functions return a truthy sentinel once the payload has
        # been handed to the channel layer, and None when the relevant
        # ENABLE_* flag turned the call into a no-op. Do not try to infer
        # this from the channel layer itself: group_send()/send() return
        # None *on success*, so a None from down there means nothing.
        if self._invoke(fn, target, payload, kind, level):
            self.stdout.write(
                self.style.SUCCESS(f"Sent: --audience={audience}, --kind={kind}.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"No-op: the relevant CHANNELS_BROADCAST_ENABLE_* "
                    f"flag is False for --audience={audience}, "
                    f"--kind={kind}."
                )
            )

    # --------------------------------------------------- argument resolution

    def _resolve_kind(self, options):
        kind = options.get("kind")
        if kind:
            return kind
        if not _is_tty():
            return "message"  # default; never prompts cron
        return _prompt_choice("Kind", KIND_CHOICES, default="message")

    def _resolve_audience(self, options):
        audience = options.get("audience")
        if audience:
            return audience
        if not _is_tty():
            _require_tty("--audience")
        return _prompt_choice("Audience", AUDIENCE_CHOICES)

    def _resolve_target(self, audience, options):
        if audience == "user":
            username = options.get("username")
            if not username and _is_tty():
                username = _prompt_string("Username")
            return _resolve_user(username)
        if audience == "object":
            spec = options.get("object_spec")
            if not spec and _is_tty():
                spec = _prompt_string("Object (app.Model:pk)")
            if not spec:
                raise CommandError("--object is required when --audience=object")
            return _resolve_object(spec)
        if audience == "channel":
            channel = options.get("channel")
            if not channel and _is_tty():
                channel = _prompt_string("Channel name")
            if not channel:
                raise CommandError("--channel is required when --audience=channel")
            return channel
        return None  # all / authenticated / anonymous have no target

    def _resolve_level(self, options, kind):
        if kind != "message":
            # level only meaningful for messages; ignore if supplied
            return LEVEL_MAP["info"]
        level = options.get("level")
        if not level:
            if _is_tty():
                level = _prompt_choice("Level", list(LEVEL_MAP), default="info")
            else:
                level = "info"
        return LEVEL_MAP[level]

    def _resolve_payload(self, options, kind):
        payload = options.get("payload")
        if payload is not None:
            return payload
        if not _is_tty():
            _require_tty("payload")
        return _prompt_string(PAYLOAD_LABELS[kind])

    # ---------------------------------------------------------- dispatch

    def _dispatch_fn(self, audience, kind):
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
        fn = {"message": msg_fn, "redirect": redir_fn, "progress": prog_fn}[kind]
        if fn is None:
            # Should be unreachable: combination rejected earlier in handle().
            raise CommandError("invalid combination of --kind and --audience")
        return fn

    def _invoke(self, fn, target, payload, kind, level):
        if kind == "message":
            if target is None:
                return fn(payload, level=level)
            return fn(target, payload, level=level)
        if kind == "redirect":
            return fn(target, payload)
        if kind == "progress":
            return fn(target, payload)
