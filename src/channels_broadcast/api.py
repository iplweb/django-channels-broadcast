"""High-level audience-routing API.

Three payload families, each with the same set of audience targets:

- **Messages** (``send_to_*``) — render as toast/inline notifications.
- **Redirects** (``redirect_*``) — tell the receiving page to navigate.
- **Progress** (``progress_*``) — push a progress percent to the page.

Audience targets: ``all``, ``authenticated``, ``anonymous``, ``user``,
``object``, plus a raw ``channel`` escape hatch.

Return value contract: every function returns ``True`` once the payload
has been handed to the channel layer, and ``None`` when it did nothing
because the relevant ``CHANNELS_BROADCAST_ENABLE_*`` flag in
:mod:`channels_broadcast.settings` is False. ``True`` means "dispatched",
not "a browser rendered it" — the channel layer gives no delivery receipt
(``group_send``/``send`` return ``None`` on success), so the truthy value
is a sentinel produced here rather than something forwarded from below.
"""

from django.contrib.messages import constants as message_constants

from channels_broadcast import settings as cn_settings
from channels_broadcast.core import (
    Message,
    _send,
    convert_obj_to_channel_name,
    get_channel_name_for_user,
)


def _deliver(channel_name: str, payload: dict) -> bool:
    """Hand ``payload`` to the channel layer and report that we did.

    ``_send`` forwards the return value of ``channel_layer.group_send`` /
    ``.send``, and both return ``None`` *on success* — so the transport
    return value cannot distinguish "sent" from "did nothing". Callers
    (notably the ``send_notification`` management command) need that
    distinction, hence the explicit ``True`` sentinel.
    """
    _send(channel_name, payload)
    return True


def _message_payload(text: str, level: int | str | None, close_url: str | None) -> dict:
    if isinstance(level, int):
        css_class = message_constants.DEFAULT_TAGS.get(level, "info")
    elif isinstance(level, str):
        css_class = level
    else:
        css_class = "info"
    return Message(text=text, cssClass=css_class, closeURL=close_url)._asdict()


def _redirect_payload(url: str) -> dict:
    return {"url": url}


def _progress_payload(percent) -> dict:
    if isinstance(percent, (int, float)):
        percent_str = f"{percent}%"
    elif isinstance(percent, str) and not percent.endswith("%"):
        percent_str = f"{percent}%"
    else:
        percent_str = str(percent)
    return {"progress": True, "percent": percent_str}


# ============================================================ messages


def send_to_all(
    text: str, *, level="info", close_url: str | None = None
) -> bool | None:
    """Broadcast a message to every connected client (logged-in + anonymous).

    No-op if ``CHANNELS_BROADCAST_ENABLE_ALL`` is False.
    """
    if not cn_settings.is_all_enabled():
        return None
    return _deliver(cn_settings.GROUP_ALL, _message_payload(text, level, close_url))


def send_to_authenticated(
    text: str, *, level="info", close_url: str | None = None
) -> bool | None:
    """Broadcast a message to every authenticated user.

    No-op if ``CHANNELS_BROADCAST_ENABLE_AUTHENTICATED`` is False.
    """
    if not cn_settings.is_authenticated_enabled():
        return None
    return _deliver(
        cn_settings.GROUP_AUTHENTICATED, _message_payload(text, level, close_url)
    )


def send_to_anonymous(
    text: str, *, level="info", close_url: str | None = None
) -> bool | None:
    """Broadcast a message to every anonymous visitor.

    No-op if ``CHANNELS_BROADCAST_ENABLE_ANONYMOUS`` is False — also,
    if the flag is off the consumer rejects anonymous connections outright,
    so no websocket is ever opened for them.
    """
    if not cn_settings.is_anonymous_enabled():
        return None
    return _deliver(
        cn_settings.GROUP_ANONYMOUS, _message_payload(text, level, close_url)
    )


def send_to_user(
    user, text: str, *, level="info", close_url: str | None = None
) -> bool | None:
    """Send a message to all open pages of one specific user.

    Accepts a Django user instance or anything with ``.pk`` and ``.username``.
    No-op if ``CHANNELS_BROADCAST_ENABLE_AUTHENTICATED`` is False.
    """
    if not cn_settings.is_authenticated_enabled():
        return None
    channel = get_channel_name_for_user(user)
    return _deliver(channel, _message_payload(text, level, close_url))


def send_to_object(
    obj, text: str, *, level="info", close_url: str | None = None
) -> bool | None:
    """Send a message to any page subscribed to ``obj`` via ChannelSubscriberMixin.

    The page joins the channel ``<app_label>.<model>-<pk>`` on connect; this
    function broadcasts to that group. No-op if
    ``CHANNELS_BROADCAST_ENABLE_PAGE_CHANNELS`` is False.
    """
    if not cn_settings.is_page_channels_enabled():
        return None
    channel = convert_obj_to_channel_name(obj)
    return _deliver(channel, _message_payload(text, level, close_url))


def send_to_channel(
    channel_name: str, text: str, *, level="info", close_url: str | None = None
) -> bool | None:
    """Escape hatch: send a message to a raw channel name.

    Use when the channel is a server-issued UID (see ``issue_subscription_token``)
    that doesn't correspond to a Django model row. The page channels flag
    gates this — turning it off makes every channel-by-name send a no-op,
    including UID-based ones.
    """
    if not cn_settings.is_page_channels_enabled():
        return None
    return _deliver(channel_name, _message_payload(text, level, close_url))


# =========================================================== redirects


def redirect_user(user, url: str) -> bool | None:
    """Tell every open page of ``user`` to navigate to ``url``.

    Useful at the end of a long-running task: ``redirect_user(owner,
    results_url)`` jumps the user from the progress page to the results
    page without polling. No-op if ``ENABLE_AUTHENTICATED`` is False.
    """
    if not cn_settings.is_authenticated_enabled():
        return None
    return _deliver(get_channel_name_for_user(user), _redirect_payload(url))


def redirect_object(obj, url: str) -> bool | None:
    """Tell every page subscribed to ``obj`` to navigate to ``url``.

    No-op if ``ENABLE_PAGE_CHANNELS`` is False.
    """
    if not cn_settings.is_page_channels_enabled():
        return None
    return _deliver(convert_obj_to_channel_name(obj), _redirect_payload(url))


def redirect_channel(channel_name: str, url: str) -> bool | None:
    """Escape hatch — redirect a raw channel (UID, etc.)."""
    if not cn_settings.is_page_channels_enabled():
        return None
    return _deliver(channel_name, _redirect_payload(url))


# ============================================================ progress


def progress_user(user, percent) -> bool | None:
    """Update the progress bar on every open page of ``user``.

    ``percent`` may be an int/float (``42``), a string with a percent
    sign (``"42%"``), or any value — it'll be stringified and a ``%``
    appended if missing. No-op if ``ENABLE_AUTHENTICATED`` is False.
    """
    if not cn_settings.is_authenticated_enabled():
        return None
    return _deliver(get_channel_name_for_user(user), _progress_payload(percent))


def progress_object(obj, percent) -> bool | None:
    """Update the progress bar on every page subscribed to ``obj``.

    No-op if ``ENABLE_PAGE_CHANNELS`` is False.
    """
    if not cn_settings.is_page_channels_enabled():
        return None
    return _deliver(convert_obj_to_channel_name(obj), _progress_payload(percent))


def progress_channel(channel_name: str, percent) -> bool | None:
    """Escape hatch — push progress to a raw channel (UID, etc.)."""
    if not cn_settings.is_page_channels_enabled():
        return None
    return _deliver(channel_name, _progress_payload(percent))
