import pytest
from model_bakery import baker

from channels_notifications.models import Notification


@pytest.mark.django_db
def test_notification_send_redirect(monkeypatch):
    """``send_redirect`` creates a Notification row and dispatches to the layer."""
    from tests.testapp.models import Thing

    calls = []
    monkeypatch.setattr(
        "channels_notifications.models.core._send",
        lambda channel, data: calls.append((channel, data)),
    )

    obj = baker.make(Thing)
    Notification.objects.send_redirect(obj, "http://example.com/")

    assert Notification.objects.count() == 1
    n = Notification.objects.get()
    assert n.channel_name.startswith("testapp.thing-")
    assert n.values == {"url": "http://example.com/"}
    assert calls == [(n.channel_name, {"id": n.pk, "url": "http://example.com/"})]


@pytest.mark.django_db
def test_acknowledge_flips_flag():
    n = Notification.objects.create(channel_name="x", values={})
    assert n.acknowledged is False
    n.acknowledge()
    n.refresh_from_db()
    assert n.acknowledged is True


@pytest.mark.django_db
def test_unacknowledged_manager_filters():
    Notification.objects.create(channel_name="x", values={})
    Notification.objects.create(channel_name="x", values={}, acknowledged=True)
    assert Notification.objects.unacknowledged().count() == 1


@pytest.mark.django_db
def test_on_connect_replays_unacknowledged(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "channels_notifications.models.core._send",
        lambda channel, data: sent.append((channel, data)),
    )

    Notification.objects.create(channel_name="ch", values={"a": 1})
    Notification.objects.create(channel_name="ch", values={"a": 2}, acknowledged=True)
    Notification.objects.on_connect(["ch"])

    assert len(sent) == 1
    assert sent[0][1]["a"] == 1
