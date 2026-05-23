import json
import logging

from django.utils import timezone

from pretix_sumup.api.client import SumUpClient
from pretix_sumup.models.webhook import SumUpWebhookEvent
from pretix_sumup.utils.logging import (
    log_webhook_failed,
    log_webhook_processed,
    log_webhook_received,
)

logger = logging.getLogger("pretix.plugins.sumup.webhooks")


def record_webhook_event(request):
    """Record an incoming webhook payload."""
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    headers = dict(request.headers)
    headers.pop("Authorization", None)

    event_id = payload.get("event_id", "")
    event_type = payload.get("event_type", "")
    checkout_id = (
        payload.get("checkout_id")
        or payload.get("payload", {}).get("checkout_id", "")
    )
    transaction_id = (
        payload.get("transaction_id")
        or payload.get("payload", {}).get("transaction_id", "")
    )

    log_webhook_received(logger, event_id, event_type, checkout_id)

    event = SumUpWebhookEvent.objects.create(
        event_type=event_type,
        event_id=event_id,
        sumup_checkout_id=checkout_id,
        sumup_transaction_id=transaction_id,
        payload_json=json.dumps(payload),
        headers_json=json.dumps(headers),
        processing_status=SumUpWebhookEvent.ProcessingStatus.PENDING,
    )

    return event


def _check_idempotency(event):
    """Check if this event should be processed or ignored."""
    if not event.event_id:
        return False

    existing = (
        SumUpWebhookEvent.objects.filter(event_id=event.event_id)
        .exclude(pk=event.pk)
        .first()
    )
    if existing:
        if existing.processing_status in (
            SumUpWebhookEvent.ProcessingStatus.PROCESSED,
            SumUpWebhookEvent.ProcessingStatus.IGNORED,
        ):
            event.processing_status = SumUpWebhookEvent.ProcessingStatus.IGNORED
            event.error_message = (
                f"Duplicate event_id {event.event_id} already "
                f"{existing.processing_status}"
            )
            event.save(update_fields=["processing_status", "error_message"])
            log_webhook_processed(logger, event.pk, "ignored (duplicate event_id)")
            return True

    return False


def _check_transaction_already_linked(payment):
    """Check if the transaction is already linked to a confirmed payment."""
    if payment and payment.state == "confirmed" and payment.info_data.get("sumup_transaction"):
        return True
    return False


def process_webhook_event(event):
    """Process a recorded webhook event."""
    from pretix.base.models import OrderPayment

    event.refresh_from_db()

    if event.processing_status in (
        SumUpWebhookEvent.ProcessingStatus.PROCESSED,
        SumUpWebhookEvent.ProcessingStatus.IGNORED,
    ):
        return

    if _check_idempotency(event):
        return

    payload = event.get_payload()
    checkout_id = event.sumup_checkout_id
    if not checkout_id:
        checkout_id = payload.get("checkout_id") or payload.get("payload", {}).get(
            "checkout_id", ""
        )

    if not checkout_id:
        event.processing_status = SumUpWebhookEvent.ProcessingStatus.FAILED
        event.error_message = "No checkout_id in webhook payload"
        event.save(update_fields=["processing_status", "error_message"])
        log_webhook_failed(logger, event.pk, event.error_message)
        return

    try:
        payment = OrderPayment.objects.filter(
            info__contains=checkout_id
        ).first()

        if not payment:
            event.processing_status = SumUpWebhookEvent.ProcessingStatus.IGNORED
            event.error_message = f"No Pretix payment found for checkout {checkout_id}"
            event.save(update_fields=["processing_status", "error_message"])
            log_webhook_processed(
                logger, event.pk, "ignored (no matching payment)"
            )
            return

        if _check_transaction_already_linked(payment):
            event.processing_status = SumUpWebhookEvent.ProcessingStatus.IGNORED
            event.error_message = (
                f"Transaction already processed for payment {payment.pk}"
            )
            event.save(update_fields=["processing_status", "error_message"])
            log_webhook_processed(
                logger, event.pk, "ignored (already processed)"
            )
            return

        event.pretix_order_code = payment.order.code
        event.save(update_fields=["pretix_order_code"])

        _synchronize_payment(payment, checkout_id)

        event.processing_status = SumUpWebhookEvent.ProcessingStatus.PROCESSED
        event.processed_at = timezone.now()
        event.save(update_fields=["processing_status", "processed_at"])
        log_webhook_processed(
            logger, event.pk, "processed", order_code=payment.order.code
        )

    except Exception as exc:
        event.processing_status = SumUpWebhookEvent.ProcessingStatus.FAILED
        event.error_message = str(exc)
        event.processed_at = timezone.now()
        event.save(update_fields=["processing_status", "error_message", "processed_at"])
        log_webhook_failed(logger, event.pk, exc)


def _synchronize_payment(payment, checkout_id):
    """Synchronize a payment with SumUp checkout status."""
    from pretix_sumup.payment import SumUp

    provider = SumUp(payment.order.event)
    provider._synchronize_payment_status(payment)
