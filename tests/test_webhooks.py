import json
from unittest.mock import MagicMock, patch

import pytest

from pretix_sumup.models.webhook import SumUpWebhookEvent
from pretix_sumup.webhooks.processor import (
    _check_idempotency,
    record_webhook_event,
)


class TestRecordWebhookEvent:
    @patch("pretix_sumup.webhooks.processor.SumUpWebhookEvent.objects.create")
    def test_record_webhook_event(self, mock_create):
        mock_event = MagicMock()
        mock_event.pk = 1
        mock_create.return_value = mock_event

        mock_request = MagicMock()
        mock_request.body = json.dumps(
            {
                "event_id": "evt_001",
                "event_type": "checkout.paid",
                "checkout_id": "ch_001",
                "transaction_id": "txn_001",
            }
        ).encode()
        mock_request.headers = {"Authorization": "Bearer secret", "Content-Type": "application/json"}

        event = record_webhook_event(mock_request)

        assert event == mock_event
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["event_id"] == "evt_001"
        assert call_kwargs["event_type"] == "checkout.paid"
        assert call_kwargs["sumup_checkout_id"] == "ch_001"
        assert call_kwargs["sumup_transaction_id"] == "txn_001"

        parsed_headers = json.loads(call_kwargs["headers_json"])
        assert "Authorization" not in parsed_headers

    @patch("pretix_sumup.webhooks.processor.SumUpWebhookEvent.objects.create")
    def test_record_webhook_event_empty_body(self, mock_create):
        mock_request = MagicMock()
        mock_request.body = b""
        mock_request.headers = {}

        record_webhook_event(mock_request)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["payload_json"] == "{}"

    @patch("pretix_sumup.webhooks.processor.SumUpWebhookEvent.objects.create")
    def test_record_webhook_event_invalid_json(self, mock_create):
        mock_request = MagicMock()
        mock_request.body = b"not json"
        mock_request.headers = {}

        record_webhook_event(mock_request)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["payload_json"] == "{}"


class TestIdempotency:
    @patch("pretix_sumup.webhooks.processor.SumUpWebhookEvent.objects.filter")
    def test_duplicate_event_id_ignored(self, mock_filter):
        existing_event = MagicMock()
        existing_event.processing_status = SumUpWebhookEvent.ProcessingStatus.PROCESSED

        mock_qs = MagicMock()
        mock_qs.exclude.return_value.first.return_value = existing_event
        mock_filter.return_value = mock_qs

        event = MagicMock()
        event.event_id = "evt_001"
        event.pk = 2

        result = _check_idempotency(event)

        assert result is True
        assert event.processing_status == SumUpWebhookEvent.ProcessingStatus.IGNORED

    @patch("pretix_sumup.webhooks.processor.SumUpWebhookEvent.objects.filter")
    def test_no_duplicate_event(self, mock_filter):
        mock_filter.return_value.exclude.return_value.first.return_value = None

        event = MagicMock()
        event.event_id = "evt_001"

        result = _check_idempotency(event)

        assert result is False

    @patch("pretix_sumup.webhooks.processor.SumUpWebhookEvent.objects.filter")
    def test_no_event_id(self, mock_filter):
        event = MagicMock()
        event.event_id = ""

        result = _check_idempotency(event)

        assert result is False
        mock_filter.assert_not_called()
