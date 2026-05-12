from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from channels_notifications import (
    send_to_all,
    send_to_anonymous,
    send_to_authenticated,
    send_to_user,
)


def home(request):
    return render(request, "home.html")


@require_POST
def send(request):
    audience = request.POST.get("audience", "all")
    text = request.POST.get("text", "(no text)")
    level = request.POST.get("level", "info")

    if audience == "all":
        send_to_all(text, level=level)
    elif audience == "authenticated":
        send_to_authenticated(text, level=level)
    elif audience == "anonymous":
        send_to_anonymous(text, level=level)
    elif audience == "user":
        username = request.POST.get("username")
        if username:
            try:
                user = get_user_model().objects.get(username=username)
            except get_user_model().DoesNotExist:
                pass
            else:
                send_to_user(user, text, level=level)

    return HttpResponseRedirect(reverse("home"))
