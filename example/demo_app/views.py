from django.views.generic import DetailView, ListView

from channels_notifications.mixins import ChannelSubscriberSingleObjectMixin

from .models import Thing


class ThingList(ListView):
    model = Thing
    template_name = "demo_app/thing_list.html"


class ThingDetail(ChannelSubscriberSingleObjectMixin, DetailView):
    """Subscribes the page to `<app_label>.<model>-<pk>` automatically.

    The channel name is exposed in the template via `extraChannels` (a list
    produced by ChannelSubscriberMixin.get_context_data); the JS picks it
    up and hands it to the websocket in `?extraChannels=...`.
    """

    model = Thing
    template_name = "demo_app/thing_detail.html"
