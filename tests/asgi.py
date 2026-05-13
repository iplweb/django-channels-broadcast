"""Minimal ASGI application for consumer tests.

Wires :mod:`channels_broadcast.routing` together with the standard
auth middleware stack so the consumer sees a populated ``scope["user"]``.
"""

import django

django.setup()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from channels_broadcast.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
