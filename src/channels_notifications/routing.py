from django.urls import re_path

from channels_notifications.consumers import NotificationsConsumer

websocket_urlpatterns = [
    re_path(r"asgi/notifications/$", NotificationsConsumer.as_asgi()),
]
