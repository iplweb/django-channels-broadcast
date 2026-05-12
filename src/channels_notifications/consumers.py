"""WebSocket consumer subscribing each connection to its allowed audiences.

The consumer composes the set of channels to join from four sources, in
order:

1. **Audience groups** derived from ``scope["user"]`` and the
   ``CHANNELS_NOTIFICATIONS_ENABLE_*`` flags. Always trusted —
   the auth comes from the Django session cookie.

2. **Per-user channel** (authenticated users only). Always trusted.

3. **``?extraChannels=`` query param** — each channel name is passed
   through the configured subscription authorizer
   (``CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER``). Channels the
   authorizer rejects are silently dropped. Default authorizer denies
   everything, so this is opt-in.

4. **``?subscription_token=`` query param** — a server-issued, signed
   token (see ``channels_notifications.security.issue_subscription_token``)
   that binds a user to a set of channel names. The channels in a valid
   token are subscribed without consulting the authorizer.

If anonymous broadcasting is disabled, anonymous connections are closed
before ``.accept()`` — no websocket is opened for them at all.
"""

import json
from urllib.parse import parse_qs

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.utils.functional import cached_property

from channels_notifications import settings as cn_settings
from channels_notifications.core import get_channel_name_for_user
from channels_notifications.security import (
    authorize_extra_channel,
    verify_subscription_token,
)


class NotificationsConsumer(WebsocketConsumer):
    """Bidirectional websocket. Subscribes on connect, ACKs on incoming JSON."""

    def _parse_query(self) -> dict:
        return parse_qs(self.scope.get("query_string", b""))

    def _audience_channels(self):
        """Channels derived purely from the authenticated identity."""
        user = self.scope.get("user")
        is_auth = bool(user and getattr(user, "is_authenticated", False))

        if cn_settings.is_all_enabled():
            yield cn_settings.GROUP_ALL

        if is_auth and cn_settings.is_authenticated_enabled():
            yield cn_settings.GROUP_AUTHENTICATED
            yield get_channel_name_for_user(user)
        elif (not is_auth) and cn_settings.is_anonymous_enabled():
            yield cn_settings.GROUP_ANONYMOUS

    def _extra_channels_from_query(self, qstr):
        """Channels requested via ``?extraChannels=`` that the authorizer permits."""
        if not cn_settings.is_page_channels_enabled():
            return
        if b"extraChannels" not in qstr:
            return
        try:
            requested = json.loads(qstr[b"extraChannels"][0])
        except (ValueError, IndexError):
            return
        user = self.scope.get("user")
        for elem in requested:
            name = str(elem)
            if authorize_extra_channel(user, name):
                yield name

    def _token_channels_from_query(self, qstr):
        """Channels carried by a valid signed subscription token."""
        if not cn_settings.is_page_channels_enabled():
            return
        if b"subscription_token" not in qstr:
            return
        try:
            token = qstr[b"subscription_token"][0].decode("utf-8")
        except (UnicodeDecodeError, IndexError):
            return
        user = self.scope.get("user")
        yield from verify_subscription_token(token, user)

    def _channels(self):
        qstr = self._parse_query()
        yield from self._audience_channels()
        yield from self._extra_channels_from_query(qstr)
        yield from self._token_channels_from_query(qstr)

    @cached_property
    def channels(self):
        # de-dup while preserving order — same channel via multiple sources
        # should only be joined once.
        seen = set()
        result = []
        for ch in self._channels():
            if ch not in seen:
                seen.add(ch)
                result.append(ch)
        return result

    def subscribe(self):
        for channel in self.channels:
            async_to_sync(self.channel_layer.group_add)(channel, self.channel_name)

    def unsubscribe(self):
        for channel in self.channels:
            async_to_sync(self.channel_layer.group_discard)(channel, self.channel_name)

    def connect(self):
        user = self.scope.get("user")
        is_auth = bool(user and getattr(user, "is_authenticated", False))

        if not is_auth and not cn_settings.is_anonymous_enabled():
            self.close()
            return

        self.subscribe()
        self.accept()

        from channels_notifications.models import Notification

        Notification.objects.on_connect(self.channels)

    def disconnect(self, close_code):
        self.unsubscribe()

    def chat_message(self, event):
        self.send(text_data=json.dumps(event))

    def receive(self, text_data):
        text_data_json = json.loads(text_data)

        if text_data_json.get("type") == "ack_message":
            from channels_notifications.models import Notification

            try:
                n = Notification.objects.get(id=text_data_json["id"])
            except Notification.DoesNotExist:
                return

            if n.channel_name in self.channels:
                n.acknowledge()
