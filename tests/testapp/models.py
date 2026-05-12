from django.db import models


class Thing(models.Model):
    """Generic test object used by tests that need a content-type-bearing model."""

    name = models.CharField(max_length=64, default="")
