import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.fixture
def captured(monkeypatch):
    calls = []
    for name in (
        "send_to_all",
        "send_to_authenticated",
        "send_to_anonymous",
        "send_to_user",
    ):
        monkeypatch.setattr(
            f"channels_notifications.api.{name}",
            lambda *args, _n=name, **kw: calls.append((_n, args, kw)),
        )
    return calls


def test_command_audience_all(captured):
    call_command("send_notification", "--audience", "all", "hello")
    assert captured[0][0] == "send_to_all"
    assert captured[0][1][0] == "hello"


def test_command_audience_authenticated(captured):
    call_command("send_notification", "--audience", "authenticated", "hello")
    assert captured[0][0] == "send_to_authenticated"


def test_command_audience_anonymous(captured):
    call_command("send_notification", "--audience", "anonymous", "hello")
    assert captured[0][0] == "send_to_anonymous"


@pytest.mark.django_db
def test_command_audience_user(captured):
    get_user_model().objects.create_user(username="alice", password="x")
    call_command(
        "send_notification",
        "--audience",
        "user",
        "--username",
        "alice",
        "hello",
    )
    assert captured[0][0] == "send_to_user"
    user = captured[0][1][0]
    assert user.username == "alice"
