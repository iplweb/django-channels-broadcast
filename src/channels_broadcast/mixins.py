from channels_broadcast.core import convert_obj_to_channel_name


class ChannelSubscriberMixin:
    """View mixin that exposes a list of object-channel names to subscribe to.

    Add objects with :meth:`subscribe_to`; the resulting channel names are
    placed into the context under :attr:`channels_template_variable_name`
    (default: ``extraChannels``) so the frontend JS can pass them to the
    websocket via the ``?extraChannels=...`` query string.
    """

    _subscribed_to = None
    channels_template_variable_name = "extraChannels"

    def subscribe_to(self, obj):
        if self._subscribed_to is None:
            self._subscribed_to = []
        cn = convert_obj_to_channel_name(obj)
        self._subscribed_to.append(cn)
        return cn

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[self.channels_template_variable_name] = self._subscribed_to
        return context


class ChannelSubscriberSingleObjectMixin(ChannelSubscriberMixin):
    """ChannelSubscriberMixin variant for ``SingleObjectMixin`` views.

    Subscribes to whatever ``get_object()`` returns.
    """

    def get_object(self, *args, **kw):
        obj = super().get_object(*args, **kw)
        self.subscribe_to(obj)
        return obj
