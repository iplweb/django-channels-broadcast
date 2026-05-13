from django.urls import path

from channels_broadcast.consumers import NotificationsConsumer

websocket_urlpatterns = [
    path("asgi/notifications/", NotificationsConsumer.as_asgi()),
]
