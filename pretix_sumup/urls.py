import os

from django.urls import re_path

from pretix_sumup.admin.diagnostics import (
    force_payment_sync,
    recheck_payment,
    reconcile_view,
    retry_webhook,
    webhook_event_detail,
    webhook_event_list,
)
from pretix_sumup.views.return_view import ReturnView
from pretix_sumup.webhooks.views import checkout_event

event_patterns = [
    re_path(
        r"^sumup/checkout_event/(?P<payment>[^/]+)$",
        checkout_event,
        name="checkout_event",
    ),
    re_path(
        r"^sumup/return/(?P<order>[^/]+)/(?P<hash>[^/]+)/(?P<payment>[0-9]+)/$",
        ReturnView.as_view(),
        name="return",
    ),
    re_path(
        r"^sumup/webhook-events/$",
        webhook_event_list,
        name="webhook_event_list",
    ),
    re_path(
        r"^sumup/webhook-events/(?P<event_id>\d+)/$",
        webhook_event_detail,
        name="webhook_event_detail",
    ),
    re_path(
        r"^sumup/webhook-events/(?P<event_id>\d+)/retry/$",
        retry_webhook,
        name="retry_webhook",
    ),
    re_path(
        r"^sumup/payments/(?P<payment_id>\d+)/recheck/$",
        recheck_payment,
        name="recheck_payment",
    ),
    re_path(
        r"^sumup/payments/(?P<payment_id>\d+)/force-sync/$",
        force_payment_sync,
        name="force_payment_sync",
    ),
    re_path(
        r"^sumup/reconcile/$",
        reconcile_view,
        name="reconcile",
    ),
]

if os.environ.get("PRETIX_DEBUG"):
    from pretix_sumup.webhooks.views import (
        debug_fake_webhook,
        debug_fake_webhook_failed,
    )

    event_patterns.extend([
        re_path(
            r"^sumup/debug/fake-webhook/(?P<payment>\d+)/$",
            debug_fake_webhook,
            name="debug_fake_webhook",
        ),
        re_path(
            r"^sumup/debug/fake-webhook-failed/(?P<payment>\d+)/$",
            debug_fake_webhook_failed,
            name="debug_fake_webhook_failed",
        ),
    ])
