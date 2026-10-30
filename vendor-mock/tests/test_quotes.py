import json
import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.factory import create_app
from app.quotes.pricing import total_commission

KEY = "test-key"
VALID_BODY = {"loanAmount": 1000, "loanTermInMonths": 12, "riskBand": "MEDIUM"}


def make_client(**overrides: Any) -> TestClient:
    values: dict[str, Any] = {
        "vendor_api_key": KEY,
        "failure_rate": 0,
        "slow_response_rate": 0,
        "commission_rate_low": Decimal("0.01"),
        "commission_rate_medium": Decimal("0.015"),
        "commission_rate_high": Decimal("0.0225"),
    }
    return TestClient(create_app(Settings(_env_file=None, **{**values, **overrides})))


@pytest.mark.parametrize("headers", [{}, {"api-key": "wrong"}, {"api-key": "wé"}])
def test_missing_or_wrong_key_returns_401(headers: dict[str, str]) -> None:
    encoded = {name.encode(): value.encode("latin-1") for name, value in headers.items()}
    response = make_client().post("/commission-quotes", json=VALID_BODY, headers=encoded)
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


def test_key_sent_twice_returns_401() -> None:
    response = make_client().post(
        "/commission-quotes", json=VALID_BODY, headers=[("api-key", KEY), ("api-key", KEY)]
    )
    assert response.status_code == 401


def test_right_key_returns_quote() -> None:
    response = make_client().post("/commission-quotes", json=VALID_BODY, headers={"api-key": KEY})
    assert response.status_code == 200
    body = response.json()
    assert uuid.UUID(body["quoteId"]).version == 4
    assert body["commissionRate"] == 0.015
    assert body["totalCommission"] == 15


def test_wrong_key_with_invalid_body_returns_401() -> None:
    response = make_client().post(
        "/commission-quotes", content=b"not json", headers={"api-key": "wrong"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b"{}",
        b'{"loanAmount": "1000", "loanTermInMonths": 12, "riskBand": "LOW"}',
        b'{"loanAmount": true, "loanTermInMonths": 12, "riskBand": "LOW"}',
        b'{"loanAmount": NaN, "loanTermInMonths": 12, "riskBand": "LOW"}',
        b'{"loanAmount": Infinity, "loanTermInMonths": 12, "riskBand": "LOW"}',
        b'{"loanAmount": 0, "loanTermInMonths": 12, "riskBand": "LOW"}',
        b'{"loanAmount": 1000, "loanTermInMonths": 12.5, "riskBand": "LOW"}',
        b'{"loanAmount": 1000, "loanTermInMonths": 12.0, "riskBand": "LOW"}',
        b'{"loanAmount": 1000, "loanTermInMonths": true, "riskBand": "LOW"}',
        b'{"loanAmount": 1000, "loanTermInMonths": 12, "riskBand": "low"}',
        b'{"loanAmount": 1000, "loanTermInMonths": 12, "riskBand": "LOW", "extra": 1}',
        b'{"loanAmount": 1000, "loanTermInMonths": 12, "riskBand": []}',
        b'{"loanAmount": 1000, "loanTermInMonths": 12, "riskBand": {}}',
        b'{"loanAmount": 1000, "loanTermInMonths": 12, "riskBand": 1}',
        b'{"loanAmount": 1e999999, "loanTermInMonths": 12, "riskBand": "LOW"}',
        b'{"loanAmount": 1e9999999, "loanTermInMonths": 12, "riskBand": "LOW"}',
        b'{"loanAmount": 1e99999999999999999999, "loanTermInMonths": 12, "riskBand": "LOW"}',
    ],
)
def test_invalid_body_returns_422(body: bytes) -> None:
    response = make_client().post(
        "/commission-quotes",
        content=body,
        headers={"api-key": KEY, "content-type": "application/json"},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["error"], str)


def test_non_json_content_type_returns_422() -> None:
    response = make_client().post(
        "/commission-quotes",
        content=json.dumps(VALID_BODY),
        headers={"api-key": KEY, "content-type": "text/plain"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("band", "rate", "total"),
    [("LOW", 0.01, 10), ("MEDIUM", 0.015, 15), ("HIGH", 0.0225, 22.5)],
)
def test_rate_per_band(band: str, rate: float, total: float) -> None:
    response = make_client().post(
        "/commission-quotes", json={**VALID_BODY, "riskBand": band}, headers={"api-key": KEY}
    )
    assert response.json()["commissionRate"] == rate
    assert response.json()["totalCommission"] == total


@pytest.mark.parametrize(
    ("amount", "rate", "expected"),
    [
        # 0.125 and 0.135 would round the wrong way half-even or via a float.
        ("12.5", "0.01", "0.13"),
        ("13.5", "0.01", "0.14"),
        ("1.005", "1", "1.01"),
    ],
)
def test_total_rounds_half_up_to_cents(amount: str, rate: str, expected: str) -> None:
    assert total_commission(Decimal(amount), Decimal(rate)) == Decimal(expected)


def test_amounts_are_raw_json_numbers() -> None:
    response = make_client().post("/commission-quotes", json=VALID_BODY, headers={"api-key": KEY})
    assert '"commissionRate":0.015' in response.text
    assert '"totalCommission":15.00' in response.text


def test_failure_rate_one_always_returns_5xx() -> None:
    client = make_client(failure_rate=1)
    for _ in range(20):
        response = client.post("/commission-quotes", json=VALID_BODY, headers={"api-key": KEY})
        assert response.status_code in (500, 502, 503)


@pytest.mark.parametrize(
    "overrides",
    [
        {"vendor_api_key": "   "},
        {"failure_rate": 1.5},
        {"failure_rate": float("nan")},
        {"commission_rate_low": Decimal("2")},
        {"slow_response_delay_seconds": -1},
    ],
)
def test_invalid_config_refuses_to_load(overrides: dict[str, Any]) -> None:
    values = {"vendor_api_key": KEY, **overrides}
    with pytest.raises(ValueError):
        Settings(_env_file=None, **values)
