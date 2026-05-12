"""channels_notifications — pluggable websocket notification dispatch for Django.

Public API:

    from channels_notifications import (
        send_to_all,             # broadcast to every connected client
        send_to_authenticated,   # broadcast to every authenticated user
        send_to_anonymous,       # broadcast to every anonymous visitor
        send_to_user,            # all open tabs/pages of one user
        send_to_object,          # one specific page subscribed to an object
    )

Audience channels are individually gated via Django settings — see
``channels_notifications.settings``.
"""

from channels_notifications.api import (
    send_to_all,
    send_to_anonymous,
    send_to_authenticated,
    send_to_object,
    send_to_user,
)

__all__ = [
    "send_to_all",
    "send_to_anonymous",
    "send_to_authenticated",
    "send_to_object",
    "send_to_user",
]
