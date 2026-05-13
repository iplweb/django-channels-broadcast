import uuid

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView, TemplateView

from channels_broadcast import issue_subscription_token
from channels_broadcast.mixins import ChannelSubscriberSingleObjectMixin

from .models import Thing


class ThingList(ListView):
    model = Thing
    template_name = "demo_app/thing_list.html"


class ThingDetail(ChannelSubscriberSingleObjectMixin, DetailView):
    """Subscribes the page to `<app_label>.<model>-<pk>` automatically.

    The ``?extraChannels=`` request hits the consumer, which calls
    ``demo_app.security.authorize`` (configured in settings) — that
    enforces "only the Thing's owner may subscribe" for owned Things.
    """

    model = Thing
    template_name = "demo_app/thing_detail.html"


class UidStreamView(LoginRequiredMixin, TemplateView):
    """Demonstrates server-issued signed-token subscription.

    Generates a fresh UUID per page-load, signs a (user, [uuid]) token,
    and renders both into the page. The browser connects with
    ``?subscription_token=<token>`` — only the original user can use it,
    only for 5 minutes, no Redis required.

    A "fire" button kicks off a fake background task (here: just
    HttpResponseRedirect to itself) that pushes progress updates to
    the UID channel via ``progress_channel``.
    """

    template_name = "demo_app/uid_stream.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        stream_uid = f"stream-{uuid.uuid4().hex}"
        ctx["stream_uid"] = stream_uid
        ctx["subscription_token"] = issue_subscription_token(
            user=self.request.user,
            channels=[stream_uid],
            ttl=600,
        )
        return ctx
