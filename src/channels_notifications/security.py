"""Subscription authorization.

Two complementary mechanisms control which channels a websocket
connection is allowed to subscribe to via ``?extraChannels=`` and
``?subscription_token=``:

1. **Subscription authorizer** — a settings-pluggable callable invoked
   once per channel name in ``?extraChannels=``. Returns ``True`` to
   allow, ``False`` (or any falsy) to silently drop the subscription.
   Default: deny everything.

   Configure via::

       CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER = "myapp.notif.authorize"

   The callable receives ``(user, channel_name)`` and must return a bool.

2. **Signed subscription tokens** — for channels that don't correspond
   to a Django model (UID/UUID per page, opaque tokens, etc.) you
   issue a token server-side that cryptographically binds a user to a
   set of channel names. Browser sends it as ``?subscription_token=``;
   the consumer verifies signature, user match, and expiry, then
   subscribes — bypassing the authorizer because the binding is
   already proof of authorization.

   No Redis or server-side storage required — the token is a signed
   payload (``django.core.signing.TimestampSigner``).

Both mechanisms are layered on top of the audience flags
(``ENABLE_ALL/AUTHENTICATED/ANONYMOUS/PAGE_CHANNELS``) and the per-user
channel; the authorizer / token only gate **extra** channels requested
by the client. The audience groups are always handled by the consumer
itself based on ``scope["user"]``.
"""

import json
from typing import Any

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils.module_loading import import_string

# Salt namespaces the signed payload — different libraries signing with
# the same SECRET_KEY won't produce interchangeable tokens.
_SIGNING_SALT = "channels_notifications.subscription_token"

# Default token lifetime if the caller doesn't pass `ttl`.
DEFAULT_TOKEN_TTL_SECONDS = 300


# ----------------------------------------------------- authorizer hook


def _deny_all(user: Any, channel_name: str) -> bool:
    """Default authorizer — refuses every ``?extraChannels=`` entry.

    Override by setting
    ``CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER`` to a dotted path.
    """
    return False


def _resolve_authorizer():
    path = getattr(settings, "CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER", None)
    if not path:
        return _deny_all
    return import_string(path)


def authorize_extra_channel(user: Any, channel_name: str) -> bool:
    """Run the configured authorizer for one channel name.

    The consumer calls this for every entry in ``?extraChannels=`` at
    websocket connect time. Tokens (``?subscription_token=``) bypass
    this — they're already a proof of authorization.
    """
    return bool(_resolve_authorizer()(user, channel_name))


# ----------------------------------------------- signed tokens (issue)


def _user_id(user: Any):
    """Return the user's PK if authenticated, else ``None``."""
    if user is None:
        return None
    if not getattr(user, "is_authenticated", False):
        return None
    return user.pk


def issue_subscription_token(
    user: Any,
    channels,
    *,
    ttl: int = DEFAULT_TOKEN_TTL_SECONDS,
) -> str:
    """Sign a (user, channels) pair into a single string.

    Pass the resulting token into the page (template context); when the
    browser opens a websocket with ``?subscription_token=<token>`` the
    consumer will verify the signature, check the bound user matches the
    request's user, check the token hasn't expired (default 5 min), and
    subscribe to ``channels``.

    The TTL controls how long the token remains valid after issuance —
    not how long the resulting websocket stays open. Once subscribed,
    the connection lives as long as the websocket itself.

    Anonymous users: pass ``user=None`` (or any AnonymousUser). The token
    will only be honored on connections that are also anonymous; logging
    in mid-session won't let you replay it as the new identity.
    """
    payload = json.dumps(
        {"u": _user_id(user), "c": list(channels), "t": int(ttl)},
        separators=(",", ":"),
    )
    return TimestampSigner(salt=_SIGNING_SALT).sign(payload)


# ---------------------------------------------- signed tokens (verify)


def verify_subscription_token(token: str, user: Any) -> list[str]:
    """Return the channels list from a valid token, ``[]`` otherwise.

    Failures (bad signature, expired, user mismatch, malformed payload)
    all produce ``[]`` without distinguishing — the websocket consumer
    just falls back to its baseline subscriptions. We deliberately don't
    raise: an attacker should not learn whether their token was rejected
    for a bad signature vs. a user mismatch.
    """
    if not token:
        return []

    try:
        raw = TimestampSigner(salt=_SIGNING_SALT).unsign(token)
        payload = json.loads(raw)
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return []

    if not isinstance(payload, dict):
        return []

    ttl = payload.get("t")
    if not isinstance(ttl, int) or ttl <= 0:
        return []
    # Re-check expiry against the token's own embedded TTL: we always
    # signed with the *default* signer (no max_age at unsign time), so
    # we must enforce TTL ourselves here.
    try:
        TimestampSigner(salt=_SIGNING_SALT).unsign(token, max_age=ttl)
    except (BadSignature, SignatureExpired):
        return []

    issued_to = payload.get("u")
    requester = _user_id(user)
    if issued_to != requester:
        return []

    channels = payload.get("c")
    if not isinstance(channels, list):
        return []
    return [str(c) for c in channels]
