from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "example-not-for-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

# `daphne` MUST come first so it overrides Django's stock `runserver`
# with an ASGI-aware version that routes both HTTP and WebSocket. Without
# this, `./manage.py runserver` serves HTTP only and every websocket
# connect to /asgi/notifications/ returns 404.
INSTALLED_APPS = [
    "daphne",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.contrib.staticfiles",
    "channels",
    "channels_broadcast",
    "demo_app",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "example_project.urls"
ASGI_APPLICATION = "example_project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# ---------------------- channels_broadcast audience gates -------
# Demonstrates each flag. Anonymous users are off by default — flip on
# below to see anonymous broadcast working.
CHANNELS_BROADCAST_ENABLE_ALL = True
CHANNELS_BROADCAST_ENABLE_AUTHENTICATED = True
CHANNELS_BROADCAST_ENABLE_ANONYMOUS = True
CHANNELS_BROADCAST_ENABLE_PAGE_CHANNELS = True

# Authorizer for ?extraChannels= subscriptions. Library default is to
# DENY every extra channel — you must point this setting at a function
# that decides which channels each user may join. See
# demo_app/security.py for the function this demo uses (owner-only).
CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER = "demo_app.security.authorize"
