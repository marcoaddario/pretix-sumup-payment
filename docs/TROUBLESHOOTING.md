# Troubleshooting Guide

## Common Failure Modes

### 1. Payment shows as pending but SumUp says it's paid

**Symptom**: Order is stuck in "pending" state, but the customer
says the payment went through.

**Diagnosis**:
1. Check the SumUpWebhookEvent list in admin to see if a webhook arrived
2. Check the payload to see the checkout status
3. Try "Re-check payment" from the order page

**Fix**:
1. Go to the order in Pretix admin
2. Use the "Re-check payment from SumUp" action
3. The plugin will query SumUp API and update the order status

### 2. Webhook processing failed

**Symptom**: A webhook event shows "failed" status in the admin.

**Diagnosis**:
1. Open the webhook event detail to see the error message
2. Check the raw payload to verify it contains the expected data
3. Check order logs for related errors

**Fix**:
1. Click "Retry processing" on the webhook event detail page
2. The plugin will reprocess the webhook
3. If it fails again, check the error message for details

### 3. Duplicate webhook events

**Symptom**: Multiple webhook events for the same checkout.

**Diagnosis**:
1. Check the webhook event list for events with the same `event_id`
2. Duplicates should show as "ignored"

**Action**: No action needed. Idempotency handles this automatically.

### 4. Payment in SumUp but not in Pretix

**Symptom**: A transaction exists in SumUp but the corresponding
Pretix order shows no payment.

**Diagnosis**:
1. Use the "Reconcile recent SumUp payments" admin action
2. Check the report for "paid_in_sumup_unpaid_in_pretix" mismatches

**Fix**:
1. Click "Attempt repair" on the reconciliation page
2. The plugin will sync the payment status from SumUp

### 5. Refunded in SumUp but not in Pretix

**Symptom**: A refund was processed in SumUp but the Pretix order
still shows as paid.

**Diagnosis**:
1. Run reconciliation to detect "refunded_in_sumup_not_in_pretix" mismatches

**Fix**:
1. Manually refund the order in Pretix
2. The reconciliation tool will detect the mismatch

### 6. Missing transaction linkage

**Symptom**: The payment info doesn't have the SumUp transaction details.

**Diagnosis**:
1. Check the payment info in the order page
2. Run reconciliation to detect "missing_transaction_link" mismatches

**Fix**:
1. Use "Attempt repair" or "Force payment sync" to update the transaction data

## Manual Recovery Steps

### Re-check a single payment

1. Go to the order in Pretix admin
2. Click "Re-check payment from SumUp"
3. The plugin queries SumUp for the checkout status and updates the order

### Force sync all recent payments

1. Go to event settings → SumUp webhooks → Reconcile
2. Click "Refresh" to fetch recent SumUp transactions
3. Review mismatches
4. Click "Attempt repair" to fix them

### Retry a failed webhook

1. Go to event settings → SumUp webhooks
2. Find the failed webhook event
3. Click "Details"
4. Click "Retry processing"

## Debugging Guide

### Check if the webhook URL is configured correctly

In SumUp dashboard, the webhook URL should be:
```
https://your-domain.com/pretix/<org>/<event>/sumup/checkout_event/<payment_id>/
```

**Important**: The webhook URL must be accessible from the internet.
For local development, use ngrok or similar.

### Check if webhooks are arriving

1. Go to event settings → SumUp webhooks in Pretix admin
2. Check the list of webhook events
3. If no events appear, the webhook URL might be misconfigured
4. If events appear with "failed" status, check the error message

### Enable detailed logging

Set `PRETIX_DEBUG=1` in your environment. This enables:

- Structured JSON logging for all payment operations
- Debug-only webhook endpoints for testing
- More verbose error messages

View logs with:
```bash
docker compose logs -f pretix
```

### Test webhooks locally (PRETIX_DEBUG only)

```bash
# Fake successful payment
curl -X POST "http://localhost:8080/pretix/<org>/<event>/sumup/debug/fake-webhook/<payment_id>/"

# Fake failed payment
curl -X POST "http://localhost:8080/pretix/<org>/<event>/sumup/debug/fake-webhook-failed/<payment_id>/"
```

## Webhook Lifecycle

1. SumUp sends POST to your webhook URL
2. Plugin records the event in `SumUpWebhookEvent` (with full payload)
3. Plugin checks idempotency (event_id already processed?)
4. Plugin finds matching Pretix payment
5. Plugin syncs checkout status from SumUp API
6. Plugin marks event as processed (or failed/ignored)
7. You can view all events and retry failures in the admin UI

## How Reconciliation Works

1. Fetch recent (last 50) transactions from SumUp API
2. For each transaction:
   - Find the matching Pretix payment by checkout reference
   - Compare payment statuses
   - Check if transaction is linked in payment info
3. Report any mismatches found
4. Optionally repair mismatches by syncing statuses

Reconciliation is intentionally manual. Run it when you suspect
a discrepancy between SumUp and Pretix.
