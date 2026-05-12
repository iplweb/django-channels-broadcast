from django.db import models

from channels_notifications import core
from channels_notifications.core import convert_obj_to_channel_name


class NotificationManager(models.Manager):
    def send_redirect(self, obj, url):
        res = self.create(
            channel_name=convert_obj_to_channel_name(obj), values={"url": url}
        )
        res.send()
        return res

    def unacknowledged(self):
        return self.filter(acknowledged=False)

    def on_connect(self, channels):
        """Replay unacknowledged notifications to a newly connected client."""
        for notification in self.unacknowledged().filter(channel_name__in=channels):
            notification.send()


class Notification(models.Model):
    channel_name = models.CharField(max_length=128, db_index=True)
    created_on = models.DateTimeField(auto_now_add=True)

    values = models.JSONField()

    acknowledged = models.BooleanField(default=False, db_index=True)

    objects = NotificationManager()

    class Meta:
        ordering = ("created_on",)

    def send(self):
        return core._send(self.channel_name, dict(id=self.pk, **self.values))

    def acknowledge(self):
        self.acknowledged = True
        self.save(update_fields=["acknowledged"])
