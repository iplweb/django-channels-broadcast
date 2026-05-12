import pytest
from django.test import override_settings

from channels_notifications import settings as cn_settings


def test_defaults_match_documented_baseline():
    assert cn_settings.DEFAULTS == {
        "CHANNELS_NOTIFICATIONS_ENABLE_ALL": True,
        "CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED": True,
        "CHANNELS_NOTIFICATIONS_ENABLE_ANONYMOUS": False,
        "CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS": True,
    }


@pytest.mark.parametrize(
    "setting,getter",
    [
        ("CHANNELS_NOTIFICATIONS_ENABLE_ALL", cn_settings.is_all_enabled),
        (
            "CHANNELS_NOTIFICATIONS_ENABLE_AUTHENTICATED",
            cn_settings.is_authenticated_enabled,
        ),
        (
            "CHANNELS_NOTIFICATIONS_ENABLE_ANONYMOUS",
            cn_settings.is_anonymous_enabled,
        ),
        (
            "CHANNELS_NOTIFICATIONS_ENABLE_PAGE_CHANNELS",
            cn_settings.is_page_channels_enabled,
        ),
    ],
)
def test_flags_react_to_override(setting, getter):
    with override_settings(**{setting: True}):
        assert getter() is True
    with override_settings(**{setting: False}):
        assert getter() is False


def test_anonymous_disabled_by_default():
    assert cn_settings.is_anonymous_enabled() is False
