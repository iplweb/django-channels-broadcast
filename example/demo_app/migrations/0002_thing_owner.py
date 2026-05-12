from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("demo_app", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="thing",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Only this user is allowed to subscribe to this Thing's channel."
                ),
                null=True,
                on_delete=models.CASCADE,
                related_name="things",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
