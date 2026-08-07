"""Tests for the public audience-routing API in channels_broadcast.api.

Each test patches ``_send`` so we can assert which channel the API selected
without needing a real channel layer round-trip.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from model_bakery import baker

from channels_broadcast import api
from channels_broadcast import settings as cn_settings


@pytest.fixture
def captured(monkeypatch):
    calls = []

    def fake_send(channel_name, data):
        calls.append((channel_name, data))

    monkeypatch.setattr("channels_broadcast.api._send", fake_send)
    return calls


# ---------------------------------------------------------- send_to_all


def test_send_to_all_uses_group_all(captured):
    api.send_to_all("hello")
    assert len(captured) == 1
    assert captured[0][0] == cn_settings.GROUP_ALL
    assert captured[0][1]["text"] == "hello"


@override_settings(CHANNELS_BROADCAST_ENABLE_ALL=False)
def test_send_to_all_disabled_is_noop(captured):
    assert api.send_to_all("hello") is None
    assert captured == []


# ---------------------------------------------- send_to_authenticated


def test_send_to_authenticated_uses_group_authenticated(captured):
    api.send_to_authenticated("hello")
    assert captured[0][0] == cn_settings.GROUP_AUTHENTICATED


@override_settings(CHANNELS_BROADCAST_ENABLE_AUTHENTICATED=False)
def test_send_to_authenticated_disabled_is_noop(captured):
    assert api.send_to_authenticated("hello") is None
    assert captured == []


# -------------------------------------------------- send_to_anonymous


def test_send_to_anonymous_disabled_by_default_is_noop(captured):
    assert api.send_to_anonymous("hello") is None
    assert captured == []


@override_settings(CHANNELS_BROADCAST_ENABLE_ANONYMOUS=True)
def test_send_to_anonymous_enabled_uses_group_anonymous(captured):
    api.send_to_anonymous("hello")
    assert captured[0][0] == cn_settings.GROUP_ANONYMOUS


# ------------------------------------------------------ send_to_user


@pytest.mark.django_db
def test_send_to_user_uses_per_user_channel(captured):
    user = get_user_model().objects.create_user(username="alice", password="x")
    api.send_to_user(user, "hello")
    assert len(captured) == 1
    # Channel name is a hash; the important property is that it is stable
    # per user. Re-call and ensure same channel reused.
    api.send_to_user(user, "hello again")
    assert captured[1][0] == captured[0][0]


@override_settings(CHANNELS_BROADCAST_ENABLE_AUTHENTICATED=False)
@pytest.mark.django_db
def test_send_to_user_respects_authenticated_flag(captured):
    user = get_user_model().objects.create_user(username="alice", password="x")
    assert api.send_to_user(user, "hello") is None
    assert captured == []


# ---------------------------------------------------- send_to_object


@pytest.mark.django_db
def test_send_to_object_uses_object_channel(captured):
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    api.send_to_object(obj, "hello")
    assert captured[0][0].startswith("testapp.thing-")
    assert captured[0][0].endswith(str(obj.pk))


@override_settings(CHANNELS_BROADCAST_ENABLE_PAGE_CHANNELS=False)
@pytest.mark.django_db
def test_send_to_object_respects_page_channels_flag(captured):
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    assert api.send_to_object(obj, "hello") is None
    assert captured == []


# --------------------------------------------------------- payloads


def test_payload_includes_text_and_css_class(captured):
    api.send_to_all("hi there", level="warning")
    payload = captured[0][1]
    assert payload["text"] == "hi there"
    assert payload["cssClass"] == "warning"


def test_payload_translates_integer_levels(captured):
    from django.contrib.messages import constants

    api.send_to_all("hi", level=constants.ERROR)
    assert captured[0][1]["cssClass"] == "error"


# ------------------------------------------------- return-value contract
#
# Truthy == dispatched, None == no-op. It has to be a sentinel produced by
# the api layer: channel_layer.group_send()/send() return None *on success*,
# so forwarding their return value would make every call look like a no-op.


@pytest.mark.django_db
def test_every_sender_returns_truthy_when_enabled(captured):
    from tests.testapp.models import Thing

    user = get_user_model().objects.create_user(username="alice", password="x")
    obj = baker.make(Thing)

    results = [
        api.send_to_all("hi"),
        api.send_to_authenticated("hi"),
        api.send_to_user(user, "hi"),
        api.send_to_object(obj, "hi"),
        api.send_to_channel("stream-abc", "hi"),
        api.redirect_user(user, "/x/"),
        api.redirect_object(obj, "/x/"),
        api.redirect_channel("stream-abc", "/x/"),
        api.progress_user(user, 10),
        api.progress_object(obj, 10),
        api.progress_channel("stream-abc", 10),
    ]

    assert len(captured) == len(results)
    assert all(r is True for r in results), results


def test_sender_returns_truthy_over_the_real_channel_layer():
    """Same contract without patching _send — the transport returns None."""
    assert api.send_to_all("hi") is True
