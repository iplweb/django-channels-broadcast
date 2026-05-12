"""Tests for redirect_* and progress_* API surface.

Same pattern as test_api.py: patch _send and verify the right channel
and payload was chosen.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from model_bakery import baker

from channels_notifications import (
    progress_channel,
    progress_object,
    progress_user,
    redirect_channel,
    redirect_object,
    redirect_user,
)
from channels_notifications import settings as cn_settings


@pytest.fixture
def captured(monkeypatch):
    calls = []

    def fake_send(channel_name, data):
        calls.append((channel_name, data))

    monkeypatch.setattr("channels_notifications.api._send", fake_send)
    return calls


# ============================================================ redirects


@pytest.mark.django_db
def test_redirect_user_uses_per_user_channel(captured):
    user = get_user_model().objects.create_user(username="alice", password="x")
    redirect_user(user, "/results/")
    assert len(captured) == 1
    assert captured[0][1] == {"url": "/results/"}


@pytest.mark.django_db
def test_redirect_object_uses_object_channel(captured):
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    redirect_object(obj, "/somewhere/")
    assert captured[0][0].startswith("testapp.thing-")
    assert captured[0][1] == {"url": "/somewhere/"}


def test_redirect_channel_uses_raw_channel(captured):
    redirect_channel("my-uid-123", "/x/")
    assert captured == [("my-uid-123", {"url": "/x/"})]


@override_settings(CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED=False)
@pytest.mark.django_db
def test_redirect_user_respects_auth_flag(captured):
    user = get_user_model().objects.create_user(username="alice", password="x")
    assert redirect_user(user, "/x/") is None
    assert captured == []


@override_settings(CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS=False)
@pytest.mark.django_db
def test_redirect_object_respects_page_channels_flag(captured):
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    assert redirect_object(obj, "/x/") is None
    assert captured == []


# ============================================================ progress


@pytest.mark.django_db
def test_progress_user_int_percent(captured):
    user = get_user_model().objects.create_user(username="alice", password="x")
    progress_user(user, 42)
    assert captured[0][1] == {"progress": True, "percent": "42%"}


@pytest.mark.django_db
def test_progress_user_string_with_percent_passes_through(captured):
    user = get_user_model().objects.create_user(username="alice", password="x")
    progress_user(user, "73%")
    assert captured[0][1] == {"progress": True, "percent": "73%"}


@pytest.mark.django_db
def test_progress_user_string_no_percent_gets_one(captured):
    user = get_user_model().objects.create_user(username="alice", password="x")
    progress_user(user, "100")
    assert captured[0][1] == {"progress": True, "percent": "100%"}


@pytest.mark.django_db
def test_progress_object_uses_object_channel(captured):
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    progress_object(obj, 50)
    assert captured[0][0].startswith("testapp.thing-")
    assert captured[0][1] == {"progress": True, "percent": "50%"}


def test_progress_channel_uses_raw_channel(captured):
    progress_channel("op-uid", 25)
    assert captured == [("op-uid", {"progress": True, "percent": "25%"})]


def test_progress_channel_float_percent(captured):
    progress_channel("op-uid", 33.5)
    assert captured[0][1] == {"progress": True, "percent": "33.5%"}


# -------- group gates


@override_settings(CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS=False)
def test_progress_channel_respects_page_channels_flag(captured):
    assert progress_channel("op-uid", 25) is None
    assert captured == []
