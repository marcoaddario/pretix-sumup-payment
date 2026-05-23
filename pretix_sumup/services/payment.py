import logging

from decimal import Decimal
from django.utils.translation import gettext_lazy as _

from pretix_sumup.api.client import SumUpClient, SumupApiError
from pretix_sumup.utils.logging import log_reconciliation_action

logger = logging.getLogger("pretix.plugins.sumup.services")


def reconcile_payments(event, access_token, merchant_code, limit=50):
    """Reconcile recent SumUp payments against Pretix orders.
    Returns a list of mismatch reports.
    """
    client = SumUpClient(access_token, merchant_code=merchant_code)
    mismatches = []

    try:
        transactions = client.get_recent_transactions(limit=limit)
    except SumupApiError as exc:
        log_reconciliation_action(
            logger, "fetch_failed", {"error": str(exc)}
        )
        return {"error": str(exc), "mismatches": []}

    items = transactions.get("items", [])
    if not items:
        return {"mismatches": [], "checked": 0}

    from pretix.base.models import OrderPayment
    from pretix.base.models import Order

    for txn in items:
        txn_id = txn.get("id", "")
        txn_status = txn.get("status", "")
        txn_amount = Decimal(str(txn.get("amount", 0)))
        txn_currency = txn.get("currency", "")
        checkout_ref = txn.get("checkout_ref", "")

        payment = _find_payment_by_reference(checkout_ref, event)
        if not payment:
            mismatches.append(
                {
                    "type": "no_matching_payment",
                    "transaction_id": txn_id,
                    "status": txn_status,
                    "amount": txn_amount,
                    "currency": txn_currency,
                    "reference": checkout_ref,
                    "detail": _("No matching Pretix payment found"),
                }
            )
            continue

        order = payment.order
        if txn_status == "SUCCESSFUL" and order.status != Order.STATUS_PAID:
            mismatches.append(
                {
                    "type": "paid_in_sumup_unpaid_in_pretix",
                    "transaction_id": txn_id,
                    "status": txn_status,
                    "payment_id": payment.pk,
                    "order_code": order.code,
                    "detail": _("Paid in SumUp but not confirmed in Pretix"),
                }
            )
        elif txn_status == "REFUNDED" and order.status != Order.STATUS_REFUNDED:
            mismatches.append(
                {
                    "type": "refunded_in_sumup_not_in_pretix",
                    "transaction_id": txn_id,
                    "status": txn_status,
                    "payment_id": payment.pk,
                    "order_code": order.code,
                    "detail": _("Refunded in SumUp but not in Pretix"),
                }
            )

        stored_txn = payment.info_data.get("sumup_transaction")
        if not stored_txn or stored_txn.get("id") != txn_id:
            mismatches.append(
                {
                    "type": "missing_transaction_link",
                    "transaction_id": txn_id,
                    "status": txn_status,
                    "payment_id": payment.pk,
                    "order_code": order.code,
                    "detail": _("Transaction not linked to payment"),
                }
            )

    log_reconciliation_action(
        logger,
        "completed",
        {"checked": len(items), "mismatches": len(mismatches)},
    )

    return {"mismatches": mismatches, "checked": len(items)}


def repair_mismatch(mismatch, access_token, merchant_code, event):
    """Attempt to repair a single mismatch."""
    from pretix_sumup.payment import SumUp

    if mismatch["type"] == "paid_in_sumup_unpaid_in_pretix":
        payment = _find_payment_by_reference(mismatch["reference"], event)
        if payment:
            provider = SumUp(event)
            provider._synchronize_payment_status(payment)
            return {"repaired": True, "action": "payment_synced", "payment_id": payment.pk}

    if mismatch["type"] == "missing_transaction_link":
        payment = _find_payment_by_reference(mismatch["reference"], event)
        if payment and mismatch.get("transaction_id"):
            provider = SumUp(event)
            provider._try_synchronize_transaction(
                payment, mismatch["transaction_id"]
            )
            return {
                "repaired": True,
                "action": "transaction_synced",
                "payment_id": payment.pk,
            }

    return {"repaired": False, "action": "no_repair_available"}


def _find_payment_by_reference(checkout_ref, event):
    """Find a Pretix payment by SumUp checkout reference."""
    from pretix.base.models import OrderPayment

    if not checkout_ref:
        return None

    parts = checkout_ref.split("/")
    if len(parts) >= 2:
        order_code = parts[-2]
        from pretix.base.models import Order

        try:
            order = Order.objects.get(code=order_code, event=event)
            return order.payments.last()
        except Order.DoesNotExist:
            pass

    payment = OrderPayment.objects.filter(
        order__event=event, info__contains=checkout_ref
    ).first()
    return payment
