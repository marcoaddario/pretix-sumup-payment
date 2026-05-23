import logging
from collections import OrderedDict
from decimal import Decimal

from django import forms
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from pretix.base.forms import SECRET_REDACTED, SecretKeySettingsField
from pretix.base.middleware import get_language_from_request
from pretix.base.models import Order, OrderPayment, OrderRefund
from pretix.base.payment import BasePaymentProvider, PaymentException
from pretix.multidomain.urlreverse import build_absolute_uri
from pretix.plugins.stripe.forms import StripeKeyValidator

from pretix_sumup.api.client import SumUpClient, SumupApiError
from pretix_sumup.utils.logging import (
    log_payment_confirmation,
    log_payment_initiation,
)

logger = logging.getLogger("pretix.plugins.sumup.payment")


class SumUp(BasePaymentProvider):
    identifier = "sumup"
    verbose_name = _("Credit card via SumUp")
    public_name = _("Credit card")
    abort_pending_allowed = True

    @property
    def settings_form_fields(self):
        d = OrderedDict(
            [
                (
                    "access_token",
                    SecretKeySettingsField(
                        label=_("API Key"),
                        required=True,
                        help_text=_(
                            "API keys are authorization tokens that allow pretix to call SumUp on your behalf. "
                            '<a href="https://developer.sumup.com/api-keys" target="_blank">Click here to '
                            "manage API Keys in SumUp</a>"
                        ),
                        validators=(StripeKeyValidator("sup_sk_"),),
                    ),
                ),
                (
                    "merchant_code",
                    forms.CharField(
                        widget=forms.TextInput(
                            attrs={
                                "maxlength": 10,
                                "readonly": "readonly",
                                "placeholder": _("Automatically filled in"),
                            }
                        ),
                        empty_value="-",
                        label=_("Merchant Code"),
                    ),
                ),
                (
                    "merchant_name",
                    forms.CharField(
                        widget=forms.TextInput(
                            attrs={
                                "readonly": "readonly",
                                "placeholder": _("Automatically filled in"),
                            }
                        ),
                        empty_value="-",
                        label=_("Merchant Name"),
                    ),
                ),
                (
                    "enable_apms",
                    forms.BooleanField(
                        label=_("Enable Alternative Payment Methods"),
                        required=False,
                        help_text=_(
                            "Allow customers to pay using alternative payment methods like Apple Pay, Google Pay, iDEAL. <br>"
                            '<i>The supported payment methods depend on the country of your SumUp account. </i>'
                            '<i><a href="https://developer.sumup.com/online-payments/apm/introduction" target="_blank">Learn more</a></i> <br>'
                            "<br>"
                            "<i>In order to enable Apple Pay:</i><br>"
                            "<i>1. Download the Domain verification file from "
                            '<a href="https://developer.sumup.com/settings/wallets/apple-pay?tab=web" target="_blank">SumUp Wallets Settings</a> '
                            "and open it with a text editor</i><br>"
                            '<i>2. Copy and paste the whole file as text to the "ApplePay MerchantID Domain Association" field under '
                            'Pretix\'s "Global settings" (only accessible as an Admin user via "Admin mode")</i><br>'
                            "<i>3. Verify your domain by pasting it to "
                            '<a href="https://developer.sumup.com/settings/wallets" target="_blank">SumUp Wallets Settings</a> '
                            'and clicking "Check domain" (like "example.com" or "world.example.com")</i><br>'
                        ),
                    ),
                ),
                (
                    "enable_google_pay",
                    forms.BooleanField(
                        label=_("Enable Google Pay"),
                        required=False,
                        help_text=_(
                            "Allow customers to pay using Google Pay.<br>"
                            "<br>"
                            "<i>Follow these steps to enable Google Pay:</i><br>"
                            "<i>1. Register a Google Pay business account at "
                            '<a href="https://pay.google.com/business/console/" target="_blank">Google Pay for Business</a></i><br>'
                            '<i>2. Fill out your information under the "Business profile" tab and get it approved by Google</i><br>'
                            "<i>3. Enable Google Pay here and fill in your Google Merchant ID "
                            "(found next to your business name on the Google Pay console)</i><br>"
                            '<i>4. In Google Pay console\'s "Google Pay API" tab, fill in your domain and choose "Gateway" as Integration type</i><br>'
                            "<i>5. Take screenshots of your Pretix store and submit them to Google. For test screens, add:</i>"
                            " <code>#sumup-widget:google-pay-demo-mode</code> "
                            "<i>to the end of your payment URL</i><br>"
                            "<i>6. After Google approves your implementation (usually within 48h), contact SumUp's Integration Team to activate Google Pay"
                            ' through the <a href="https://developer.sumup.com/contact" target="_blank">SumUp contact form</a>, providing your '
                            "SumUp Merchant Code, Email, and a test ticket shop URL</i><br>"
                            "<br>"
                            "<i>For more detailed instructions and example screenshots, please visit the "
                            '<a href="https://github.com/wiomoc/pretix-sumup-payment" target="_blank">project\'s GitHub repository</a>.</i>'
                        ),
                        widget=forms.CheckboxInput(
                            attrs={
                                "data-checkbox-dependency": "#id_payment_sumup_enable_apms",
                            }
                        ),
                    ),
                ),
                (
                    "google_pay_merchant_id",
                    forms.CharField(
                        label=_("Google Pay Merchant ID"),
                        required=False,
                        help_text=_(
                            "The Merchant ID for Google Pay. Must be between 12-18 characters long."
                        ),
                        min_length=12,
                        max_length=18,
                        disabled=False,
                        widget=forms.TextInput(
                            attrs={
                                "data-checkbox-dependency": "#id_payment_sumup_enable_google_pay"
                            }
                        ),
                    ),
                ),
            ]
            + list(super().settings_form_fields.items())
        )
        d.move_to_end("_enabled", last=False)
        return d

    def settings_form_clean(self, cleaned_data: dict):
        cleaned_data = super().settings_form_clean(cleaned_data)
        errors = {}

        raw_access_token = cleaned_data.get("payment_sumup_access_token")
        access_token = raw_access_token
        if access_token == SECRET_REDACTED:
            access_token = self.settings.get("access_token")

        if access_token:
            try:
                client = SumUpClient(access_token)
                merchant_name, merchant_code = client.validate_access_token()
                cleaned_data["payment_sumup_merchant_code"] = merchant_code
                cleaned_data["payment_sumup_merchant_name"] = merchant_name
            except Exception as e:
                if raw_access_token != SECRET_REDACTED:
                    errors["payment_sumup_access_token"] = _(
                        "Invalid API key: {}"
                    ).format(str(e))

        apms_enabled = cleaned_data.get("payment_sumup_enable_apms", False)
        enable_google_pay = (
            cleaned_data.get("payment_sumup_enable_google_pay", False) and apms_enabled
        )

        if (
            cleaned_data.get("payment_sumup_enable_google_pay", False)
            and not apms_enabled
        ):
            errors["payment_sumup_enable_google_pay"] = _(
                "Google Pay requires Alternative Payment Methods to be enabled first."
            )

        if enable_google_pay:
            merchant_id = cleaned_data.get("payment_sumup_google_pay_merchant_id")
            merchant_name = cleaned_data.get("payment_sumup_merchant_name")

            if not merchant_id:
                errors["payment_sumup_google_pay_merchant_id"] = _(
                    "Google Pay Merchant ID is required when Google Pay is enabled."
                )

            if not merchant_name or merchant_name == "-":
                errors["payment_sumup_merchant_name"] = _(
                    "Merchant Name is required when Google Pay is enabled. "
                    "Please input your API key again in order to retrieve your Merchant Name."
                )

        if errors:
            raise forms.ValidationError(errors)

        return cleaned_data

    def is_allowed(self, request: HttpRequest, total: Decimal = None):
        if total is None:
            return True
        return total >= 1

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        payment_id = payment.local_id
        order = payment.order
        event = order.event

        has_valid_checkout = self._synchronize_payment_status(payment)
        if has_valid_checkout:
            return

        try:
            merchant_code = self.settings.get("merchant_code")
            access_token = self.settings.get("access_token")
            client = SumUpClient(access_token, merchant_code=merchant_code)

            checkout_params = {
                "checkout_reference": f"{event.slug}/{order.code}/{payment_id}",
                "amount": payment.amount,
                "currency": event.currency,
                "description": f"{event.name} #{order.code}",
                "return_url": build_absolute_uri(
                    event,
                    "plugins:pretix_sumup:checkout_event",
                    kwargs={"payment": payment.pk},
                ),
            }

            if self.settings.get("enable_apms", as_type=bool, default=False):
                checkout_params["redirect_url"] = build_absolute_uri(
                    event,
                    "plugins:pretix_sumup:return",
                    kwargs={
                        "order": order.code,
                        "payment": payment.pk,
                        "hash": order.tagged_secret("plugins:pretix_sumup"),
                    },
                )

            checkout_id = client.create_checkout(**checkout_params)

            info_data = payment.info_data
            info_data["sumup_checkout_id"] = checkout_id
            payment.info_data = info_data
            payment.save()

            log_payment_initiation(
                logger, order.code, payment_id, payment.amount, event.currency
            )
        except Exception as err:
            internal_exception_message = f"Error while creating SumUp checkout: {err}"
            payment.fail(info={"error": internal_exception_message})
            logger.exception(internal_exception_message)
            raise PaymentException(_("Error while creating SumUp checkout"))

    def checkout_confirm_render(self, request: HttpRequest, **kwargs):
        return _(
            "After confirmation you will be redirected to SumUp to complete the payment."
        )

    def payment_form_render(self, request: HttpRequest, **kwargs):
        return self.checkout_confirm_render(request, **kwargs)

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        checkout_id = payment.info_data.get("sumup_checkout_id")
        if checkout_id is None:
            return ""

        self._synchronize_payment_status(payment)

        csp_nonce = get_random_string(10)
        request.__dict__["sumup_csp_nonce"] = csp_nonce

        enable_google_pay = self.settings.get(
            "enable_google_pay", as_type=bool, default=False
        )
        request.__dict__["sumup_enable_google_pay"] = enable_google_pay

        if (
            payment.state == OrderPayment.PAYMENT_STATE_PENDING
            or payment.state == OrderPayment.PAYMENT_STATE_FAILED
        ):
            context = {
                "checkout_id": checkout_id,
                "email": payment.order.email,
                "retry": payment.state == OrderPayment.PAYMENT_STATE_FAILED,
                "locale": self._get_sumup_locale(request),
                "csp_nonce": csp_nonce,
                "enable_google_pay": enable_google_pay,
                "google_pay_merchant_id": self.settings.get("google_pay_merchant_id"),
                "merchant_name": self.settings.get("merchant_name"),
            }
        elif payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED:
            context = {"reload": True, "csp_nonce": csp_nonce}
        else:
            return ""

        return get_template("pretix_sumup/payment_widget.html").render(context)

    def payment_is_valid_session(self, request: HttpRequest):
        return True

    def cancel_payment(self, payment: OrderPayment):
        checkout_id = payment.info_data.get("sumup_checkout_id")
        if checkout_id:
            try:
                access_token = self.settings.get("access_token")
                client = SumUpClient(access_token)
                client.cancel_checkout(checkout_id)
            except Exception as err:
                logger.warning(f"Error while canceling SumUp checkout: {err}")
        super().cancel_payment(payment)

    def payment_refund_supported(self, payment: OrderPayment):
        self._synchronize_payment_status(payment)
        return payment.info_data.get("sumup_transaction") is not None

    def payment_partial_refund_supported(self, payment: OrderPayment):
        self._synchronize_payment_status(payment)
        return payment.info_data.get("sumup_transaction") is not None

    def execute_refund(self, refund: OrderRefund):
        payment = refund.payment
        transaction = payment.info_data.get("sumup_transaction")
        if not transaction:
            logger.exception(
                "Error while refunding sumup transaction. No transaction found"
            )
            raise PaymentException(_("Error while refunding SumUp transaction"))
        try:
            access_token = self.settings.get("access_token")
            merchant_code = self.settings.get("merchant_code")
            client = SumUpClient(access_token, merchant_code=merchant_code)
            client.refund_transaction(
                transaction_id=transaction["id"],
                amount=float(refund.amount),
            )
            refund.done()
        except Exception as err:
            logger.exception(f"Error while refunding SumUp transaction: {err}")
            refund.state = OrderRefund.REFUND_STATE_FAILED
            refund.save(update_fields=["state"])
            raise PaymentException(_("Error while refunding SumUp transaction"))

        self._try_synchronize_transaction(payment, transaction["id"])

    def render_invoice_text(self, order: Order, payment: OrderPayment):
        transaction = payment.info_data.get("sumup_transaction")
        if not transaction:
            return ""

        card = transaction.get("card")
        if card:
            payment_info = card.get("type", transaction.get("simple_payment_type", ""))
            entry_mode = transaction.get("entry_mode")
            if entry_mode and entry_mode != "customer entry":
                payment_info += f" {entry_mode.title()}"
            last_4_digits = card.get("last_4_digits")
            if last_4_digits:
                payment_info += f" **** **** **** {last_4_digits}"
        else:
            payment_info = transaction.get("simple_payment_type", "")

        return _("Payed via SumUp\n{}\nAuth code: {}").format(
            payment_info,
            transaction.get("auth_code", ""),
        )

    @staticmethod
    def _render_transaction_control(transaction: dict, receipt_url: str | None = None):
        payment_info = {"receipt_url": receipt_url}
        card = transaction.get("card")
        if card:
            payment_info["payment_type"] = card.get(
                "type", transaction.get("simple_payment_type", "")
            )
            entry_mode = transaction.get("entry_mode")
            if entry_mode and entry_mode != "customer entry":
                payment_info["entry_mode"] = entry_mode.title()
            payment_info["card_last_4_digit"] = card.get("last_4_digits")
        else:
            payment_info["payment_type"] = transaction.get("simple_payment_type", "")

        return get_template("pretix_sumup/control.html").render(payment_info)

    def payment_presale_render(self, payment: OrderPayment):
        transaction = payment.info_data.get("sumup_transaction")
        if not transaction:
            return ""
        return self._render_transaction_control(transaction)

    def payment_control_render(self, order: Order, payment: OrderPayment):
        transaction = payment.info_data.get("sumup_transaction")
        if not transaction:
            return ""
        return self._render_transaction_control(
            transaction, self._build_receipt_url(transaction)
        )

    def refund_control_render(self, request: HttpRequest, refund: OrderRefund):
        if refund.amount != refund.payment.amount:
            return ""
        transaction = refund.payment.info_data.get("sumup_transaction")
        if not transaction:
            return ""
        refund_event_id = next(
            (
                event.get("id")
                for event in transaction.get("events")
                if event.get("type") == "REFUND"
            ),
            None,
        )
        if not refund_event_id:
            return ""
        return self._render_transaction_control(
            transaction, self._build_receipt_url(transaction, event_id=refund_event_id)
        )

    def matching_id(self, payment):
        transaction = payment.info_data.get("sumup_transaction")
        if not transaction:
            return None
        return transaction.get("transaction_code")

    def api_payment_details(self, payment):
        return {"sumup_transaction": payment.info_data.get("sumup_transaction")}

    @staticmethod
    def _build_receipt_url(transaction, event_id: str | None = None):
        merchant_code = transaction.get("merchant_code")
        transaction_code = transaction.get("transaction_code")
        if not merchant_code or not transaction_code:
            return None
        url = f"https://receipts-ng.sumup.com/v0.1/receipts/{transaction_code}?mid={merchant_code}&format=pdf"
        if event_id:
            url += f"&tx_event_id={event_id}"
        return url

    def _synchronize_payment_status(self, payment: OrderPayment, force: bool = False):
        checkout_id = payment.info_data.get("sumup_checkout_id")
        if not checkout_id:
            return False
        if not force:
            if (
                payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED
                and payment.info_data.get("sumup_transaction") is not None
            ):
                return True

        access_token = self.settings.get("access_token")
        client = SumUpClient(access_token)

        try:
            checkout = client.get_checkout(checkout_id)
        except Exception as err:
            logger.exception(
                "Error while synchronizing SumUp checkout",
                extra={
                    "checkout_id": checkout_id,
                    "order_code": payment.order.code,
                },
            )
            raise PaymentException(_("Error while synchronizing SumUp checkout"))

        if checkout["status"] == "PAID":
            if not payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED:
                payment.confirm()

            transaction_id = next(
                (
                    transaction.get("id")
                    for transaction in checkout["transactions"]
                    if transaction["status"] == "SUCCESSFUL"
                ),
                None,
            )
            if transaction_id is not None:
                self._try_synchronize_transaction(payment, transaction_id)
                log_payment_confirmation(
                    logger,
                    payment.order.code,
                    payment.pk,
                    transaction_id,
                )
            return True

        elif checkout["status"] == "PENDING":
            if not payment.state == OrderPayment.PAYMENT_STATE_PENDING:
                payment.state = OrderPayment.PAYMENT_STATE_PENDING
                payment.save(update_fields=["state"])
            return True

        elif checkout["status"] == "FAILED":
            if not payment.state == OrderPayment.PAYMENT_STATE_FAILED:
                payment.fail()
            return False

    def _try_synchronize_transaction(self, payment: OrderPayment, transaction_id: str):
        access_token = self.settings.get("access_token")
        merchant_code = self.settings.get("merchant_code")
        client = SumUpClient(access_token, merchant_code=merchant_code)

        try:
            transaction = client.get_transaction(transaction_id)
            info_data = payment.info_data
            info_data["sumup_transaction"] = transaction
            payment.info_data = info_data
            payment.save()
            logger.info(
                "Transaction data synchronized",
                extra={
                    "transaction_id": transaction_id,
                    "order_code": payment.order.code,
                },
            )
        except Exception as err:
            logger.warning(
                "Error while synchronizing SumUp transaction",
                extra={
                    "transaction_id": transaction_id,
                    "order_code": payment.order.code,
                    "error": str(err),
                },
            )

    @staticmethod
    def _get_sumup_locale(request):
        language = get_language_from_request(request)
        if language == "de" or language == "de-informal":
            return "de-DE"
        elif language == "fr":
            return "fr-FR"
        return "en-GB"
