from django.dispatch import receiver
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from pretix.base.middleware import _merge_csp, _parse_csp, _render_csp
from pretix.base.signals import register_payment_providers
from pretix.control.signals import nav_event
from pretix.presale.signals import process_response


@receiver(register_payment_providers, dispatch_uid="sumup_payment")
def register_payment_provider(sender, **kwargs):
    from .payment import SumUp

    return SumUp


@receiver(nav_event, dispatch_uid="sumup_nav_event")
def register_admin_nav(sender, request=None, **kwargs):
    if not hasattr(request, "event"):
        return []

    url = reverse(
        "plugins:pretix_sumup:webhook_event_list",
        kwargs={
            "organizer": request.event.organizer.slug,
            "event": request.event.slug,
        },
    )

    return [
        {
            "label": _("SumUp webhooks"),
            "url": url,
            "parent": "settings",
            "active": False,
        }
    ]


@receiver(process_response, dispatch_uid="sumup_csp_middleware_resp")
def signal_process_response(
    sender, request: HttpRequest, response: HttpResponse, **kwargs
):
    sumup_csp_nonce = request.__dict__.get("sumup_csp_nonce")
    if not sumup_csp_nonce:
        return response

    enable_google_pay = bool(request.__dict__.get("sumup_enable_google_pay", False))

    if "Content-Security-Policy" in response:
        h = _parse_csp(response["Content-Security-Policy"])
    else:
        h = {}

    csps = {
        "default-src": ["*.sumup.com"],
        "script-src": [
            f"'nonce-{sumup_csp_nonce}'",
            "*.sumup.com",
        ],
        "style-src": [
            f"'nonce-{sumup_csp_nonce}'",
            "*.sumup.com",
        ],
        "frame-src": ["*"],
        "img-src": [
            "*.sumup.com",
            "data:",
        ],
        "connect-src": [
            "*.sumup.com",
            "cdn.optimizely.com",
        ],
    }

    if enable_google_pay:
        csps["script-src"].extend([
            "'unsafe-inline'",
            "pay.google.com",
            "apis.google.com",
            "*.gstatic.com",
            "*.google.com",
        ])
        csps["style-src"].extend([
            "'unsafe-inline'",
            "pay.google.com",
            "*.gstatic.com",
        ])
        csps["img-src"].extend([
            "pay.google.com",
            "*.gstatic.com",
            "*.googleusercontent.com",
        ])
        csps["connect-src"].extend([
            "pay.google.com",
            "apis.google.com",
        ])

    _merge_csp(h, csps)

    if h:
        response["Content-Security-Policy"] = _render_csp(h)

    return response
