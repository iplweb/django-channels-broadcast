import pytest
from model_bakery import baker

from channels_notifications.core import (
    convert_obj_to_channel_name,
    get_obj_from_channel_name,
)


@pytest.mark.django_db
def test_convert_obj_to_channel_name():
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    name = convert_obj_to_channel_name(obj)
    assert name.startswith("testapp.thing-")
    assert name.endswith(str(obj.pk))


@pytest.mark.django_db
def test_get_obj_from_channel_name_roundtrip():
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    name = convert_obj_to_channel_name(obj)
    assert get_obj_from_channel_name(name) == obj
