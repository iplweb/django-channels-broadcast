def test_app_imports():
    import channels_broadcast

    assert channels_broadcast


def test_appconfig_loads():
    from django.apps import apps

    config = apps.get_app_config("channels_broadcast")
    assert config.name == "channels_broadcast"
    assert config.label == "channels_broadcast"


def test_public_api_surface():
    """Make sure the documented top-level names are importable."""
    from channels_broadcast import (
        send_to_all,
        send_to_anonymous,
        send_to_authenticated,
        send_to_object,
        send_to_user,
    )

    assert callable(send_to_all)
    assert callable(send_to_anonymous)
    assert callable(send_to_authenticated)
    assert callable(send_to_object)
    assert callable(send_to_user)
