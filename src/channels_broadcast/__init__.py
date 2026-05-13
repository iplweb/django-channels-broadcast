"""channels_broadcast — pluggable websocket notification dispatch for Django.

Public API:

    # Messages (rendered as inline/toast notifications):
    from channels_broadcast import (
        send_to_all,             # broadcast to every connected client
        send_to_authenticated,   # broadcast to every authenticated user
        send_to_anonymous,       # broadcast to every anonymous visitor
        send_to_user,            # all open tabs/pages of one user
        send_to_object,          # one specific page subscribed to an object
        send_to_channel,         # raw channel-name escape hatch (UIDs, etc.)
    )

    # Redirects (tell the receiving page to navigate):
    from channels_broadcast import (
        redirect_user, redirect_object, redirect_channel,
    )

    # Progress bar updates:
    from channels_broadcast import (
        progress_user, progress_object, progress_channel,
    )

    # Channel-name helpers (round-trippable):
    from channels_broadcast import (
        convert_obj_to_channel_name, get_obj_from_channel_name,
        get_channel_name_for_user,
    )

    # Signed subscription tokens (for server-issued UID channels):
    from channels_broadcast import issue_subscription_token

Audience channels are individually gated via Django settings — see
``channels_broadcast.settings``. Per-object subscriptions and
custom UID channels require either an authorizer
(``CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER``) or a server-issued
subscription token. See ``channels_broadcast.security``.
"""

from channels_broadcast.api import (
    progress_channel,
    progress_object,
    progress_user,
    redirect_channel,
    redirect_object,
    redirect_user,
    send_to_all,
    send_to_anonymous,
    send_to_authenticated,
    send_to_channel,
    send_to_object,
    send_to_user,
)
from channels_broadcast.core import (
    convert_obj_to_channel_name,
    get_channel_name_for_user,
    get_obj_from_channel_name,
)
from channels_broadcast.security import issue_subscription_token

__all__ = [
    # messages
    "send_to_all",
    "send_to_anonymous",
    "send_to_authenticated",
    "send_to_channel",
    "send_to_object",
    "send_to_user",
    # redirects
    "redirect_channel",
    "redirect_object",
    "redirect_user",
    # progress
    "progress_channel",
    "progress_object",
    "progress_user",
    # helpers
    "convert_obj_to_channel_name",
    "get_channel_name_for_user",
    "get_obj_from_channel_name",
    # security
    "issue_subscription_token",
]
