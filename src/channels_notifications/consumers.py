"""WebSocket consumer subscribing each connection to its allowed audiences.

The consumer reads the audience flags from
:mod:`channels_notifications.settings` and only subscribes to groups that
are enabled. If anonymous broadcasting is disabled, anonymous connections
are closed before ``accept()`` — no websocket is opened for them at all.
"""

import json
from urllib.parse import parse_qs

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.utils.functional import cached_property

from channels_notifications import settings as cn_settings
from channels_notifications.core import get_channel_name_for_user


class NotificationsConsumer(WebsocketConsumer):
    """Bidirectional websocket. Subscribes on connect, ACKs on incoming JSON."""

    def _channels(self):
        user = self.scope.get("user")
        is_auth = bool(user and getattr(user, "is_authenticated", False))

        if cn_settings.is_all_enabled():
            yield cn_settings.GROUP_ALL

        if is_auth and cn_settings.is_authenticated_enabled():
            yield cn_settings.GROUP_AUTHENTICATED
            yield get_channel_name_for_user(user)
        elif (not is_auth) and cn_settings.is_anonymous_enabled():
            yield cn_settings.GROUP_ANONYMOUS

        if cn_settings.is_page_channels_enabled():
            qstr = parse_qs(self.scope.get("query_string", b""))
            if b"extraChannels" in qstr:
                for elem in json.loads(qstr[b"extraChannels"][0]):
                    yield str(elem)

    @cached_property
    def channels(self):
        return list(self._channels())

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
