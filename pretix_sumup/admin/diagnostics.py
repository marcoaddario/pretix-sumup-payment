import json
import logging

from django.contrib import messages
from django.db import models
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from pretix.base.models import Order, OrderPayment
from pretix.control.permissions import event_permission_required

from pretix_sumup.api.client import SumUpClient
from pretix_sumup.models.webhook import SumUpWebhookEvent
from pretix_sumup.payment import SumUp
from pretix_sumup.services.payment import reconcile_payments, repair_mismatch
from pretix_sumup.utils.logging import log_admin_action

logger = logging.getLogger("pretix.plugins.sumup.admin")


@event_permission_required("can_change_event_settings")
def webhook_event_list(request, organizer, event):
    """List all webhook events for this event."""
    queryset = SumUpWebhookEvent.objects.all()

    status = request.GET.get("status")
    if status:
        queryset = queryset.filter(processing_status=status)

    event_type = request.GET.get("event_type")
    if event_type:
        queryset = queryset.filter(event_type=event_type)

    search = request.GET.get("search")
    if search:
        queryset = queryset.filter(
            models.Q(pretix_order_code__icontains=search)
            | models.Q(sumup_checkout_id__icontains=search)
            | models.Q(event_id__icontains=search)
        )

    return TemplateResponse(
        request,
        "pretix_sumup/webhook_event_list.html",
        {
            "events": queryset[:100],
            "status_filter": status,
            "event_type_filter": event_type,
            "search": search or "",
        },
    )


@event_permission_required("can_change_event_settings")
def webhook_event_detail(request, organizer, event, event_id):
    """Show webhook event detail."""
    webhook_event = get_object_or_404(SumUpWebhookEvent, pk=event_id)

    return TemplateResponse(
        request,
        "pretix_sumup/webhook_event_detail.html",
        {
            "event": webhook_event,
            "payload": webhook_event.get_payload(),
            "headers": webhook_event.get_headers(),
        },
    )


@event_permission_required("can_change_event_settings")
def retry_webhook(request, organizer, event, event_id):
    """Retry processing a failed webhook."""
    webhook_event = get_object_or_404(SumUpWebhookEvent, pk=event_id)

    if webhook_event.processing_status != SumUpWebhookEvent.ProcessingStatus.FAILED:
        messages.warning(request, _("Only failed webhook events can be retried."))
        return HttpResponseRedirect(
            reverse(
                "plugins:pretix_sumup:webhook_event_detail",
                kwargs={"organizer": organizer.slug, "event": event.slug, "event_id": event_id},
            )
        )

    from pretix_sumup.webhooks.processor import process_webhook_event

    process_webhook_event(webhook_event)

    log_admin_action(
        logger,
        "retry_webhook",
        request.user,
        {"webhook_event_id": event_id, "result": webhook_event.processing_status},
    )

    messages.success(
        request,
        _("Webhook reprocessed. New status: {}").format(webhook_event.processing_status),
    )
    return HttpResponseRedirect(
        reverse(
            "plugins:pretix_sumup:webhook_event_detail",
            kwargs={"organizer": organizer.slug, "event": event.slug, "event_id": event_id},
        )
    )


@event_permission_required("can_change_event_settings")
def recheck_payment(request, organizer, event, payment_id):
    """Re-check a payment status with SumUp."""
    payment = get_object_or_404(
        OrderPayment, pk=payment_id, order__event=event
    )

    try:
        provider = SumUp(event)
        provider._synchronize_payment_status(payment, force=True)
        provider._try_synchronize_transaction(
            payment, payment.info_data.get("sumup_transaction", {}).get("id")
        )
        log_admin_action(
            logger,
            "recheck_payment",
            request.user,
            {"payment_id": payment_id, "order_code": payment.order.code},
        )
        messages.success(request, _("Payment status re-checked successfully."))
    except Exception as exc:
        logger.exception("Failed to re-check payment %s", payment_id)
        messages.error(request, _("Failed to re-check payment: {}").format(str(exc)))

    return HttpResponseRedirect(
        reverse(
            "control:event.order",
            kwargs={
                "organizer": organizer.slug,
                "event": event.slug,
                "code": payment.order.code,
            },
        )
    )


@event_permission_required("can_change_event_settings")
def force_payment_sync(request, organizer, event, payment_id):
    """Force sync a payment from SumUp transaction data."""
    payment = get_object_or_404(
        OrderPayment, pk=payment_id, order__event=event
    )

    try:
        provider = SumUp(event)
        checkout_id = payment.info_data.get("sumup_checkout_id")
        if checkout_id:
            provider._synchronize_payment_status(payment, force=True)

        log_admin_action(
            logger,
            "force_payment_sync",
            request.user,
            {"payment_id": payment_id, "order_code": payment.order.code},
        )
        messages.success(request, _("Payment force-synced successfully."))
    except Exception as exc:
        logger.exception("Failed to force sync payment %s", payment_id)
        messages.error(request, _("Failed to sync payment: {}").format(str(exc)))

    return HttpResponseRedirect(
        reverse(
            "control:event.order",
            kwargs={
                "organizer": organizer.slug,
                "event": event.slug,
                "code": payment.order.code,
            },
        )
    )


@event_permission_required("can_change_event_settings")
def reconcile_view(request, organizer, event):
    """Run reconciliation and show results."""
    provider = SumUp(event)
    access_token = provider.settings.get("access_token")
    merchant_code = provider.settings.get("merchant_code")

    if not access_token or not merchant_code:
        messages.error(
            request,
            _("SumUp is not configured for this event."),
        )
        return HttpResponseRedirect(
            reverse(
                "control:event.settings.payment.provider",
                kwargs={
                    "organizer": organizer.slug,
                    "event": event.slug,
                    "provider": "sumup",
                },
            )
        )

    result = reconcile_payments(event, access_token, merchant_code)

    if request.POST.get("action") == "repair":
        repaired_count = 0
        for mismatch in result.get("mismatches", []):
            outcome = repair_mismatch(
                mismatch, access_token, merchant_code, event
            )
            if outcome.get("repaired"):
                repaired_count += 1

        log_admin_action(
            logger,
            "reconciliation_repair",
            request.user,
            {"repaired": repaired_count, "total": len(result.get("mismatches", []))},
        )
        messages.success(
            request,
            _("Repaired {} out of {} mismatches.").format(
                repaired_count, len(result.get("mismatches", []))
            ),
        )
        return HttpResponseRedirect(
            reverse(
                "plugins:pretix_sumup:reconcile",
                kwargs={"organizer": organizer.slug, "event": event.slug},
            )
        )

    return TemplateResponse(
        request,
        "pretix_sumup/reconcile.html",
        {
            "result": result,
        },
    )
