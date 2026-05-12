# django-channels-notifications

Pluggable websocket notifications for Django. Send realtime messages to:

- **all** connected clients (logged-in + anonymous), or
- only **authenticated** users, or
- only **anonymous** visitors, or
- a single **user** (all of their open tabs), or
- a single **page** subscribed to a specific object (via `ContentType`).

Each audience is gated by a Django setting — flip a flag, the consumer
refuses to join that group (or, for anonymous, refuses to open the
websocket at all).

## Installation

```bash
pip install django-channels-notifications
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "channels",
    "channels_notifications",
]
```

Wire the websocket route into your `asgi.py`:

```python
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels_notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})
```

Set a channel layer (see [channels docs](https://channels.readthedocs.io/)):

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
    },
}
```

Run migrations:

```bash
./manage.py migrate channels_notifications
```

## Settings — audience gates

| Setting | Default | What turning it off does |
|---|---|---|
| `CHANNELS_NOTIFICATIONS_ENABLE_ALL` | `True` | `send_to_all()` becomes a no-op and the consumer doesn't join the broadcast group. |
| `CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED` | `True` | `send_to_authenticated()` and `send_to_user()` are no-ops; consumer skips the authenticated-only group and the per-user channel. |
| `CHANNELS_NOTIFICATIONS_ENABLE_ANONYMOUS` | `False` | **The consumer closes anonymous connections before `.accept()` — no websocket is opened for them.** `send_to_anonymous()` is a no-op. |
| `CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS` | `True` | `send_to_object()` is a no-op; consumer ignores `?extraChannels=` subscriptions. |

The most security-relevant flag is `ENABLE_ANONYMOUS`. Off by default so anonymous visitors don't open a connection at all — flip it on deliberately.

## Sending notifications

```python
from channels_notifications import (
    send_to_all,
    send_to_authenticated,
    send_to_anonymous,
    send_to_user,
    send_to_object,
)

send_to_all("System maintenance starts in 10 minutes.", level="warning")
send_to_authenticated("New report available.")
send_to_anonymous("Welcome — sign in to save your work.")
send_to_user(user, "Your import finished.")
send_to_object(article, "Someone just commented on this page.")
```

`level` accepts a `django.contrib.messages` constant (`INFO`, `SUCCESS`,
`WARNING`, `ERROR`) or a string CSS class (`"info"`, `"success"`,
`"warning"`, `"error"`).

## Object-channel subscriptions (per-page)

In a class-based view:

```python
from django.views.generic import DetailView
from channels_notifications.mixins import ChannelSubscriberSingleObjectMixin

class ArticleDetail(ChannelSubscriberSingleObjectMixin, DetailView):
    model = Article
```

Then in the template, render the channel list into a query string that
the frontend JS hands to the websocket as `?extraChannels=…`. The
included static files (`channels_notifications/js/notifications.js`)
already do this — read the source for the wiring.

## Management command

```bash
./manage.py send_notification --audience=all "Hello everyone"
./manage.py send_notification --audience=authenticated "Hello logged-in users"
./manage.py send_notification --audience=anonymous "Hello anons"
./manage.py send_notification --audience=user --username=alice "Hi Alice"
```

## Requirements

- Python ≥ 3.10
- Django ≥ 5.2 (5.2 LTS, 6.0)
- channels ≥ 4.0
- A channel layer backend (`channels-redis` in production,
  `InMemoryChannelLayer` in tests)

## Development

```bash
git clone https://github.com/iplweb/django-channels-notifications
cd django-channels-notifications
uv sync --all-extras
DJANGO_SETTINGS_MODULE=tests.settings uv run pytest
```

Pre-commit:

```bash
uv run pre-commit install
```

## License

MIT — see [LICENSE](./LICENSE).
