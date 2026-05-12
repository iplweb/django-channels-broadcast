from django.contrib.auth import get_user_model
from django.contrib.messages import constants as message_constants
from django.core.management import BaseCommand

from channels_notifications import api


class Command(BaseCommand):
    help = "Send a realtime notification via django-channels"

    def add_arguments(self, parser):
        parser.add_argument(
            "--audience",
            choices=["all", "authenticated", "anonymous", "user"],
            required=True,
            help="Audience to deliver the message to.",
        )
        parser.add_argument(
            "--username",
            help="Required when --audience=user.",
        )
        parser.add_argument(
            "--level",
            choices=["info", "success", "warning", "error"],
            default="info",
        )
        parser.add_argument("text")

    def handle(self, *args, **options):
        text = options["text"]
        level = {
            "info": message_constants.INFO,
            "success": message_constants.SUCCESS,
            "warning": message_constants.WARNING,
            "error": message_constants.ERROR,
        }[options["level"]]
        audience = options["audience"]

        if audience == "all":
            api.send_to_all(text, level=level)
        elif audience == "authenticated":
            api.send_to_authenticated(text, level=level)
        elif audience == "anonymous":
            api.send_to_anonymous(text, level=level)
        elif audience == "user":
            username = options["username"]
            if not username:
                self.stderr.write("--username is required when --audience=user")
                return
            user = get_user_model().objects.get(username=username)
            api.send_to_user(user, text, level=level)
