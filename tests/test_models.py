import json

from pretix_sumup.models.webhook import SumUpWebhookEvent


class TestSumUpWebhookEvent:
    def test_str_with_event_id(self):
        event = SumUpWebhookEvent(
            event_id="evt_001",
            processing_status=SumUpWebhookEvent.ProcessingStatus.PROCESSED,
        )
        assert "evt_001" in str(event)

    def test_str_without_event_id(self):
        event = SumUpWebhookEvent(
            processing_status=SumUpWebhookEvent.ProcessingStatus.PENDING
        )
        result = str(event)
        assert "SumUp webhook" in result
        assert "pending" in result

    def test_get_payload_valid_json(self):
        payload = {"key": "value"}
        event = SumUpWebhookEvent(payload_json=json.dumps(payload))
        assert event.get_payload() == payload

    def test_get_payload_empty(self):
        event = SumUpWebhookEvent(payload_json="")
        assert event.get_payload() == {}

    def test_get_payload_invalid_json(self):
        event = SumUpWebhookEvent(payload_json="not json")
        assert event.get_payload() == {}

    def test_get_headers(self):
        headers = {"Content-Type": "application/json"}
        event = SumUpWebhookEvent(headers_json=json.dumps(headers))
        assert event.get_headers() == headers

    def test_processing_statuses(self):
        assert SumUpWebhookEvent.ProcessingStatus.PENDING == "pending"
        assert SumUpWebhookEvent.ProcessingStatus.PROCESSED == "processed"
        assert SumUpWebhookEvent.ProcessingStatus.FAILED == "failed"
        assert SumUpWebhookEvent.ProcessingStatus.IGNORED == "ignored"
