"""Settings contract for channels_notifications.

Every audience is opt-in/opt-out via a Django setting. Defaults aim for a
sensible reusable-app baseline: everything *except* anonymous broadcasting
is enabled. Anonymous opens a websocket for every visitor and is the most
sensitive flag — flip it on deliberately.

Override in your project's settings.py:

    CHANNELS_NOTIFICATIONS_ENABLE_ALL = True
    CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED = True
    CHANNELS_NOTIFICATIONS_ENABLE_ANONYMOUS = False
    CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS = True
"""

from django.conf import settings

GROUP_ALL = "channels_notifications.all"
GROUP_AUTHENTICATED = "channels_notifications.authenticated"
GROUP_ANONYMOUS = "channels_notifications.anonymous"

DEFAULTS = {
    "CHANNELS_NOTIFICATIONS_ENABLE_ALL": True,
    "CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED": True,
    "CHANNELS_NOTIFICATIONS_ENABLE_ANONYMOUS": False,
    "CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS": True,
}


def _flag(name: str) -> bool:
    return bool(getattr(settings, name, DEFAULTS[name]))


def is_all_enabled() -> bool:
    return _flag("CHANNELS_NOTIFICATIONS_ENABLE_ALL")


def is_authenticated_enabled() -> bool:
    return _flag("CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED")


def is_anonymous_enabled() -> bool:
    return _flag("CHANNELS_NOTIFICATIONS_ENABLE_ANONYMOUS")


def is_page_channels_enabled() -> bool:
    return _flag("CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS")
