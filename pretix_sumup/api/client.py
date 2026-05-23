import logging
from decimal import Decimal

import requests
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("pretix.plugins.sumup.api")

SUMUP_BASE_URL = "https://api.sumup.com"
SUMUP_CHECKOUT_TIMEOUT = 15
SUMUP_TRANSACTION_TIMEOUT = 15


class SumupApiError(Exception):
    def __init__(self, message, error_code, param):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.param = param

    def __str__(self):
        parts = [str(self.error_code), self.message]
        if self.param:
            parts.append(f"({self.param})")
        return " - ".join(p for p in parts if p)


def handle_response_status(response):
    if response.status_code // 100 == 4:
        try:
            response_body = response.json()
        except ValueError:
            response_body = {}
        raise SumupApiError(
            response_body.get("message") or response_body.get("error_message") or "",
            response_body.get("error_code"),
            response_body.get("param"),
        )
    response.raise_for_status()


class SumUpClient:
    def __init__(self, access_token, merchant_code=None):
        self.access_token = access_token
        self.merchant_code = merchant_code

    def _auth_header(self):
        return {"Authorization": "Bearer " + self.access_token}

    def validate_access_token(self):
        if not self.access_token:
            raise ValidationError(_("No API Key given."))
        try:
            response = requests.get(
                f"{SUMUP_BASE_URL}/v0.1/me",
                headers=self._auth_header(),
                timeout=SUMUP_CHECKOUT_TIMEOUT,
            )
        except IOError:
            raise ValidationError(_("Could not contact SumUp."))
        if response.status_code == 401:
            raise ValidationError(_("The API Key is invalid."))
        handle_response_status(response)
        response_body = response.json()
        return (
            response_body["merchant_profile"]["company_name"],
            response_body["merchant_profile"]["merchant_code"],
        )

    def create_checkout(
        self,
        amount: Decimal,
        currency: str,
        checkout_reference: str,
        description: str,
        return_url: str,
        redirect_url: str = None,
    ):
        if not self.merchant_code:
            raise ValueError("merchant_code is required to create a checkout")
        checkout_data = {
            "checkout_reference": checkout_reference,
            "description": description,
            "amount": float(amount),
            "currency": currency,
            "merchant_code": self.merchant_code,
            "return_url": return_url,
        }
        if redirect_url:
            checkout_data["redirect_url"] = redirect_url

        logger.info(
            "Creating SumUp checkout",
            extra={
                "checkout_reference": checkout_reference,
                "amount": float(amount),
                "currency": currency,
            },
        )
        response = requests.post(
            f"{SUMUP_BASE_URL}/v0.1/checkouts",
            json=checkout_data,
            headers=self._auth_header(),
            timeout=SUMUP_CHECKOUT_TIMEOUT,
        )
        handle_response_status(response)
        response_body = response.json()
        checkout_id = response_body["id"]
        logger.info(
            "SumUp checkout created",
            extra={"checkout_id": checkout_id, "checkout_reference": checkout_reference},
        )
        return checkout_id

    def get_checkout(self, checkout_id: str):
        response = requests.get(
            f"{SUMUP_BASE_URL}/v0.1/checkouts/{checkout_id}",
            headers=self._auth_header(),
            timeout=SUMUP_CHECKOUT_TIMEOUT,
        )
        handle_response_status(response)
        return response.json()

    def cancel_checkout(self, checkout_id: str):
        response = requests.delete(
            f"{SUMUP_BASE_URL}/v0.1/checkouts/{checkout_id}",
            headers=self._auth_header(),
            timeout=SUMUP_CHECKOUT_TIMEOUT,
        )
        handle_response_status(response)

    def get_transaction(self, transaction_id: str):
        if not self.merchant_code:
            raise ValueError("merchant_code is required to get a transaction")
        response = requests.get(
            f"{SUMUP_BASE_URL}/v2.1/merchants/{self.merchant_code}/transactions",
            params={"id": transaction_id},
            headers=self._auth_header(),
            timeout=SUMUP_TRANSACTION_TIMEOUT,
        )
        handle_response_status(response)
        return response.json()

    def get_recent_transactions(self, limit: int = 50, offset: int = 0):
        if not self.merchant_code:
            raise ValueError("merchant_code is required to list transactions")
        response = requests.get(
            f"{SUMUP_BASE_URL}/v2.1/merchants/{self.merchant_code}/transactions",
            params={"limit": limit, "offset": offset},
            headers=self._auth_header(),
            timeout=SUMUP_TRANSACTION_TIMEOUT,
        )
        handle_response_status(response)
        return response.json()

    def refund_transaction(self, transaction_id: str, amount: Decimal = None):
        if not self.merchant_code:
            raise ValueError("merchant_code is required to refund a transaction")
        payload = {"amount": float(amount)} if amount is not None else None
        response = requests.post(
            f"{SUMUP_BASE_URL}/v1.0/merchants/{self.merchant_code}/payments/{transaction_id}/refunds",
            json=payload,
            headers=self._auth_header(),
            timeout=SUMUP_TRANSACTION_TIMEOUT,
        )
        handle_response_status(response)


def validate_access_token_and_get_merchant_code(access_token):
    client = SumUpClient(access_token)
    return client.validate_access_token()


def create_checkout(
    amount, currency, checkout_reference, description, merchant_code, return_url, access_token, redirect_url=None,
):
    client = SumUpClient(access_token, merchant_code=merchant_code)
    return client.create_checkout(
        amount=amount,
        currency=currency,
        checkout_reference=checkout_reference,
        description=description,
        return_url=return_url,
        redirect_url=redirect_url,
    )


def get_checkout(checkout_id, access_token):
    client = SumUpClient(access_token)
    return client.get_checkout(checkout_id)


def cancel_checkout(checkout_id, access_token):
    client = SumUpClient(access_token)
    client.cancel_checkout(checkout_id)


def get_transaction(transaction_id, merchant_code, access_token):
    client = SumUpClient(access_token, merchant_code=merchant_code)
    return client.get_transaction(transaction_id)


def refund_transaction(transaction_id, merchant_code, access_token, amount=None):
    client = SumUpClient(access_token, merchant_code=merchant_code)
    client.refund_transaction(transaction_id, amount=amount)
