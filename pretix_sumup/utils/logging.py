import logging


def get_logger(name):
    return logging.getLogger(f"pretix.plugins.sumup.{name}")


def log_payment_initiation(logger, order_code, payment_id, amount, currency):
    logger.info(
        "Payment initiation",
        extra={
            "order_code": order_code,
            "payment_id": payment_id,
            "amount": float(amount) if amount else None,
            "currency": currency,
        },
    )


def log_payment_confirmation(logger, order_code, payment_id, transaction_id):
    logger.info(
        "Payment confirmed",
        extra={
            "order_code": order_code,
            "payment_id": payment_id,
            "transaction_id": transaction_id,
        },
    )


def log_webhook_received(logger, webhook_event_id, event_type, checkout_id):
    logger.info(
        "Webhook received",
        extra={
            "webhook_event_id": webhook_event_id,
            "event_type": event_type,
            "checkout_id": checkout_id,
        },
    )


def log_webhook_processed(logger, webhook_event_id, status, order_code=None):
    logger.info(
        f"Webhook processed ({status})",
        extra={
            "webhook_event_id": webhook_event_id,
            "status": status,
            "order_code": order_code,
        },
    )


def log_webhook_failed(logger, webhook_event_id, error):
    logger.error(
        f"Webhook processing failed: {error}",
        extra={
            "webhook_event_id": webhook_event_id,
            "error": str(error),
        },
    )


def log_reconciliation_action(logger, action, details=None):
    logger.info(
        f"Reconciliation: {action}",
        extra={"action": action, "details": details or {}},
    )


def log_admin_action(logger, action, user, details=None):
    logger.info(
        f"Admin action: {action} (by {user})",
        extra={
            "action": action,
            "user": str(user),
            "details": details or {},
        },
    )
