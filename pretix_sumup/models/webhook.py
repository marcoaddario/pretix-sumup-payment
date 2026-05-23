import json

from django.db import models
from django.utils.translation import gettext_lazy as _


class SumUpWebhookEvent(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        PROCESSED = "processed", _("Processed")
        FAILED = "failed", _("Failed")
        IGNORED = "ignored", _("Ignored")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    event_id = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    sumup_checkout_id = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    sumup_transaction_id = models.CharField(
        max_length=255, blank=True, default=""
    )
    pretix_order_code = models.CharField(
        max_length=16, blank=True, default="", db_index=True
    )
    processing_status = models.CharField(
        max_length=16,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True, default="")
    payload_json = models.TextField(blank=True, default="")
    headers_json = models.TextField(blank=True, default="")
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "pretix_sumup"
        verbose_name = _("SumUp webhook event")
        verbose_name_plural = _("SumUp webhook events")
        ordering = ["-created_at"]

    def __str__(self):
        return f"SumUp webhook {self.event_id or self.pk} ({self.processing_status})"

    def get_payload(self):
        try:
            return json.loads(self.payload_json) if self.payload_json else {}
        except (json.JSONDecodeError, ValueError):
            return {}

    def get_headers(self):
        try:
            return json.loads(self.headers_json) if self.headers_json else {}
        except (json.JSONDecodeError, ValueError):
            return {}
