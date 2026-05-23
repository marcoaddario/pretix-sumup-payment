from unittest.mock import MagicMock, patch

import pytest
import requests
from django.core.exceptions import ValidationError

from pretix_sumup.api.client import (
    SUMUP_BASE_URL,
    SumUpClient,
    SumupApiError,
)


class TestSumupApiError:
    def test_str_with_all_fields(self):
        err = SumupApiError("Something went wrong", "BAD_REQUEST", "amount")
        assert "BAD_REQUEST" in str(err)
        assert "Something went wrong" in str(err)
        assert "amount" in str(err)

    def test_str_without_param(self):
        err = SumupApiError("Not found", "NOT_FOUND", None)
        assert "NOT_FOUND" in str(err)
        assert "param" not in str(err).lower()


class TestSumUpClient:
    def test_init(self):
        client = SumUpClient("test_token", merchant_code="test_mc")
        assert client.access_token == "test_token"
        assert client.merchant_code == "test_mc"

    def test_auth_header(self):
        client = SumUpClient("test_token")
        header = client._auth_header()
        assert header["Authorization"] == "Bearer test_token"

    @patch("pretix_sumup.api.client.requests.get")
    def test_validate_access_token_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "merchant_profile": {
                "company_name": "Test Company",
                "merchant_code": "MC001",
            }
        }
        mock_get.return_value = mock_response

        client = SumUpClient("valid_token")
        name, code = client.validate_access_token()

        assert name == "Test Company"
        assert code == "MC001"
        mock_get.assert_called_once_with(
            f"{SUMUP_BASE_URL}/v0.1/me",
            headers={"Authorization": "Bearer valid_token"},
            timeout=15,
        )

    @patch("pretix_sumup.api.client.requests.get")
    def test_validate_access_token_unauthorized(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        client = SumUpClient("invalid_token")

        with pytest.raises(ValidationError, match="API Key is invalid"):
            client.validate_access_token()

    def test_validate_access_token_empty(self):
        client = SumUpClient("")

        with pytest.raises(ValidationError, match="No API Key given"):
            client.validate_access_token()

    @patch("pretix_sumup.api.client.requests.post")
    def test_create_checkout_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "checkout_123"}
        mock_post.return_value = mock_response

        client = SumUpClient("token", merchant_code="MC001")
        checkout_id = client.create_checkout(
            amount=10.00,
            currency="GBP",
            checkout_reference="event/order/1",
            description="Test order",
            return_url="https://example.com/return",
        )

        assert checkout_id == "checkout_123"
        mock_post.assert_called_once()
        call_data = mock_post.call_args[1]["json"]
        assert call_data["amount"] == 10.0
        assert call_data["currency"] == "GBP"
        assert call_data["merchant_code"] == "MC001"

    @patch("pretix_sumup.api.client.requests.post")
    def test_create_checkout_with_redirect(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "checkout_123"}
        mock_post.return_value = mock_response

        client = SumUpClient("token", merchant_code="MC001")
        checkout_id = client.create_checkout(
            amount=10.00,
            currency="GBP",
            checkout_reference="event/order/1",
            description="Test order",
            return_url="https://example.com/return",
            redirect_url="https://example.com/redirect",
        )

        assert checkout_id == "checkout_123"
        call_data = mock_post.call_args[1]["json"]
        assert "redirect_url" in call_data
        assert call_data["redirect_url"] == "https://example.com/redirect"

    @patch("pretix_sumup.api.client.requests.post")
    def test_create_checkout_api_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "message": "Invalid amount",
            "error_code": "INVALID_AMOUNT",
            "param": "amount",
        }
        mock_post.return_value = mock_response

        client = SumUpClient("token", merchant_code="MC001")

        with pytest.raises(SumupApiError):
            client.create_checkout(
                amount=-1,
                currency="GBP",
                checkout_reference="event/order/1",
                description="Test",
                return_url="https://example.com/return",
            )

    def test_create_checkout_no_merchant_code(self):
        client = SumUpClient("token")

        with pytest.raises(ValueError, match="merchant_code is required"):
            client.create_checkout(
                amount=10,
                currency="GBP",
                checkout_reference="ref",
                description="desc",
                return_url="https://example.com",
            )

    @patch("pretix_sumup.api.client.requests.get")
    def test_get_checkout(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "checkout_123", "status": "PAID"}
        mock_get.return_value = mock_response

        client = SumUpClient("token")
        result = client.get_checkout("checkout_123")

        assert result["status"] == "PAID"
        mock_get.assert_called_once_with(
            f"{SUMUP_BASE_URL}/v0.1/checkouts/checkout_123",
            headers={"Authorization": "Bearer token"},
            timeout=15,
        )

    @patch("pretix_sumup.api.client.requests.get")
    def test_get_transaction(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "txn_123", "status": "SUCCESSFUL"}
        mock_get.return_value = mock_response

        client = SumUpClient("token", merchant_code="MC001")
        result = client.get_transaction("txn_123")

        assert result["status"] == "SUCCESSFUL"
        mock_get.assert_called_once()

    @patch("pretix_sumup.api.client.requests.get")
    def test_get_recent_transactions(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{"id": "txn_1"}, {"id": "txn_2"}]
        }
        mock_get.return_value = mock_response

        client = SumUpClient("token", merchant_code="MC001")
        result = client.get_recent_transactions(limit=10)

        assert len(result["items"]) == 2

    @patch("pretix_sumup.api.client.requests.delete")
    def test_cancel_checkout(self, mock_delete):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        client = SumUpClient("token")
        client.cancel_checkout("checkout_123")

        mock_delete.assert_called_once()

    @patch("pretix_sumup.api.client.requests.post")
    def test_refund_transaction(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = SumUpClient("token", merchant_code="MC001")
        client.refund_transaction("txn_123", amount=5.00)

        mock_post.assert_called_once()
        call_data = mock_post.call_args[1]["json"]
        assert call_data["amount"] == 5.0

    @patch("pretix_sumup.api.client.requests.post")
    def test_refund_transaction_full(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = SumUpClient("token", merchant_code="MC001")
        client.refund_transaction("txn_123")

        mock_post.assert_called_once()
        assert mock_post.call_args[1]["json"] is None


class TestModuleLevelFunctions:
    @patch("pretix_sumup.api.client.SumUpClient.validate_access_token")
    def test_validate_access_token_and_get_merchant_code(self, mock_validate):
        from pretix_sumup.api.client import (
            validate_access_token_and_get_merchant_code,
        )

        mock_validate.return_value = ("Test Co", "MC001")
        result = validate_access_token_and_get_merchant_code("token")

        assert result == ("Test Co", "MC001")
