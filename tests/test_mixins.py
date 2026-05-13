import pytest
from model_bakery import baker

from channels_broadcast.mixins import (
    ChannelSubscriberMixin,
    ChannelSubscriberSingleObjectMixin,
)


@pytest.mark.django_db
def test_subscribe_to_appends_channel_name():
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    x = ChannelSubscriberMixin()
    cn = x.subscribe_to(obj)
    assert cn.startswith("testapp.thing-")
    assert x._subscribed_to == [cn]


def test_get_context_data_emits_extra_channels_key():
    class Base:
        def get_context_data(self):
            return {"a": "B"}

    class Mixed(ChannelSubscriberMixin, Base):
        pass

    res = Mixed().get_context_data()
    assert "extraChannels" in res


@pytest.mark.django_db
def test_single_object_mixin_subscribes_on_get_object():
    from tests.testapp.models import Thing

    obj = baker.make(Thing)

    class Base:
        def get_object(self):
            return obj

    class Mixed(ChannelSubscriberSingleObjectMixin, Base):
        pass

    view = Mixed()
    assert view.get_object() == obj
    assert len(view._subscribed_to) == 1
