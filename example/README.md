# Example project for `django-channels-broadcast`

Minimal Django project showing every audience mode.

## Run

```bash
cd example
uv run python manage.py migrate
uv run python manage.py createsuperuser  # for the per-user demo
uv run daphne -p 8000 example_project.asgi:application
```

Open `http://127.0.0.1:8000/` in two tabs:

1. one authenticated (log in at `/admin/` first), and
2. one anonymous (incognito window).

Pick an audience from the dropdown, hit *Send*, and watch which tab(s)
receive the message.

Toggle `CHANNELS_NOTIFICATIONS_ENABLE_ANONYMOUS = False` in
`example_project/settings.py` and reload — the anonymous tab's websocket
closes immediately on connect.

## What's wired

- `example_project/settings.py` — every gate flag set explicitly.
- `example_project/asgi.py` — `AuthMiddlewareStack` + URLRouter wiring
  `channels_notifications.routing.websocket_urlpatterns`.
- `example_project/views.py` — single endpoint dispatching to each
  `send_to_*` API.
- `templates/home.html` — bare-minimum HTML+JS websocket client.

> Uses `InMemoryChannelLayer` for portability. For multi-process
> production deployments use `channels-redis`.
