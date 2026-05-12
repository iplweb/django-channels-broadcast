from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("channel_name", models.CharField(db_index=True, max_length=128)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("values", models.JSONField()),
                (
                    "acknowledged",
                    models.BooleanField(db_index=True, default=False),
                ),
            ],
            options={
                "ordering": ("created_on",),
            },
        ),
    ]
