"""High-level audience-routing API.

Each function targets one of five audiences. If the relevant audience flag
in ``channels_notifications.settings`` is disabled, the call is a no-op
(returning ``None``) and no message reaches the channel layer. The consumer
also refuses to subscribe disabled audiences, so the websocket itself is
either never opened (anonymous gate) or never joined to the disabled group.
"""

from django.contrib.messages import constants as message_constants

from channels_notifications import settings as cn_settings
from channels_notifications.core import (
    Message,
    _send,
    convert_obj_to_channel_name,
    get_channel_name_for_user,
)


def _payload(text: str, level: int | str | None, close_url: str | None) -> dict:
    if isinstance(level, int):
        css_class = message_constants.DEFAULT_TAGS.get(level, "info")
    elif isinstance(level, str):
        css_class = level
    else:
        css_class = "info"
    return Message(text=text, cssClass=css_class, closeURL=close_url)._asdict()


def send_to_all(text: str, *, level="info", close_url: str | None = None):
    """Broadcast a message to every connected client (logged-in + anonymous).

    No-op if ``CHANNELS_NOTIFICATIONS_ENABLE_ALL`` is False.
    """
    if not cn_settings.is_all_enabled():
        return None
    return _send(cn_settings.GROUP_ALL, _payload(text, level, close_url))


def send_to_authenticated(text: str, *, level="info", close_url: str | None = None):
    """Broadcast a message to every authenticated user.

    No-op if ``CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED`` is False.
    """
    if not cn_settings.is_authenticated_enabled():
        return None
    return _send(cn_settings.GROUP_AUTHENTICATED, _payload(text, level, close_url))


def send_to_anonymous(text: str, *, level="info", close_url: str | None = None):
    """Broadcast a message to every anonymous visitor.

    No-op if ``CHANNELS_NOTIFICATIONS_ENABLE_ANONYMOUS`` is False — also,
    if the flag is off the consumer rejects anonymous connections outright,
    so no websocket is ever opened for them.
    """
    if not cn_settings.is_anonymous_enabled():
        return None
    return _send(cn_settings.GROUP_ANONYMOUS, _payload(text, level, close_url))


def send_to_user(user, text: str, *, level="info", close_url: str | None = None):
    """Send a message to all open pages of one specific user.

    Accepts a Django user instance or anything with ``.pk`` and ``.username``.
    No-op if ``CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED`` is False.
    """
    if not cn_settings.is_authenticated_enabled():
        return None
    channel = get_channel_name_for_user(user)
    return _send(channel, _payload(text, level, close_url))


def send_to_object(obj, text: str, *, level="info", close_url: str | None = None):
    """Send a message to any page subscribed to ``obj`` via ChannelSubscriberMixin.

    The page joins the channel ``<app_label>.<model>-<pk>`` on connect; this
    function broadcasts to that group. No-op if
    ``CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS`` is False.
    """
    if not cn_settings.is_page_channels_enabled():
        return None
    channel = convert_obj_to_channel_name(obj)
    return _send(channel, _payload(text, level, close_url))
