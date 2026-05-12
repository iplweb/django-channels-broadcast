"""Per-object subscription authorizer for the demo.

This is the function ``CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER``
points at. The consumer calls it once per channel in ``?extraChannels=``.

Policy implemented here:

- If the channel decodes to a ``demo_app.thing`` row, allow the
  subscription only if ``thing.owner_id == user.pk``.
- A Thing with no owner is treated as "public" — anyone may subscribe
  (so the demo works even before you create owned Things).
- Anything else (different model, malformed name): deny.

Pattern to replicate in a real project: parse the channel name with
``get_obj_from_channel_name``, then run whatever permission logic your
app uses (`user.has_perm`, ownership check, group membership, etc.).
"""

from channels_notifications import get_obj_from_channel_name


def authorize(user, channel_name):
    try:
        obj = get_obj_from_channel_name(channel_name)
    except Exception:
        return False

    if obj is None:
        return False

    if obj._meta.label_lower != "demo_app.thing":
        return False

    if obj.owner_id is None:
        return True  # public Things: anyone may subscribe

    if not getattr(user, "is_authenticated", False):
        return False
    return obj.owner_id == user.pk
