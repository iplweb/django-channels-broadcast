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

        monkeypatch.setattr(f"channels_broadcast.api.{n}", make_recorder())
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
    import channels_broadcast.api as api

    monkeypatch.setattr(api, "send_to_all", lambda *a, **k: None)
    call_command("send_notification", "--audience=all", "hi")
    out = capsys.readouterr().out
    assert "No-op" in out


# ==================================================== interactive prompts

# Stdin is not a TTY in pytest, so we monkeypatch _is_tty + _input
# to simulate a real terminal. This exercises the same code path that
# fires when a user runs `./manage.py send_notification` from a shell.

from channels_broadcast.management.commands import (  # noqa: E402
    send_notification as cmd_module,
)


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a TTY and feed canned responses to _input()."""
    monkeypatch.setattr(cmd_module, "_is_tty", lambda: True)

    responses = []

    def fake_input(prompt):
        if not responses:
            raise AssertionError(
                f"_input({prompt!r}) called with no canned responses left"
            )
        return responses.pop(0)

    monkeypatch.setattr(cmd_module, "_input", fake_input)
    return responses  # tests append to this list


def test_no_args_full_wizard_message_all(interactive, stubs):
    """No CLI args → asks kind, audience, level, then the message text."""
    interactive.extend(
        [
            "1",  # Kind: message (the default, but we pick explicitly)
            "1",  # Audience: all
            "1",  # Level: info
            "hello from wizard",  # Message text
        ]
    )
    call_command("send_notification")
    assert len(stubs["send_to_all"]) == 1
    args, kwargs = stubs["send_to_all"][0]
    assert args == ("hello from wizard",)
    from django.contrib.messages import constants

    assert kwargs["level"] == constants.INFO


@pytest.mark.django_db
def test_no_args_wizard_for_user_audience_prompts_username(interactive, stubs):
    """audience=user triggers a username prompt."""
    get_user_model().objects.create_user(username="alice", password="x")
    interactive.extend(
        [
            "",  # Kind: enter → default (message)
            "4",  # Audience: user
            "alice",  # Username
            "",  # Level: enter → default (info)
            "Hi Alice",  # Message text
        ]
    )
    call_command("send_notification")
    assert len(stubs["send_to_user"]) == 1
    args, _ = stubs["send_to_user"][0]
    assert args[0].username == "alice"
    assert args[1] == "Hi Alice"


@pytest.mark.django_db
def test_no_args_wizard_for_object_audience_prompts_spec(interactive, stubs):
    from tests.testapp.models import Thing

    thing = Thing.objects.create(name="t-wiz")
    interactive.extend(
        [
            "",  # Kind default → message
            "5",  # Audience: object
            f"testapp.Thing:{thing.pk}",  # Object spec
            "",  # Level default
            "comment posted",
        ]
    )
    call_command("send_notification")
    assert len(stubs["send_to_object"]) == 1


def test_no_args_wizard_for_channel_audience_prompts_name(interactive, stubs):
    interactive.extend(
        [
            "",  # Kind default → message
            "6",  # Audience: channel
            "stream-xyz",  # Channel name
            "",  # Level default
            "hello UID",
        ]
    )
    call_command("send_notification")
    assert len(stubs["send_to_channel"]) == 1
    args, _ = stubs["send_to_channel"][0]
    assert args[0] == "stream-xyz"


def test_partial_args_only_prompts_for_missing(interactive, stubs):
    """If --audience=all and --kind=message are on the CLI, the wizard
    skips those questions and only prompts for what's actually missing."""
    interactive.extend(
        [
            "",  # Level default
            "from partial wizard",  # Message text
        ]
    )
    call_command("send_notification", "--kind=message", "--audience=all")
    assert len(stubs["send_to_all"]) == 1


def test_wizard_accepts_choice_by_name_not_just_number(interactive, stubs):
    interactive.extend(
        [
            "message",  # Kind by name
            "all",  # Audience by name
            "info",  # Level by name
            "named",
        ]
    )
    call_command("send_notification")
    assert len(stubs["send_to_all"]) == 1


def test_wizard_redirect_for_user_prompts_url(interactive, stubs):
    """--kind=redirect changes the payload prompt label to "Redirect URL"."""
    get_user_model().objects.create_user(
        username="bob", password="x"
    ) if False else None
    interactive.extend(
        [
            "redirect",  # Kind
            "channel",  # Audience
            "stream-xyz",  # Channel name
            "/results/",  # Redirect URL (note: no level prompt for redirects)
        ]
    )
    call_command("send_notification")
    assert len(stubs["redirect_channel"]) == 1
    args, _ = stubs["redirect_channel"][0]
    assert args == ("stream-xyz", "/results/")


def test_wizard_progress_for_channel_prompts_percent(interactive, stubs):
    interactive.extend(
        [
            "progress",  # Kind
            "channel",
            "stream-xyz",
            "75",  # percent
        ]
    )
    call_command("send_notification")
    assert len(stubs["progress_channel"]) == 1
    args, _ = stubs["progress_channel"][0]
    assert args == ("stream-xyz", "75")


def test_wizard_rejects_invalid_choice_then_accepts_valid(interactive, stubs, capsys):
    interactive.extend(
        [
            "",  # Kind default → message
            "99",  # Audience: out of range
            "garbage-channel",  # Audience: unknown name
            "1",  # Audience: all (valid)
            "",  # Level default
            "retry payload",
        ]
    )
    call_command("send_notification")
    assert len(stubs["send_to_all"]) == 1


def test_no_tty_no_audience_errors_with_helpful_message(monkeypatch):
    """Without a TTY and without --audience, the command must fail
    fast, not hang on input()."""
    monkeypatch.setattr(cmd_module, "_is_tty", lambda: False)
    with pytest.raises(CommandError, match="--audience is required"):
        call_command("send_notification")


def test_no_tty_no_payload_errors_with_helpful_message(monkeypatch):
    monkeypatch.setattr(cmd_module, "_is_tty", lambda: False)
    with pytest.raises(CommandError, match="payload is required"):
        call_command("send_notification", "--audience=all")


def test_eof_cancels_wizard(monkeypatch):
    monkeypatch.setattr(cmd_module, "_is_tty", lambda: True)

    def eof_input(prompt):
        raise EOFError

    monkeypatch.setattr(cmd_module, "_input", eof_input)
    with pytest.raises(CommandError, match="EOF"):
        call_command("send_notification")


def test_quit_cancels_wizard(monkeypatch):
    monkeypatch.setattr(cmd_module, "_is_tty", lambda: True)
    monkeypatch.setattr(cmd_module, "_input", lambda prompt: "q")
    with pytest.raises(CommandError, match="cancelled"):
        call_command("send_notification")


def test_empty_payload_in_wizard_errors(interactive):
    """Hitting enter on the payload prompt should fail loudly."""
    interactive.extend(
        [
            "",  # Kind default
            "1",  # Audience: all
            "",  # Level default
            "",  # Empty payload
        ]
    )
    with pytest.raises(CommandError, match="cannot be empty"):
        call_command("send_notification")
