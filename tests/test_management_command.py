"""Tests for the send_notification management command.

The command exposes all 14 distinct (kind, audience) combinations that
are valid in the API. Each test stubs the corresponding api.* function
and asserts the right one was dispatched with the right target.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command


@pytest.fixture
def stubs(monkeypatch):
    """Patch every send_to_*/redirect_*/progress_* function with a recorder.

    Returns a dict of {fn_name: list-of-(args, kwargs)}.
    """
    calls = {}
    names = [
        # messages
        "send_to_all",
        "send_to_authenticated",
        "send_to_anonymous",
        "send_to_user",
        "send_to_object",
        "send_to_channel",
        # redirects
        "redirect_user",
        "redirect_object",
        "redirect_channel",
        # progress
        "progress_user",
        "progress_object",
        "progress_channel",
    ]
    for n in names:
        calls[n] = []

        def make_recorder(_name=n):
            def recorder(*args, **kwargs):
                calls[_name].append((args, kwargs))
                return object()  # truthy sentinel — not a no-op

            return recorder

        monkeypatch.setattr(f"channels_notifications.api.{n}", make_recorder())
    return calls


# ==================================================== messages


def test_message_all(stubs):
    call_command("send_notification", "--audience=all", "hello")
    assert len(stubs["send_to_all"]) == 1
    assert stubs["send_to_all"][0][0] == ("hello",)


def test_message_authenticated(stubs):
    call_command("send_notification", "--audience=authenticated", "hi")
    assert len(stubs["send_to_authenticated"]) == 1


def test_message_anonymous(stubs):
    call_command("send_notification", "--audience=anonymous", "hi")
    assert len(stubs["send_to_anonymous"]) == 1


@pytest.mark.django_db
def test_message_user(stubs):
    get_user_model().objects.create_user(username="alice", password="x")
    call_command("send_notification", "--audience=user", "--username=alice", "hello")
    assert len(stubs["send_to_user"]) == 1
    args, _ = stubs["send_to_user"][0]
    assert args[0].username == "alice"
    assert args[1] == "hello"


@pytest.mark.django_db
def test_message_object(stubs):
    from tests.testapp.models import Thing

    thing = Thing.objects.create(name="t1")
    call_command(
        "send_notification",
        "--audience=object",
        f"--object=testapp.Thing:{thing.pk}",
        "to that thing",
    )
    assert len(stubs["send_to_object"]) == 1
    args, _ = stubs["send_to_object"][0]
    assert args[0] == thing
    assert args[1] == "to that thing"


def test_message_channel(stubs):
    call_command(
        "send_notification",
        "--audience=channel",
        "--channel=stream-abc-123",
        "raw text",
    )
    assert len(stubs["send_to_channel"]) == 1
    args, _ = stubs["send_to_channel"][0]
    assert args[0] == "stream-abc-123"
    assert args[1] == "raw text"


def test_message_level_translates_to_django_constant(stubs):
    from django.contrib.messages import constants

    call_command("send_notification", "--audience=all", "--level=warning", "careful")
    _, kwargs = stubs["send_to_all"][0]
    assert kwargs["level"] == constants.WARNING


# ==================================================== redirects


@pytest.mark.django_db
def test_redirect_user(stubs):
    get_user_model().objects.create_user(username="bob", password="x")
    call_command(
        "send_notification",
        "--kind=redirect",
        "--audience=user",
        "--username=bob",
        "/results/",
    )
    assert len(stubs["redirect_user"]) == 1
    args, _ = stubs["redirect_user"][0]
    assert args[1] == "/results/"


@pytest.mark.django_db
def test_redirect_object(stubs):
    from tests.testapp.models import Thing

    thing = Thing.objects.create(name="r1")
    call_command(
        "send_notification",
        "--kind=redirect",
        "--audience=object",
        f"--object=testapp.Thing:{thing.pk}",
        "/somewhere/",
    )
    assert len(stubs["redirect_object"]) == 1
    args, _ = stubs["redirect_object"][0]
    assert args[0] == thing
    assert args[1] == "/somewhere/"


def test_redirect_channel(stubs):
    call_command(
        "send_notification",
        "--kind=redirect",
        "--audience=channel",
        "--channel=op-42",
        "/results/",
    )
    assert len(stubs["redirect_channel"]) == 1
    args, _ = stubs["redirect_channel"][0]
    assert args == ("op-42", "/results/")


# ==================================================== progress


@pytest.mark.django_db
def test_progress_user(stubs):
    get_user_model().objects.create_user(username="carol", password="x")
    call_command(
        "send_notification",
        "--kind=progress",
        "--audience=user",
        "--username=carol",
        "42",
    )
    assert len(stubs["progress_user"]) == 1
    args, _ = stubs["progress_user"][0]
    assert args[1] == "42"  # string, no coercion at CLI layer


@pytest.mark.django_db
def test_progress_object(stubs):
    from tests.testapp.models import Thing

    thing = Thing.objects.create(name="p1")
    call_command(
        "send_notification",
        "--kind=progress",
        "--audience=object",
        f"--object=testapp.Thing:{thing.pk}",
        "75",
    )
    assert len(stubs["progress_object"]) == 1


def test_progress_channel(stubs):
    call_command(
        "send_notification",
        "--kind=progress",
        "--audience=channel",
        "--channel=op-42",
        "100%",
    )
    assert len(stubs["progress_channel"]) == 1
    args, _ = stubs["progress_channel"][0]
    assert args == ("op-42", "100%")


# ==================================================== rejected combinations


def test_redirect_to_all_is_rejected():
    """Redirects need a specific recipient — can't broadcast a redirect."""
    with pytest.raises(CommandError, match="not supported for --audience=all"):
        call_command("send_notification", "--kind=redirect", "--audience=all", "/x/")


def test_progress_to_authenticated_is_rejected():
    with pytest.raises(CommandError):
        call_command(
            "send_notification",
            "--kind=progress",
            "--audience=authenticated",
            "50",
        )


def test_user_audience_without_username_errors():
    with pytest.raises(CommandError, match="--username is required"):
        call_command("send_notification", "--audience=user", "hi")


def test_object_audience_without_object_errors():
    with pytest.raises(CommandError, match="--object is required"):
        call_command("send_notification", "--audience=object", "hi")


def test_channel_audience_without_channel_errors():
    with pytest.raises(CommandError, match="--channel is required"):
        call_command("send_notification", "--audience=channel", "hi")


def test_object_with_bad_format_errors():
    with pytest.raises(CommandError, match="must look like"):
        call_command(
            "send_notification",
            "--audience=object",
            "--object=notvalid",
            "hi",
        )


def test_object_with_unknown_model_errors():
    with pytest.raises(CommandError, match="unknown model"):
        call_command(
            "send_notification",
            "--audience=object",
            "--object=nosuch.Nope:1",
            "hi",
        )


@pytest.mark.django_db
def test_object_with_missing_pk_errors():
    with pytest.raises(CommandError, match="does not exist"):
        call_command(
            "send_notification",
            "--audience=object",
            "--object=testapp.Thing:9999999",
            "hi",
        )


@pytest.mark.django_db
def test_user_with_unknown_username_errors():
    with pytest.raises(CommandError, match="does not exist"):
        call_command(
            "send_notification",
            "--audience=user",
            "--username=nobody",
            "hi",
        )


# ==================================================== noop reporting


def test_noop_returns_warning_on_disabled_flag(monkeypatch, capsys):
    """If an ENABLE_* flag is off, the API returns None — command should say so."""
    import channels_notifications.api as api

    monkeypatch.setattr(api, "send_to_all", lambda *a, **k: None)
    call_command("send_notification", "--audience=all", "hi")
    out = capsys.readouterr().out
    assert "No-op" in out
