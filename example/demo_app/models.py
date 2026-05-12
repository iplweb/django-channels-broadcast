from django.conf import settings
from django.db import models


class Thing(models.Model):
    """Throw-away demo object. Its (ContentType, pk) pair becomes a channel name.

    Has an ``owner`` field so the authorizer below can demonstrate
    per-object permission checks.
    """

    name = models.CharField(max_length=64)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="things",
        help_text="Only this user is allowed to subscribe to this Thing's channel.",
    )

    def __str__(self):
        return self.name
