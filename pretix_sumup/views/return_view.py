import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views.generic import View
from pretix.base.models import Order, OrderPayment
from pretix.helpers.http import redirect_to_url
from pretix.multidomain.urlreverse import eventreverse

from pretix_sumup.payment import SumUp

logger = logging.getLogger("pretix.plugins.sumup.views")


class ReturnView(View):
    """Handle customer return after SumUp payment completion."""

    def get(self, request, *args, **kwargs):
        try:
            order = get_object_or_404(
                Order, code=kwargs.get("order"), event=request.event
            )
            payment = get_object_or_404(
                OrderPayment, pk=kwargs.get("payment"), order=order
            )

            if kwargs.get("hash") != order.tagged_secret("plugins:pretix_sumup"):
                messages.error(
                    request,
                    _(
                        "Sorry, there was an error in the payment process. "
                        "Please check the link in your emails to continue."
                    ),
                )
                return redirect_to_url(
                    eventreverse(request.event, "presale:event.index")
                )

            provider = SumUp(request.event)
            provider._synchronize_payment_status(payment)

            return redirect_to_url(
                eventreverse(
                    request.event,
                    "presale:event.order",
                    kwargs={"order": order.code, "secret": order.secret},
                )
                + ("?paid=yes" if order.status == Order.STATUS_PAID else "")
            )

        except Exception:
            logger.exception("Error in ReturnView for payment %s", kwargs.get("payment"))
            messages.error(
                request,
                _(
                    "Sorry, there was an error in the payment process. "
                    "Please check the link in your emails to continue."
                ),
            )
            return redirect_to_url(eventreverse(request.event, "presale:event.index"))
