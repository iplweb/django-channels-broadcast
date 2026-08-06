"""Low-level transport layer for channels_broadcast.

Higher-level callers should use :mod:`channels_broadcast.api` instead —
this module is the bridge to ``channels.layers`` and handles event-loop
quirks when called from sync contexts (Celery, management commands, etc.).
"""

from collections import namedtuple
from hashlib import md5

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.messages import DEFAULT_TAGS

Message = namedtuple(
    "Message", "text cssClass clickURL hideCloseOption closeURL closeText"
)
Message.__new__.__defaults__ = ("info", None, False, None, "&times;")


def get_channel_name_for_user(user) -> str:
    """Return a stable per-user channel name (hashed username+pk)."""
    return md5(
        str(user.pk).encode("utf-8") + str(user.username).encode("utf-8")
    ).hexdigest()


def convert_obj_to_channel_name(original) -> str:
    """Compute the channel name for a specific page subscribed to ``original``."""
    from django.contrib.contenttypes.models import ContentType

    ctype = ContentType.objects.get_for_model(original)
    return f"{ctype.app_label}.{ctype.model}-{original.pk}"


def get_obj_from_channel_name(name: str):
    """Inverse of :func:`convert_obj_to_channel_name`."""
    from django.contrib.contenttypes.models import ContentType

    app_label_model, pk = name.split("-", 1)
    app_label, model = app_label_model.split(".", 1)
    ctype = ContentType.objects.get(app_label=app_label, model=model)
    return ctype.get_object_for_this_type(pk=int(pk))


def force_sync(async_func, *args, **kwargs):
    """Run an async function from any context, handling nested event loops."""
    import asyncio

    try:
        asyncio.get_running_loop()
        import nest_asyncio

        nest_asyncio.apply()
        return asyncio.run(async_func(*args, **kwargs))
    except RuntimeError:
        return asyncio.run(async_func(*args, **kwargs))


def _send(channel_name: str, data: dict):
    """Send ``data`` to ``channel_name``.

    Channel names starting with ``"specific"`` are dispatched via
    ``channel_layer.send`` (individual channel); everything else goes
    through ``group_send``.

    The return value is whatever the channel layer returns — which is
    ``None`` on success for every stock backend. Do **not** read it as a
    delivery signal; :func:`channels_broadcast.api._deliver` supplies the
    explicit success sentinel that callers should use instead.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        raise RuntimeError(
            "No channel layer configured. Set CHANNEL_LAYERS in settings.py "
            "(see channels documentation)."
        )

    send_fn = channel_layer.group_send
    if channel_name.startswith("specific"):
        send_fn = channel_layer.send

    data = {**data, "type": "chat_message"}

    try:
        return async_to_sync(send_fn)(channel_name, data)
    except RuntimeError:
        return force_sync(send_fn, channel_name, data)


def send_notification(
    request_or_channel_name,
    level,
    text,
    closeURL=None,
):
    """Send a styled message to a user or a raw channel.

    Accepts either a Django ``HttpRequest`` (uses the request's user) or a
    raw channel name string.
    """
    channel_name = request_or_channel_name
    if hasattr(request_or_channel_name, "user") and hasattr(
        request_or_channel_name.user, "username"
    ):
        channel_name = get_channel_name_for_user(request_or_channel_name.user)

    return _send(
        channel_name,
        Message(
            text=text, cssClass=DEFAULT_TAGS.get(level), closeURL=closeURL
        )._asdict(),
    )


def send_redirect(specific_channel: str, redirect_url: str):
    """Tell a subscribed page to navigate to ``redirect_url``."""
    return _send(specific_channel, {"url": redirect_url})
