"""Tests for the subscription-authorization layer.

Covers:
  - default-deny behaviour of authorize_extra_channel
  - settings-pluggable authorizer
  - issue_subscription_token + verify_subscription_token round-trip
  - tampered tokens, expired tokens, user mismatch
"""

import json
from base64 import urlsafe_b64encode

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.signing import TimestampSigner
from django.test import override_settings

from channels_notifications.security import (
    _SIGNING_SALT,
    DEFAULT_TOKEN_TTL_SECONDS,
    authorize_extra_channel,
    issue_subscription_token,
    verify_subscription_token,
)

# --------------------------------------------------- authorizer hook


def test_default_authorizer_denies_everything():
    assert authorize_extra_channel(AnonymousUser(), "anything") is False


def _allow_all(user, channel_name):
    return True


def _allow_starts_with_x(user, channel_name):
    return channel_name.startswith("x.")


@override_settings(
    CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER=("tests.test_security._allow_all")
)
def test_custom_authorizer_can_permit():
    assert authorize_extra_channel(AnonymousUser(), "anything") is True


@override_settings(
    CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER=(
        "tests.test_security._allow_starts_with_x"
    )
)
def test_custom_authorizer_can_partially_permit():
    assert authorize_extra_channel(AnonymousUser(), "x.allowed") is True
    assert authorize_extra_channel(AnonymousUser(), "y.denied") is False


# ----------------------------------------- token round-trip (positive)


@pytest.mark.django_db
def test_token_roundtrip_authenticated_user():
    user = get_user_model().objects.create_user(username="alice", password="x")
    token = issue_subscription_token(user, ["op-1", "op-2"])
    assert verify_subscription_token(token, user) == ["op-1", "op-2"]


def test_token_roundtrip_anonymous_user():
    anon = AnonymousUser()
    token = issue_subscription_token(anon, ["uid-1"])
    assert verify_subscription_token(token, anon) == ["uid-1"]


def test_token_with_none_user_works_for_anonymous():
    """user=None should be equivalent to anonymous (both map to u=None)."""
    token = issue_subscription_token(None, ["uid-1"])
    assert verify_subscription_token(token, AnonymousUser()) == ["uid-1"]


# ----------------------------------------- token verification (negative)


def test_empty_token_returns_empty():
    assert verify_subscription_token("", AnonymousUser()) == []
    assert verify_subscription_token(None, AnonymousUser()) == []


def test_garbage_token_returns_empty():
    assert verify_subscription_token("not-a-real-token", AnonymousUser()) == []


def test_tampered_signature_returns_empty():
    token = issue_subscription_token(None, ["uid-1"])
    # Flip last char of the signature segment
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert verify_subscription_token(tampered, AnonymousUser()) == []


def test_tampered_payload_returns_empty():
    """If the JSON itself is rewritten in the signed segment, the
    signature won't match anymore."""
    token = issue_subscription_token(None, ["uid-1"])
    # Replace the payload — signature was for old payload
    bad_payload = (
        urlsafe_b64encode(json.dumps({"u": None, "c": ["uid-EVIL"], "t": 300}).encode())
        .rstrip(b"=")
        .decode()
    )
    parts = token.split(":")
    tampered = ":".join([bad_payload] + parts[1:])
    assert verify_subscription_token(tampered, AnonymousUser()) == []


@pytest.mark.django_db
def test_user_mismatch_returns_empty():
    alice = get_user_model().objects.create_user(username="alice", password="x")
    bob = get_user_model().objects.create_user(username="bob", password="x")
    token = issue_subscription_token(alice, ["op-1"])
    assert verify_subscription_token(token, bob) == []


@pytest.mark.django_db
def test_token_issued_to_user_rejected_for_anonymous():
    alice = get_user_model().objects.create_user(username="alice", password="x")
    token = issue_subscription_token(alice, ["op-1"])
    assert verify_subscription_token(token, AnonymousUser()) == []


def test_token_issued_anonymous_rejected_for_authenticated_user(db):
    alice = get_user_model().objects.create_user(username="alice", password="x")
    token = issue_subscription_token(None, ["uid-1"])
    assert verify_subscription_token(token, alice) == []


# ----------------------------------------- token expiry


def test_token_default_ttl_is_5_minutes():
    """Sanity: caller doesn't have to remember the number."""
    assert DEFAULT_TOKEN_TTL_SECONDS == 300


def test_token_past_ttl_is_rejected(monkeypatch):
    token = issue_subscription_token(None, ["uid-1"], ttl=1)
    # Force the verifier to think 5 s elapsed since signing.
    original_unsign = TimestampSigner.unsign

    def aged_unsign(self, value, **kw):
        if "max_age" in kw and kw["max_age"] is not None:
            kw["max_age"] = 0  # already expired
        return original_unsign(self, value, **kw)

    monkeypatch.setattr(TimestampSigner, "unsign", aged_unsign)
    assert verify_subscription_token(token, AnonymousUser()) == []


def test_token_with_zero_ttl_payload_is_rejected():
    """Defense in depth: a token whose own embedded TTL is <=0 is junk."""
    payload = json.dumps({"u": None, "c": ["uid-1"], "t": 0})
    token = TimestampSigner(salt=_SIGNING_SALT).sign(payload)
    assert verify_subscription_token(token, AnonymousUser()) == []


def test_token_with_nonlist_channels_is_rejected():
    payload = json.dumps({"u": None, "c": "uid-1", "t": 300})
    token = TimestampSigner(salt=_SIGNING_SALT).sign(payload)
    assert verify_subscription_token(token, AnonymousUser()) == []


def test_token_payload_not_a_dict_is_rejected():
    token = TimestampSigner(salt=_SIGNING_SALT).sign(json.dumps(["not", "a", "dict"]))
    assert verify_subscription_token(token, AnonymousUser()) == []
