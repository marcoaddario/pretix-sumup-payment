import logging
import os

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from pretix_sumup.models.webhook import SumUpWebhookEvent
from pretix_sumup.webhooks.processor import process_webhook_event, record_webhook_event

logger = logging.getLogger("pretix.plugins.sumup.webhooks")


@csrf_exempt
@require_POST
def checkout_event(request, *args, **kwargs):
    """Handle incoming SumUp webhook notifications."""
    event = record_webhook_event(request)
    process_webhook_event(event)
    return HttpResponse(status=204)


def debug_fake_webhook(request, *args, **kwargs):
    """Generate and process a fake successful webhook for testing.
    Only available when PRETIX_DEBUG=1.
    """
    if not os.environ.get("PRETIX_DEBUG"):
        return HttpResponse(status=404)

    import json
    from django.shortcuts import get_object_or_404
    from pretix.base.models import OrderPayment

    payment_pk = kwargs.get("payment")
    payment = get_object_or_404(
        OrderPayment, pk=payment_pk, order__event=request.event
    )
    checkout_id = payment.info_data.get("sumup_checkout_id")
    if not checkout_id:
        return JsonResponse({"error": "No checkout_id found for this payment"}, status=400)

    payload = {
        "event_id": f"fake_{payment_pk}_{checkout_id}",
        "event_type": "checkout.paid",
        "checkout_id": checkout_id,
        "transaction_id": f"fake_txn_{payment_pk}",
    }
    event = SumUpWebhookEvent.objects.create(
        event_type=payload["event_type"],
        event_id=payload["event_id"],
        sumup_checkout_id=payload["checkout_id"],
        sumup_transaction_id=payload["transaction_id"],
        payload_json=json.dumps(payload),
        headers_json=json.dumps({"X-Fake": "true"}),
        processing_status=SumUpWebhookEvent.ProcessingStatus.PENDING,
    )
    process_webhook_event(event)

    return JsonResponse(
        {
            "status": "ok",
            "webhook_event_id": event.pk,
            "processing_status": event.processing_status,
        }
    )


def debug_fake_webhook_failed(request, *args, **kwargs):
    """Generate a fake failed webhook for testing.
    Only available when PRETIX_DEBUG=1.
    """
    if not os.environ.get("PRETIX_DEBUG"):
        return HttpResponse(status=404)

    import json
    from django.shortcuts import get_object_or_404
    from pretix.base.models import OrderPayment

    payment_pk = kwargs.get("payment")
    payment = get_object_or_404(
        OrderPayment, pk=payment_pk, order__event=request.event
    )
    checkout_id = payment.info_data.get("sumup_checkout_id")
    if not checkout_id:
        return JsonResponse({"error": "No checkout_id found for this payment"}, status=400)

    payload = {
        "event_id": f"fake_failed_{payment_pk}",
        "event_type": "checkout.failed",
        "checkout_id": checkout_id,
    }
    event = SumUpWebhookEvent.objects.create(
        event_type=payload["event_type"],
        event_id=payload["event_id"],
        sumup_checkout_id=payload["checkout_id"],
        payload_json=json.dumps(payload),
        headers_json=json.dumps({"X-Fake": "true"}),
        processing_status=SumUpWebhookEvent.ProcessingStatus.PENDING,
    )
    process_webhook_event(event)

    return JsonResponse(
        {
            "status": "ok",
            "webhook_event_id": event.pk,
            "processing_status": event.processing_status,
        }
    )
