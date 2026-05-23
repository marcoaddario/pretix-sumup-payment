from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SumUpWebhookEvent",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "event_type",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=64
                    ),
                ),
                (
                    "event_id",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=255
                    ),
                ),
                (
                    "sumup_checkout_id",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=255
                    ),
                ),
                (
                    "sumup_transaction_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "pretix_order_code",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=16
                    ),
                ),
                (
                    "processing_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processed", "Processed"),
                            ("failed", "Failed"),
                            ("ignored", "Ignored"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                (
                    "error_message",
                    models.TextField(blank=True, default=""),
                ),
                (
                    "payload_json",
                    models.TextField(blank=True, default=""),
                ),
                (
                    "headers_json",
                    models.TextField(blank=True, default=""),
                ),
                (
                    "processed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
            ],
            options={
                "verbose_name": "SumUp webhook event",
                "verbose_name_plural": "SumUp webhook events",
                "ordering": ["-created_at"],
            },
        ),
    ]
