from collections.abc import Callable, Coroutine, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import LoadedConfig, Settings
from app.factory import create_app

KEY = "test-key"
VALID_BODY = {"loanAmount": 1000, "loanTermInMonths": 12, "riskBand": "MEDIUM"}
GOOD_REPLY = b'{"quoteId":"q-1","commissionRate":0.015,"totalCommission":15.00}'

Handler = Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]
ClientFactory = Callable[[Handler], TestClient]


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "vendor_quote_url": "http://vendor.test/commission-quotes",
        "vendor_api_key": KEY,
        "vendor_timeout_seconds": 0.05,
        "vendor_max_retries": 1,
        "vendor_retry_backoff_ms": 0,
        "frontend_request_timeout_seconds": 15,
        "loan_amount_min": 1,
        "loan_amount_max": 10000000,
        "loan_amount_max_decimals": 2,
        "loan_term_months_min": 1,
        "loan_term_months_max": 360,
    }
    return Settings(_env_file=None, **{**values, **overrides})


@pytest.fixture
def client_for() -> Iterator[ClientFactory]:
    """Builds a test client whose vendor calls go to the given handler."""
    clients: list[TestClient] = []

    def build(handler: Handler) -> TestClient:
        app = create_app(LoadedConfig(make_settings(), []), httpx.MockTransport(handler))
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.__exit__(None, None, None)
