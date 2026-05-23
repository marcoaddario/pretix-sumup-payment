from unittest.mock import MagicMock, patch

import pytest

from pretix_sumup.payment import SumUp


class TestSumUpProvider:
    def test_identifier(self):
        assert SumUp.identifier == "sumup"

    def test_is_allowed_below_minimum(self):
        provider = SumUp(MagicMock())
        assert provider.is_allowed(None, total=0) is False

    def test_is_allowed_at_minimum(self):
        provider = SumUp(MagicMock())
        assert provider.is_allowed(None, total=1) is True

    def test_is_allowed_above_minimum(self):
        provider = SumUp(MagicMock())
        assert provider.is_allowed(None, total=100) is True

    def test_is_allowed_none(self):
        provider = SumUp(MagicMock())
        assert provider.is_allowed(None, total=None) is True

    @patch("pretix_sumup.payment.SumUpClient")
    def test_settings_form_clean_valid(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.validate_access_token.return_value = ("Test Co", "MC001")
        mock_client_class.return_value = mock_client

        provider = SumUp(MagicMock())
        cleaned = {
            "payment_sumup_access_token": "sup_sk_test_token",
            "payment_sumup_enable_apms": False,
            "payment_sumup_enable_google_pay": False,
            "payment_sumup_google_pay_merchant_id": "",
        }
        result = provider.settings_form_clean(cleaned)
        assert result["payment_sumup_merchant_code"] == "MC001"
        assert result["payment_sumup_merchant_name"] == "Test Co"

    @patch("pretix_sumup.payment.build_absolute_uri")
    @patch("pretix_sumup.payment.SumUpClient")
    def test_execute_payment_success(self, mock_client_class, mock_build_uri):
        mock_client = MagicMock()
        mock_client.create_checkout.return_value = "checkout_123"
        mock_client_class.return_value = mock_client
        mock_build_uri.return_value = "https://example.com/return/"

        provider = SumUp(MagicMock())
        provider.settings = MagicMock()
        provider.settings.get = lambda key, **kw: "test_value"

        payment = MagicMock()
        payment.local_id = 1
        payment.amount = 10.0
        payment.info_data = {}
        order = MagicMock()
        order.code = "ORDER001"
        order.event.slug = "test-event"
        order.event.currency = "GBP"
        order.event.name = "Test Event"
        payment.order = order

        provider.execute_payment(MagicMock(), payment)

        mock_client.create_checkout.assert_called_once()
        assert payment.info_data["sumup_checkout_id"] == "checkout_123"

    @patch("pretix_sumup.payment.SumUpClient")
    def test_execute_payment_failure(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.create_checkout.side_effect = Exception("API failure")
        mock_client_class.return_value = mock_client

        provider = SumUp(MagicMock())
        provider.settings = MagicMock()
        provider.settings.get = lambda key, **kw: "test_value"

        payment = MagicMock()
        payment.local_id = 1
        payment.amount = 10.0
        payment.info_data = {}
        order = MagicMock()
        order.code = "ORDER001"
        order.event.slug = "test-event"
        order.event.currency = "GBP"
        order.event.name = "Test Event"
        payment.order = order

        from pretix.base.payment import PaymentException

        with pytest.raises(PaymentException):
            provider.execute_payment(MagicMock(), payment)

        payment.fail.assert_called_once()

    def test_cancel_payment_with_checkout_id(self):
        provider = SumUp(MagicMock())
        provider.settings = MagicMock()
        provider.settings.get = lambda key, **kw: "token"

        payment = MagicMock()
        payment.info_data = {"sumup_checkout_id": "checkout_123"}

        with patch("pretix_sumup.payment.SumUpClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            provider.cancel_payment(payment)
            mock_client.cancel_checkout.assert_called_once_with("checkout_123")
