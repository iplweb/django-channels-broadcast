"""End-to-end audience tests driving the full ASGI stack.

For each gate flag, we open a ``WebsocketCommunicator`` against the test
ASGI application and then broadcast a message to the relevant group via
the channel layer. Whether the message reaches the websocket tells us
whether the consumer joined that group — no introspection of consumer
internals required.
"""

import asyncio

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import override_settings

from channels_broadcast import settings as cn_settings

pytestmark = pytest.mark.django_db(transaction=True)


async def _open_ws(user):
    from tests.asgi import application

    comm = WebsocketCommunicator(application, "/asgi/notifications/")
    comm.scope["user"] = user
    return comm


async def _broadcast(group, payload):
    layer = get_channel_layer()
    await layer.group_send(group, {"type": "chat_message", **payload})


async def _ws_received(comm, timeout=0.3):
    """Return parsed JSON if a frame arrives within timeout, else None."""
    try:
        return await asyncio.wait_for(comm.receive_json_from(), timeout=timeout)
    except (asyncio.TimeoutError, TimeoutError):
        return None


@pytest.fixture
def authed_user(db):
    return get_user_model().objects.create_user(username="bob", password="x")


@pytest.fixture
def anonymous_user():
    from django.contrib.auth.models import AnonymousUser

    return AnonymousUser()


# -------------------------------------------------- anonymous gating


@override_settings(CHANNELS_BROADCAST_ENABLE_ANONYMOUS=False)
async def test_anonymous_connection_rejected_when_flag_off(anonymous_user):
    comm = await _open_ws(anonymous_user)
    connected, _ = await comm.connect()
    assert connected is False, "consumer must close anonymous connections"


@override_settings(
    CHANNELS_BROADCAST_ENABLE_ANONYMOUS=True,
    CHANNELS_BROADCAST_ENABLE_ALL=False,
)
async def test_anonymous_receives_anonymous_group_when_enabled(anonymous_user):
    comm = await _open_ws(anonymous_user)
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast(cn_settings.GROUP_ANONYMOUS, {"text": "hi anon"})
    msg = await _ws_received(comm)
    assert msg is not None
    assert msg["text"] == "hi anon"
    await comm.disconnect()


# ---------------------------------------------- authenticated routing


@override_settings(CHANNELS_BROADCAST_ENABLE_ALL=False)
async def test_authenticated_user_receives_auth_group(authed_user):
    comm = await _open_ws(authed_user)
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast(cn_settings.GROUP_AUTHENTICATED, {"text": "hi auth"})
    msg = await _ws_received(comm)
    assert msg is not None and msg["text"] == "hi auth"
    await comm.disconnect()


@override_settings(
    CHANNELS_BROADCAST_ENABLE_AUTHENTICATED=False,
    CHANNELS_BROADCAST_ENABLE_ALL=False,
)
async def test_authenticated_user_skips_auth_group_when_flag_off(authed_user):
    comm = await _open_ws(authed_user)
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast(cn_settings.GROUP_AUTHENTICATED, {"text": "should not arrive"})
    msg = await _ws_received(comm)
    assert msg is None, "user joined auth group despite flag being off"
    await comm.disconnect()


# ---------------------------------------------------------- all-group


async def test_authenticated_user_receives_all_group(authed_user):
    comm = await _open_ws(authed_user)
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast(cn_settings.GROUP_ALL, {"text": "to everyone"})
    msg = await _ws_received(comm)
    assert msg is not None and msg["text"] == "to everyone"
    await comm.disconnect()


@override_settings(CHANNELS_BROADCAST_ENABLE_ALL=False)
async def test_all_group_not_joined_when_flag_off(authed_user):
    comm = await _open_ws(authed_user)
    connected, _ = await comm.connect()
    assert connected is True
    await _broadcast(cn_settings.GROUP_ALL, {"text": "should not arrive"})
    msg = await _ws_received(comm)
    assert msg is None
    await comm.disconnect()


# -------------------------------------------------- per-user channel


async def test_user_receives_per_user_channel(authed_user):
    """A direct send_to_user message reaches this exact user only."""
    from channels_broadcast.core import get_channel_name_for_user

    comm = await _open_ws(authed_user)
    connected, _ = await comm.connect()
    assert connected is True
    # Drain any startup frames (none expected here, but be safe).
    await _ws_received(comm, timeout=0.05)
    channel = get_channel_name_for_user(authed_user)
    await _broadcast(channel, {"text": "private"})
    msg = await _ws_received(comm)
    assert msg is not None and msg["text"] == "private"
    await comm.disconnect()
