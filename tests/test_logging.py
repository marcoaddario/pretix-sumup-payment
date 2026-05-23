from unittest.mock import MagicMock

from pretix_sumup.utils.logging import (
    get_logger,
    log_admin_action,
    log_payment_confirmation,
    log_payment_initiation,
    log_reconciliation_action,
    log_webhook_failed,
    log_webhook_processed,
    log_webhook_received,
)


class TestLogging:
    def test_get_logger(self):
        logger = get_logger("test")
        assert logger.name == "pretix.plugins.sumup.test"

    def test_log_payment_initiation(self):
        mock_logger = MagicMock()
        log_payment_initiation(mock_logger, "ORDER001", 1, 10.0, "GBP")
        mock_logger.info.assert_called_once()
        args, kwargs = mock_logger.info.call_args
        assert kwargs.get("extra", {}).get("order_code") == "ORDER001"

    def test_log_payment_confirmation(self):
        mock_logger = MagicMock()
        log_payment_confirmation(mock_logger, "ORDER001", 1, "txn_001")
        mock_logger.info.assert_called_once()

    def test_log_webhook_received(self):
        mock_logger = MagicMock()
        log_webhook_received(mock_logger, "evt_001", "checkout.paid", "ch_001")
        mock_logger.info.assert_called_once()

    def test_log_webhook_processed(self):
        mock_logger = MagicMock()
        log_webhook_processed(mock_logger, 1, "processed", "ORDER001")
        mock_logger.info.assert_called_once()

    def test_log_webhook_failed(self):
        mock_logger = MagicMock()
        log_webhook_failed(mock_logger, 1, "Something broke")
        mock_logger.error.assert_called_once()

    def test_log_reconciliation_action(self):
        mock_logger = MagicMock()
        log_reconciliation_action(mock_logger, "completed", {"count": 5})
        mock_logger.info.assert_called_once()

    def test_log_admin_action(self):
        mock_logger = MagicMock()
        log_admin_action(mock_logger, "retry", "admin_user", {"event_id": 1})
        mock_logger.info.assert_called_once()
