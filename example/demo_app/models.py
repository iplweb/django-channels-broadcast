from django.db import models


class Thing(models.Model):
    """Throw-away demo object. Its (ContentType, pk) pair becomes a channel name."""

    name = models.CharField(max_length=64)

    def __str__(self):
        return self.name
