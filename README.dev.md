# Development Guide

## Prerequisites

- Docker and Docker Compose
- Python 3.9+ (for local development outside Docker)

## Quick Start

### 1. Build and start the development environment

```bash
docker compose build
docker compose up -d
```

This starts Pretix with the plugin mounted in editable mode at
`/pretix/plugins/pretix-sumup-payment`.

### 2. Run database migrations

```bash
docker compose exec pretix python -m pretix migrate
```

### 3. Create a superuser

```bash
docker compose exec pretix python -m pretix createsuperuser
```

### 4. Access the site

Visit http://localhost:8080/ and log in with your superuser credentials.

## Development Workflow

### Plugin code changes

The plugin code is mounted as a Docker volume, so changes are reflected
immediately. You only need to restart pretix for changes to take effect:

```bash
scripts/restart.sh
```

### View logs

```bash
scripts/logs.sh
```

Or directly:

```bash
docker compose logs -f pretix
```

### Run migrations after model changes

```bash
docker compose exec pretix python -m pretix makemigrations pretix_sumup
docker compose exec pretix python -m pretix migrate
```

## Plugin Installation

The plugin is installed in editable mode via `pip install -e`.
If you need to reinstall:

```bash
docker compose exec pretix pip install -e /pretix/plugins/pretix-sumup-payment
```

## Webhook Testing

With `PRETIX_DEBUG=1`, fake webhook endpoints are available:

### Fake successful payment

```bash
curl -X POST \
  "http://localhost:8080/pretix/<org>/<event>/sumup/debug/fake-webhook/<payment_id>/"
```

### Fake failed payment

```bash
curl -X POST \
  "http://localhost:8080/pretix/<org>/<event>/sumup/debug/fake-webhook-failed/<payment_id>/"
```

### Real webhook testing with ngrok

1. Start ngrok: `ngrok http 8080`
2. Configure SumUp webhook to point to: `https://<ngrok-url>/pretix/<org>/<event>/sumup/checkout_event/<payment_id>/`
3. Make a test payment

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRETIX_DEBUG` | Enables debug mode and developer tools | off |
| `PYTHONUNBUFFERED` | Ensures logs are visible immediately | 1 |

## Project Structure

```
pretix_sumup/
├── api/              # SumUp API client
├── webhooks/         # Webhook processing
├── admin/            # Admin diagnostics UI
├── views/            # Customer-facing views
├── services/         # Business logic (reconciliation)
├── models/           # Database models
├── utils/            # Logging and utilities
├── payment.py        # Main payment provider
├── signals.py        # Pretix signals
└── urls.py           # URL routing
```

## Debugging

1. Set `PRETIX_DEBUG=1` in the environment
2. Check logs: `docker compose logs -f pretix`
3. Webhook events are persisted in the `SumUpWebhookEvent` table
4. Admin diagnostics UI is available under event settings → SumUp webhooks
