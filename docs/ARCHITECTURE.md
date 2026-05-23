# Architecture

## Overview

`pretix-sumup-payment` is a lightweight Pretix payment plugin for
SumUp. It enables credit card and alternative payment method (APM)
acceptance through SumUp's payment gateway.

## Module Structure

```
pretix_sumup/
├── __init__.py          # Package version
├── apps.py              # Plugin configuration and Pretix registration
├── signals.py           # Pretix signal handlers (provider, CSP, nav)
├── urls.py              # URL routing (event patterns)
├── payment.py           # SumUp payment provider (BasePaymentProvider)
│
├── api/
│   ├── __init__.py
│   └── client.py        # SumUp REST API client
│
├── webhooks/
│   ├── __init__.py
│   ├── views.py         # Webhook HTTP endpoint
│   └── processor.py     # Webhook processing and idempotency
│
├── admin/
│   ├── __init__.py
│   └── diagnostics.py   # Admin diagnostic views
│
├── views/
│   ├── __init__.py
│   └── return.py        # Customer return view
│
├── services/
│   ├── __init__.py
│   └── payment.py       # Payment reconciliation logic
│
├── models/
│   ├── __init__.py
│   └── webhook.py       # SumUpWebhookEvent model
│
└── utils/
    ├── __init__.py
    └── logging.py        # Structured logging utilities
```

## Key Design Decisions

### 1. Module Separation

Business logic is split by concern:

- **`api/`**: All SumUp HTTP communication. Isolated from Pretix internals.
- **`webhooks/`**: Webhook persistence, idempotency, and processing.
- **`admin/`**: Admin diagnostic views for operational visibility.
- **`services/`**: Higher-level operations like reconciliation.
- **`models/`**: Database models for observability.
- **`utils/`**: Shared utilities (logging).

### 2. Webhook Persistence (NOT a Queue)

All incoming webhook payloads are stored in the database via
`SumUpWebhookEvent`. This provides:

- Full audit trail of all webhook events
- Debugging visibility into payloads and headers
- Manual retry capability for failed events
- No automatic retry infrastructure

This is specifically NOT a message queue. Events are stored for
observability and manual replay support only.

### 3. Idempotency

Webhook deduplication is done via `event_id`. If a webhook arrives
with an `event_id` that was already processed, it is marked as
`ignored` and not processed again.

This is safe against:
- Duplicate webhook delivery
- Retry storms
- Network duplicates

### 4. Manual Reconciliation Over Automation

Payment reconciliation is manual-only. An admin action fetches recent
transactions from SumUp, compares them with Pretix orders, and reports
mismatches. Repairs are done explicitly, not automatically.

This avoids:
- Background workers
- Celery tasks
- Cron jobs
- Complex scheduling

### 5. Developer Experience

When `PRETIX_DEBUG=1`, debug-only endpoints are available:

- Fake successful webhook generator
- Fake failed webhook generator

These allow local development without live SumUp API calls.

## Data Flow

### Payment Flow (Happy Path)

1. Customer places order → Pretix creates OrderPayment
2. `execute_payment()` → `SumUpClient.create_checkout()` → SumUp API
3. SumUp returns checkout_id → stored in payment.info_data
4. Customer redirected to SumUp (or card widget shown inline)
5. SumUp sends webhook → `checkout_event` view
6. `record_webhook_event()` → stores payload in SumUpWebhookEvent
7. `process_webhook_event()` → `_synchronize_payment_status()` → confirms payment
8. Customer returned to Pretix → `ReturnView` → final sync

### Webhook Flow

1. SumUp sends POST to `/sumup/checkout_event/<payment_id>/`
2. `checkout_event` view (CSRF-exempt) processes it
3. Payload is recorded in `SumUpWebhookEvent` (always)
4. Idempotency check: if `event_id` already processed, mark ignored
5. Processing: find matching Pretix payment, sync status
6. Result recorded: processed / failed / ignored

### Reconciliation Flow

1. Admin clicks "Reconcile recent SumUp payments"
2. Plugin fetches recent transactions from SumUp API
3. Compares with Pretix orders by checkout reference
4. Reports mismatches: unpaid, unlinked, refund differences
5. Admin optionally clicks "Attempt repair"
6. Each mismatch is individually repaired (sync status, link transaction)
