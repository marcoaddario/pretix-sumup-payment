import json
import os
from unittest.mock import patch

import pytest


@pytest.fixture
def fixture_path():
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def load_fixture(fixture_path):
    def _load(name):
        path = os.path.join(fixture_path, name)
        with open(path) as f:
            return json.load(f)

    return _load


@pytest.fixture
def webhook_paid_payload(load_fixture):
    return load_fixture("webhook_paid.json")


@pytest.fixture
def webhook_failed_payload(load_fixture):
    return load_fixture("webhook_failed.json")


@pytest.fixture
def webhook_duplicate_payload(load_fixture):
    return load_fixture("webhook_duplicate.json")


@pytest.fixture
def sumup_checkout_paid(load_fixture):
    return load_fixture("sumup_checkout_paid.json")


@pytest.fixture
def sumup_transaction(load_fixture):
    return load_fixture("sumup_transaction.json")


@pytest.fixture
def mock_sumup_client():
    with patch("pretix_sumup.api.client.SumUpClient") as mock:
        yield mock
