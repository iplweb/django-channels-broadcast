# Example project for `django-channels-broadcast`

Minimal Django project showing **all five** audience modes, including the
per-page (object-channel) one.

## Run

```bash
cd example
uv run python manage.py migrate
uv run python manage.py createsuperuser  # for the per-user demo
uv run python manage.py runserver
```

`runserver` is ASGI-aware here because `"daphne"` is listed first in
`INSTALLED_APPS` (see `example_project/settings.py`). Without that, the
stock Django `runserver` is HTTP-only and every `/asgi/notifications/`
connect returns 404. If you'd rather run Daphne directly:

```bash
uv run daphne -p 8000 example_project.asgi:application
```

Open these in separate tabs:

1. `http://127.0.0.1:8000/` — authenticated (log in at `/admin/` first)
2. `http://127.0.0.1:8000/` — anonymous (incognito window)
3. `http://127.0.0.1:8000/things/<pk>/` — a per-object page (create a Thing
   at `/admin/demo_app/thing/add/` first)

From the home page's form, pick an audience and hit *Send*. Watch which
tabs receive the message:

| Audience | Tab 1 (auth) | Tab 2 (anon) | Tab 3 (Thing detail) |
|---|:---:|:---:|:---:|
| all | ✓ | ✓ | ✓ |
| authenticated | ✓ | — | ✓ (if logged in) |
| anonymous | — | ✓ | ✓ (if anonymous) |
| user → <username> | ✓ (that user only) | — | ✓ (if same user) |
| **object → Thing PK** | — | — | **✓ (only that Thing's page)** |

Toggle `CHANNELS_BROADCAST_ENABLE_ANONYMOUS = False` in
`example_project/settings.py` and reload the anonymous tab — its
websocket closes immediately on connect.

## What's wired

- `example_project/settings.py` — every gate flag set explicitly so
  you can toggle and watch the effect.
- `example_project/asgi.py` — `AuthMiddlewareStack` + URLRouter wiring
  `channels_broadcast.routing.websocket_urlpatterns`.
- `example_project/views.py` — single endpoint dispatching to each
  `send_to_*` API (incl. `send_to_object` from the new "object"
  audience option).
- `templates/home.html` — broadcast-form page; opens a websocket
  without `extraChannels` (joins the `__all__` / authenticated /
  anonymous groups, no object channel).
- **`demo_app/`** — a tiny Django app providing a `Thing` model so the
  per-page demo has a real `ContentType` + pk to derive channel names
  from.
- **`demo_app/views.py`** — `ThingDetail` is a `DetailView` mixed with
  `ChannelSubscriberSingleObjectMixin`. The mixin auto-subscribes the
  page to channel `demo_app.thing-<pk>` by calling
  `convert_obj_to_channel_name(get_object())` and placing the name
  into context as `extraChannels`.
- **`templates/demo_app/thing_detail.html`** — surfaces the channel
  name visibly on the page (so you can see what the object's UID is),
  serialises `extraChannels` via Django's `json_script`, and opens a
  websocket with `?extraChannels=…` so the consumer subscribes to that
  page's channel in addition to the audience groups.

The library does not generate a "page UID" out of thin air — it derives
the channel name from `(ContentType.app_label, ContentType.model, pk)`,
which is stable as long as the row exists. If you need a channel that
isn't backed by a Django model (a transient UUID per browser tab, say),
pass the channel name directly to `convert_obj_to_channel_name`'s caller
sites or just `send` to whatever string you like — both ends just have
to agree on the name.

> Uses `InMemoryChannelLayer` for portability. For multi-process
> production deployments use `channels-redis`.
