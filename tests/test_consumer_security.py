"""End-to-end tests for the subscription-security layer in the consumer.

Verifies:
  - ?extraChannels= is denied by default (no authorizer configured)
  - ?extraChannels= entries pass through the authorizer when configured
  - ?subscription_token= valid token subscribes to the embedded channels
  - ?subscription_token= invalid/tampered/user-mismatch token is ignored
"""

import asyncio
import json

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import override_settings

from channels_broadcast.security import issue_subscription_token

pytestmark = pytest.mark.django_db(transaction=True)


def _ws_url(extras=None, token=None):
    path = "/asgi/notifications/"
    parts = []
    if extras is not None:
        parts.append("extraChannels=" + json.dumps(extras))
    if token is not None:
        parts.append("subscription_token=" + token)
    if parts:
        path += "?" + "&".join(parts)
    return path


async def _open_ws(user, *, extras=None, token=None):
    from tests.asgi import application

    comm = WebsocketCommunicator(application, _ws_url(extras=extras, token=token))
    comm.scope["user"] = user
    return comm


async def _broadcast(channel, payload):
    layer = get_channel_layer()
    await layer.group_send(channel, {"type": "chat_message", **payload})


async def _received(comm, timeout=0.3):
    try:
        return await asyncio.wait_for(comm.receive_json_from(), timeout=timeout)
    except (asyncio.TimeoutError, TimeoutError):
        return None


@pytest.fixture
def alice(db):
    return get_user_model().objects.create_user(username="alice", password="x")


@pytest.fixture
def bob(db):
    return get_user_model().objects.create_user(username="bob", password="x")


# ==================================================== authorizer hook


async def test_default_denies_extra_channels(alice):
    """No authorizer configured → ?extraChannels= silently dropped."""
    comm = await _open_ws(alice, extras=["secret-channel"])
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast("secret-channel", {"text": "should not arrive"})
    assert await _received(comm) is None
    await comm.disconnect()


def _allow_all(user, channel_name):
    return True


def _deny_all(user, channel_name):
    return False


def _only_owned(user, channel_name):
    """Only allow channels prefixed with the user's username."""
    if not getattr(user, "is_authenticated", False):
        return False
    return channel_name.startswith(f"{user.username}.")


@override_settings(
    CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER=(
        "tests.test_consumer_security._allow_all"
    )
)
async def test_permissive_authorizer_lets_through(alice):
    comm = await _open_ws(alice, extras=["arbitrary-channel"])
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast("arbitrary-channel", {"text": "hello"})
    msg = await _received(comm)
    assert msg is not None and msg["text"] == "hello"
    await comm.disconnect()


@override_settings(
    CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER=(
        "tests.test_consumer_security._only_owned"
    )
)
async def test_authorizer_can_partial_deny(alice):
    """Some channels permitted, others not — denied ones produce no traffic."""
    comm = await _open_ws(alice, extras=["alice.ok", "bob.denied"])
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast("alice.ok", {"text": "got it"})
    await _broadcast("bob.denied", {"text": "should not arrive"})
    received = []
    while True:
        msg = await _received(comm, timeout=0.15)
        if msg is None:
            break
        received.append(msg)
    assert any(m["text"] == "got it" for m in received)
    assert not any(m["text"] == "should not arrive" for m in received)
    await comm.disconnect()


# ============================================== signed subscription tokens


async def test_valid_token_subscribes_to_channels(alice):
    token = issue_subscription_token(alice, ["op-uid-1"])
    comm = await _open_ws(alice, token=token)
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast("op-uid-1", {"text": "tokenized"})
    msg = await _received(comm)
    assert msg is not None and msg["text"] == "tokenized"
    await comm.disconnect()


async def test_token_bypasses_authorizer(alice):
    """Token-authorized channels join even when the default-deny authorizer is active."""
    token = issue_subscription_token(alice, ["op-uid-2"])
    comm = await _open_ws(alice, token=token)
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast("op-uid-2", {"text": "tokenized"})
    msg = await _received(comm)
    assert msg is not None
    await comm.disconnect()


async def test_token_issued_to_other_user_is_ignored(alice, bob):
    """A token signed for alice MUST NOT subscribe bob — even though both
    are valid users and the signature checks out."""
    token = issue_subscription_token(alice, ["op-uid-3"])
    comm = await _open_ws(bob, token=token)
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast("op-uid-3", {"text": "should not arrive"})
    assert await _received(comm) is None
    await comm.disconnect()


async def test_tampered_token_is_ignored(alice):
    token = issue_subscription_token(alice, ["op-uid-4"])
    bad = token[:-1] + ("A" if token[-1] != "A" else "B")
    comm = await _open_ws(alice, token=bad)
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast("op-uid-4", {"text": "should not arrive"})
    assert await _received(comm) is None
    await comm.disconnect()


async def test_extra_channels_and_token_combine(alice):
    """Authorizer permits ext_*, token permits tok_*. Both should subscribe."""
    token = issue_subscription_token(alice, ["tok_only"])

    def _ext_prefix_allowed(user, ch):
        return ch.startswith("ext_")

    with override_settings(
        CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER=(
            "tests.test_consumer_security._allow_ext"
        )
    ):
        comm = await _open_ws(alice, extras=["ext_a"], token=token)
        connected, _ = await comm.connect()
        assert connected is True
        await _broadcast("ext_a", {"text": "from-extra"})
        await _broadcast("tok_only", {"text": "from-token"})
        seen = []
        while True:
            msg = await _received(comm, timeout=0.2)
            if msg is None:
                break
            seen.append(msg["text"])
        assert "from-extra" in seen
        assert "from-token" in seen
        await comm.disconnect()


def _allow_ext(user, channel_name):
    return channel_name.startswith("ext_")
