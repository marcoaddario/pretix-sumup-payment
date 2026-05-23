from unittest.mock import MagicMock, patch

import pytest

from pretix_sumup.services.payment import (
    _find_payment_by_reference,
    reconcile_payments,
)


class TestFindPaymentByReference:
    @patch("pretix.base.models.Order")
    def test_find_by_checkout_ref(self, mock_order):
        mock_order_instance = MagicMock()
        mock_order_instance.code = "TEST001"
        mock_order.objects.get.return_value = mock_order_instance

        result = _find_payment_by_reference("test-event/TEST001/1", MagicMock())

        mock_order.objects.get.assert_called_once()

    def test_find_by_empty_ref(self):
        result = _find_payment_by_reference(None, MagicMock())
        assert result is None

    @patch("pretix.base.models.OrderPayment")
    def test_find_by_invalid_ref(self, mock_order_payment):
        mock_order_payment.objects.filter.return_value.first.return_value = None
        result = _find_payment_by_reference("no-slash", MagicMock())
        assert result is None


class TestReconcilePayments:
    @patch("pretix_sumup.services.payment.SumUpClient")
    def test_reconcile_api_error(self, mock_client_class):
        from pretix_sumup.api.client import SumupApiError

        mock_client = MagicMock()
        mock_client.get_recent_transactions.side_effect = SumupApiError(
            "API error", "ERROR", None
        )
        mock_client_class.return_value = mock_client

        result = reconcile_payments(MagicMock(), "token", "MC001")

        assert "error" in result
        assert "API error" in result["error"]

    @patch("pretix_sumup.services.payment.SumUpClient")
    def test_reconcile_no_transactions(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.get_recent_transactions.return_value = {"items": []}
        mock_client_class.return_value = mock_client

        result = reconcile_payments(MagicMock(), "token", "MC001")

        assert result["checked"] == 0
        assert len(result["mismatches"]) == 0

    @patch("pretix_sumup.services.payment.SumUpClient")
    def test_reconcile_no_mismatches(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.get_recent_transactions.return_value = {
            "items": [
                {
                    "id": "txn_001",
                    "status": "SUCCESSFUL",
                    "amount": 10.0,
                    "currency": "GBP",
                    "checkout_ref": "test-event/TEST001/1",
                }
            ]
        }
        mock_client_class.return_value = mock_client

        with patch(
            "pretix_sumup.services.payment._find_payment_by_reference"
        ) as mock_find:
            mock_payment = MagicMock()
            mock_payment.info_data = {
                "sumup_transaction": {"id": "txn_001"}
            }
            mock_payment.order.status = "p"
            mock_find.return_value = mock_payment

            result = reconcile_payments(MagicMock(), "token", "MC001")

            assert result["checked"] == 1
            assert len(result["mismatches"]) == 0
