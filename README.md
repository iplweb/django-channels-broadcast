# django-channels-broadcast

[![Tests](https://github.com/iplweb/django-channels-broadcast/actions/workflows/tests.yml/badge.svg)](https://github.com/iplweb/django-channels-broadcast/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Pluggable websocket notifications for Django. Send realtime messages to:

- **all** connected clients (logged-in + anonymous), or
- only **authenticated** users, or
- only **anonymous** visitors, or
- a single **user** (all of their open tabs), or
- a single **page** subscribed to a specific object (via `ContentType`).

Each audience is gated by a Django setting — flip a flag, the consumer
refuses to join that group (or, for anonymous, refuses to open the
websocket at all).

## Why?

Most Django notification libraries assume "every message goes to a user
row in the database." That's fine for inbox-style notifications, but
falls over the moment you want to broadcast to anonymous visitors, to
everyone watching a single page, or to a transient cohort that doesn't
map cleanly to `auth.User`.

`django-channels-broadcast` is the thin layer this project kept rewriting
in-house: five send-to-X functions on top of `channels.layers`, each
backed by a documented channel-group name, each individually toggleable
in `settings.py`. Anonymous defaults to off because opening a websocket
for every public visitor is the kind of decision you want to make
deliberately, not by accident.

## Features

- **Five audience modes**, three payload families: messages, redirects,
  progress. Eighteen functions in total
  (`send_to_*` / `redirect_*` / `progress_*` × `all` / `authenticated` /
  `anonymous` / `user` / `object` / `channel`).
- **Per-audience feature flags** — disabling an audience is a real off
  switch: the consumer refuses to join the group, and for anonymous
  visitors the websocket itself is never opened.
- **Per-page subscriptions** via `ChannelSubscriberSingleObjectMixin` —
  pages auto-subscribe to a `<app_label>.<model>-<pk>` channel through
  `ContentType`, gated by an authorizer hook.
- **Default-deny on `?extraChannels=`** — the consumer will not subscribe
  any channel a hostile page asks for unless a configured authorizer
  callback explicitly returns True. No "trust the browser" defaults.
- **Signed subscription tokens** — bind a server-issued UID/UUID channel
  to a specific user for N minutes using Django's signing framework.
  Stateless, no Redis needed.
- **Replay on reconnect**: unacknowledged `Notification` rows are
  re-sent the next time a relevant client connects.
- **`send_notification` management command** with `--audience=…` for
  CLI / Celery / cron-driven broadcasts.
- **Drop-in JS client** under `static/channels_notifications/js/` —
  vanilla JS, no jQuery requirement.

## Installation

### Using uv (recommended)

```bash
uv add django-channels-broadcast
```

### Using pip

```bash
pip install django-channels-broadcast
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

## Settings

### Audience gates

| Setting | Default | What turning it off does |
|---|---|---|
| `CHANNELS_NOTIFICATIONS_ENABLE_ALL` | `True` | `send_to_all()` becomes a no-op and the consumer doesn't join the broadcast group. |
| `CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED` | `True` | `send_to_authenticated()`, `send_to_user()`, `redirect_user()`, `progress_user()` are no-ops; consumer skips the authenticated-only group and the per-user channel. |
| `CHANNELS_NOTIFICATIONS_ENABLE_ANONYMOUS` | `False` | **The consumer closes anonymous connections before `.accept()` — no websocket is opened for them.** `send_to_anonymous()` is a no-op. |
| `CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS` | `True` | `send_to_object()` / `redirect_object()` / `progress_object()` / `*_channel()` are no-ops; consumer ignores `?extraChannels=` and `?subscription_token=` subscriptions. |

The most security-relevant flag is `ENABLE_ANONYMOUS`. Off by default so anonymous visitors don't open a connection at all — flip it on deliberately.

### Subscription authorization

| Setting | Default | Effect |
|---|---|---|
| `CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER` | `None` (deny all) | Dotted path to a callable `(user, channel_name) -> bool` that decides whether a `?extraChannels=` entry is allowed. See "Security model" below. |

## Sending notifications

Three payload families, six target variants each.

### Messages

```python
from channels_notifications import (
    send_to_all, send_to_authenticated, send_to_anonymous,
    send_to_user, send_to_object, send_to_channel,
)

send_to_all("System maintenance starts in 10 minutes.", level="warning")
send_to_authenticated("New report available.")
send_to_anonymous("Welcome — sign in to save your work.")
send_to_user(user, "Your import finished.")
send_to_object(article, "Someone just commented on this page.")
send_to_channel("op-uid-42", "Step 3 of 5 complete.")   # raw channel name
```

`level` accepts a `django.contrib.messages` constant (`INFO`, `SUCCESS`,
`WARNING`, `ERROR`) or a string CSS class (`"info"`, `"success"`,
`"warning"`, `"error"`).

### Redirects

Tell the receiving page to navigate. Useful at the end of a long-running
task — bounce the user from a progress page to the results page without
polling.

```python
from channels_notifications import redirect_user, redirect_object, redirect_channel

redirect_user(user, "/reports/42/")
redirect_object(report, "/reports/42/results/")
redirect_channel("op-uid-42", "/done/")
```

### Progress

Push a percent to whatever page is showing a progress bar. The bundled
JS client looks for a `#notifications-progress` element by default; or
write your own listener for `{"progress": true, "percent": "42%"}`.

```python
from channels_notifications import progress_user, progress_object, progress_channel

progress_user(user, 42)          # → "42%"
progress_object(report, 75)
progress_channel("op-uid-42", 100)
```

`percent` accepts int, float, or string. A `%` is appended if missing.

## Security model

The websocket has the same authentication the rest of your Django app
does (session cookie, via `AuthMiddlewareStack`). Beyond that, the
consumer composes its channel subscriptions from four sources, in order
of increasing client influence:

1. **Audience groups** derived from `scope["user"]` and the
   `ENABLE_*` flags. Always trusted — server-controlled.
2. **Per-user channel** for authenticated users. Always trusted.
3. **`?extraChannels=` query param** — every channel name passes through
   a configurable authorizer. **Default: deny.**
4. **`?subscription_token=` query param** — a server-signed binding of
   `(user, channels, expiry)`. Bypasses the authorizer; the signature
   already proves authorization.

### Threat model

- A page rendered by your views may ask for `?extraChannels=…` — but
  the consumer doesn't trust the request: the authorizer decides.
- A user who edits the page source to add arbitrary channels gets no
  subscriptions for them (default authorizer denies all).
- A user who steals another user's signed token can't replay it — the
  bound user is checked against `scope["user"]` at connect time.
- Anonymous users get no websocket at all if `ENABLE_ANONYMOUS=False`
  (default).

### Configuring the authorizer

For `?extraChannels=` to ever subscribe, point Django at a callable:

```python
# settings.py
CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER = "myapp.notif.authorize"
```

```python
# myapp/notif.py
from channels_notifications import get_obj_from_channel_name

def authorize(user, channel_name):
    """Return True if user is allowed to subscribe to channel_name."""
    try:
        obj = get_obj_from_channel_name(channel_name)
    except Exception:
        return False
    return user.has_perm("can_view", obj)
```

The function runs once per channel at connect time. Channels it denies
are silently dropped (no information about which channels exist leaks
back to the client).

### Server-issued UID channels (signed tokens)

When the channel isn't backed by a Django model — for example, a
per-page UUID for a long-running background task — issue a token:

```python
import uuid
from channels_notifications import issue_subscription_token

def my_view(request):
    stream_uid = str(uuid.uuid4())
    token = issue_subscription_token(
        user=request.user,            # bound to this user (or None for anon)
        channels=[stream_uid],
        ttl=300,                      # 5 minutes
    )
    return render(request, "stream.html", {
        "stream_uid": stream_uid,
        "subscription_token": token,
    })
```

```html
{{ subscription_token|json_script:"sub-token" }}
<script>
  var token = JSON.parse(document.getElementById("sub-token").textContent);
  var ws = new WebSocket(
    "ws://example.com/asgi/notifications/"
    + "?subscription_token=" + encodeURIComponent(token));
</script>
```

The consumer verifies signature, user binding, and TTL, then subscribes
to `stream_uid`. Tokens are **stateless** — uses Django's
`TimestampSigner`, signed with `SECRET_KEY`, no Redis or DB required.
If you eventually need revocation (e.g. on logout), write a thin
revocation list and check it in a custom consumer — most apps don't
need it.

### Pushing messages to UID channels

From a Celery worker, view, or anywhere on the server side:

```python
from channels_notifications import progress_channel, send_to_channel

progress_channel(stream_uid, 42)
send_to_channel(stream_uid, "Done!", level="success")
```

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

## Frontend integration

Three JS files ship under `static/channels_notifications/js/`:

| File | What it does |
|---|---|
| `notifications.js` | Required. Opens the websocket; dispatches incoming `{text}` / `{url}` / `{progress, percent}` payloads. Default text rendering uses jQuery + Mustache to append to `#messagesPlaceholder`. Falls back to vanilla-JS DOM if neither is available. Exposes `window.channelsBroadcast`. |
| `notifications-toastify.js` | Optional. Calls `channelsBroadcast.useToastify({...})` to swap the default appender for right-side toast popups via [Toastify](https://github.com/apvarun/toastify-js) (~3KB, MIT). Redirects and progress payloads keep working unchanged. |
| `notifications-chime.js` | Optional. Plays a four-note arpeggio on each incoming message via [Tone.js](https://tonejs.github.io/). Calls `channelsBroadcast.enableChime()` after `init()` to install the hook. Defers audio context until first user gesture (browser autoplay policies). |

### Default — inline Foundation/Bootstrap-style alerts

```html
{% load static %}
<div id="messagesPlaceholder"></div>
<script id="messageTemplate" type="text/x-template">{# Mustache template #}
  <div class="callout {{ cssClass }}">{{ text }}</div>
</script>

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="{% static 'channels_notifications/js/mustache.js' %}"></script>
<script src="{% static 'channels_notifications/js/notifications.js' %}"></script>
<script>
  channelsBroadcast.init({{ extraChannels|default:"null"|json_script:"" }});
</script>
```

### Pretty mode — right-side toasts (Toastify)

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/toastify-js/src/toastify.css">
<script src="https://cdn.jsdelivr.net/npm/toastify-js"></script>
<script src="{% static 'channels_notifications/js/notifications.js' %}"></script>
<script src="{% static 'channels_notifications/js/notifications-toastify.js' %}"></script>
<script>
  channelsBroadcast.useToastify({duration: 4000, gravity: "top", position: "right"});
  channelsBroadcast.init();
</script>
```

After `useToastify()`, any `send_to_*("text...")` call appears as a sliding toast in the top-right (default — `position` and `gravity` are configurable). The `cssClass` field maps to a per-level gradient; override with `classMap`.

### Audio chime (Tone.js)

```html
<script src="https://unpkg.com/tone@15/build/Tone.js"></script>
<script src="{% static 'channels_notifications/js/notifications.js' %}"></script>
<script src="{% static 'channels_notifications/js/notifications-chime.js' %}"></script>
<script>
  channelsBroadcast.init();
  channelsBroadcast.enableChime();
</script>
```

### Wire format (for writing your own client)

The server sends one JSON object per websocket frame:

```js
// message:
{"text": "...", "cssClass": "info"|"success"|"warning"|"error",
 "clickURL": "...", "closeURL": "...", "hideCloseOption": false}

// redirect:
{"url": "/results/"}

// progress:
{"progress": true, "percent": "42%"}
```

If `id` is present, the server expects the client to ACK with
`{"type": "ack_message", "id": <id>}` so it doesn't replay this
`Notification` row on the next reconnect. The bundled JS does this for
you.

## Supported versions

### Python × Django (tested in CI)

| Django  | 3.10 | 3.11 | 3.12 | 3.13 | Status                      |
|---------|------|------|------|------|-----------------------------|
| 5.2 LTS | ✓    | ✓    | ✓    | ✓    | Active LTS (until Apr 2028) |
| 6.0     | —    | —    | ✓    | ✓    | Active                      |

(Python 3.10–3.13 supported. Django 6.0 dropped support for Python ≤ 3.11,
so those cells are intentionally blank.)

### Other dependencies

- `channels` ≥ 4.0
- `asgiref` ≥ 3.7
- `nest-asyncio` ≥ 1.6
- A channel-layer backend at runtime — `channels-redis` in production,
  `channels.layers.InMemoryChannelLayer` in tests / single-process dev.

## Development

```bash
git clone https://github.com/iplweb/django-channels-broadcast
cd django-channels-broadcast
uv sync --all-extras
DJANGO_SETTINGS_MODULE=tests.settings uv run pytest    # Python tests
npm install && npm test                                # JS tests (QUnit + sinon + jsdom)
```

Pre-commit:

```bash
uv run pre-commit install
```

## License

MIT — see [LICENSE](./LICENSE).
