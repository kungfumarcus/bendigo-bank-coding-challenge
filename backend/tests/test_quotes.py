import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import LoadedConfig, check_settings, load_config
from app.factory import create_app
from app.quotes.service import decimal_places
from tests.conftest import GOOD_REPLY, KEY, VALID_BODY, ClientFactory, make_settings


def post_raw(client: TestClient, body: bytes) -> httpx2.Response:
    return client.post("/api/v1/quotes", content=body, headers={"content-type": "application/json"})


async def good_vendor(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=GOOD_REPLY)


# --- Success ---


def test_quote_passes_through_vendor_values_exactly(client_for: ClientFactory) -> None:
    response = client_for(good_vendor).post("/api/v1/quotes", json=VALID_BODY)
    assert response.status_code == 200
    assert response.text == '{"quoteId":"q-1","commissionRate":0.015,"totalCommission":"15.00"}'


def test_vendor_exponent_is_written_out_in_total(client_for: ClientFactory) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b'{"quoteId":"q-1","commissionRate":0.015,"totalCommission":1.5E+3}'
        )

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.json()["totalCommission"] == "1500"


def test_vendor_digits_survive_beyond_float_precision(client_for: ClientFactory) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"quoteId":"q","commissionRate":0.12345678901234567890123,'
            b'"totalCommission":1.12345678901234567890123}',
        )

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert '"commissionRate":0.12345678901234567890123' in response.text
    assert '"totalCommission":"1.12345678901234567890123"' in response.text


def test_vendor_gets_key_and_amount_as_exact_json_number(client_for: ClientFactory) -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=GOOD_REPLY)

    response = post_raw(
        client_for(handler), b'{"loanAmount":"1234567.89","loanTermInMonths":12,"riskBand":"LOW"}'
    )
    assert response.status_code == 200
    assert seen[0].headers["api-key"] == KEY
    assert b'"loanAmount":1234567.89,' in seen[0].content


def test_every_response_carries_a_fresh_request_id(client_for: ClientFactory) -> None:
    client = client_for(good_vendor)
    inbound = {"X-Request-ID": "supplied-by-caller"}
    ok = client.get("/api/v1/health", headers=inbound)
    bad = post_raw(client, b"[]")
    assert uuid.UUID(ok.headers["X-Request-ID"]).version == 4
    assert ok.headers["X-Request-ID"] != "supplied-by-caller"
    assert bad.json()["error"]["requestId"] == bad.headers["X-Request-ID"]


def test_status_reports_limits(client_for: ClientFactory) -> None:
    body = client_for(good_vendor).get("/api/v1/quotes/status").json()
    assert body == {
        "available": True,
        "requestTimeoutSeconds": 15,
        "limits": {
            "loanAmountMin": 1,
            "loanAmountMax": 10000000,
            "loanAmountMaxDecimals": 2,
            "loanTermMonthsMin": 1,
            "loanTermMonthsMax": 360,
        },
    }


# --- Validation ---


def body_with(**changes: Any) -> bytes:
    body = {"loanAmount": '"1000"', "loanTermInMonths": "12", "riskBand": '"LOW"', **changes}
    return ("{" + ",".join(f'"{k}":{v}' for k, v in body.items()) + "}").encode()


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b'{"loanTermInMonths":12,"riskBand":"LOW"}', [("loanAmount", "REQUIRED")]),
        (
            b"{}",
            [
                ("loanAmount", "REQUIRED"),
                ("loanTermInMonths", "REQUIRED"),
                ("riskBand", "REQUIRED"),
            ],
        ),
        (body_with(extra="1"), [("extra", "UNKNOWN_FIELD")]),
        (body_with(loanAmount="1000"), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount="true"), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount="null"), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='""'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"abc"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"NaN"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"Infinity"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"1e3"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"+1"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"1."'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='".5"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"1_000"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='" 1"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"1\\n"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"١٢"'), [("loanAmount", "NOT_A_NUMBER")]),
        (body_with(loanAmount='"1.234"'), [("loanAmount", "TOO_MANY_DECIMALS")]),
        (body_with(loanAmount='"0.999"'), [("loanAmount", "TOO_MANY_DECIMALS")]),
        (body_with(loanAmount='"0"'), [("loanAmount", "OUT_OF_RANGE")]),
        (body_with(loanAmount='"-5"'), [("loanAmount", "OUT_OF_RANGE")]),
        (body_with(loanAmount='"10000000.01"'), [("loanAmount", "OUT_OF_RANGE")]),
        (body_with(loanAmount=f'"{"9" * 5000}"'), [("loanAmount", "OUT_OF_RANGE")]),
        (body_with(loanTermInMonths="12.5"), [("loanTermInMonths", "INVALID_VALUE")]),
        (body_with(loanTermInMonths="12.0"), [("loanTermInMonths", "INVALID_VALUE")]),
        (body_with(loanTermInMonths="1e2"), [("loanTermInMonths", "INVALID_VALUE")]),
        (body_with(loanTermInMonths='"12"'), [("loanTermInMonths", "INVALID_VALUE")]),
        (body_with(loanTermInMonths="true"), [("loanTermInMonths", "INVALID_VALUE")]),
        (body_with(loanTermInMonths="0"), [("loanTermInMonths", "OUT_OF_RANGE")]),
        (body_with(loanTermInMonths="361"), [("loanTermInMonths", "OUT_OF_RANGE")]),
        (body_with(loanTermInMonths="9" * 4300), [("loanTermInMonths", "OUT_OF_RANGE")]),
        (body_with(riskBand='"low"'), [("riskBand", "INVALID_VALUE")]),
        (body_with(riskBand="1"), [("riskBand", "INVALID_VALUE")]),
        (body_with(riskBand="[]"), [("riskBand", "INVALID_VALUE")]),
        # A shape error on one field hides bound errors on the others.
        (body_with(loanAmount='"0"', riskBand='"NOPE"'), [("riskBand", "INVALID_VALUE")]),
        # Both bound errors are reported together.
        (
            body_with(loanAmount='"0"', loanTermInMonths="0"),
            [("loanAmount", "OUT_OF_RANGE"), ("loanTermInMonths", "OUT_OF_RANGE")],
        ),
    ],
)
def test_invalid_input_returns_field_errors(
    client_for: ClientFactory, body: bytes, expected: list[tuple[str, str]]
) -> None:
    response = post_raw(client_for(good_vendor), body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    actual = [(item["field"], item["code"]) for item in error["fields"]]
    assert sorted(actual) == sorted(expected)


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b"null",
        b'"text"',
        b"[" * 100000,
        body_with(loanAmount="NaN"),
        body_with(loanAmount="Infinity"),
        # Numbers the JSON decoder itself rejects as too large.
        body_with(loanTermInMonths="9" * 4301),
        body_with(loanAmount="1e99999999999999999999"),
    ],
)
def test_unparseable_body_returns_400_without_fields(
    client_for: ClientFactory, body: bytes
) -> None:
    response = post_raw(client_for(good_vendor), body)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert "fields" not in error


def test_form_encoded_body_returns_400(client_for: ClientFactory) -> None:
    response = client_for(good_vendor).post("/api/v1/quotes", data={"loanAmount": "1"})
    assert response.status_code == 400


def test_json_with_charset_is_accepted(client_for: ClientFactory) -> None:
    response = client_for(good_vendor).post(
        "/api/v1/quotes",
        content=json.dumps(VALID_BODY),
        headers={"content-type": "application/json; charset=utf-8"},
    )
    assert response.status_code == 200


def test_validation_errors_do_not_echo_values(client_for: ClientFactory) -> None:
    response = post_raw(client_for(good_vendor), body_with(riskBand='"SECRET-VALUE"'))
    assert "SECRET-VALUE" not in response.text


@pytest.mark.parametrize(
    ("value", "places"),
    [
        ("1", 0),
        ("1.5", 1),
        ("1.50", 1),
        ("1.100", 1),
        ("1.234", 3),
        ("1E+3", 0),
        ("1.5e1", 0),
        ("0.000", 0),
        ("1e-3", 3),
    ],
)
def test_decimal_places(value: str, places: int) -> None:
    assert decimal_places(Decimal(value)) == places


# --- Config ---


def unavailable_client(config: LoadedConfig) -> TestClient:
    return TestClient(create_app(config), raise_server_exceptions=False)


def test_missing_key_makes_quotes_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.delenv("VENDOR_API_KEY", raising=False)
    monkeypatch.setenv("VENDOR_QUOTE_URL", "http://vendor.test/quotes")
    config = load_config()
    assert config.settings is None
    assert any(problem.startswith("VENDOR_API_KEY") for problem in config.problems)

    client = unavailable_client(config)
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/quotes/status").json() == {
        "available": False,
        "requestTimeoutSeconds": None,
        "limits": None,
    }
    # The availability check runs before validation, so even a bad body gets this code.
    for response in (client.post("/api/v1/quotes", json=VALID_BODY), post_raw(client, b"nope")):
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "QUOTES_UNAVAILABLE"


def test_config_problems_never_include_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VENDOR_QUOTE_URL", "http://vendor.test/quotes")
    monkeypatch.setenv("VENDOR_API_KEY", "bad\nsecret")
    problems = load_config().problems
    assert problems and not any("secret" in problem for problem in problems)


@pytest.mark.parametrize(
    "env",
    [
        {"VENDOR_QUOTE_URL": "ftp://vendor.test"},
        {"VENDOR_QUOTE_URL": "http://vendor:abc/quotes"},
        {"VENDOR_QUOTE_URL": "http://vendor:99999/quotes"},
        {"VENDOR_QUOTE_URL": "http://:9000/quotes"},
        {"VENDOR_QUOTE_URL": "http://ve ndor/quotes"},
        {"VENDOR_QUOTE_URL": "not a url"},
        {"VENDOR_API_KEY": "   "},
        {"VENDOR_API_KEY": "café"},
        {"VENDOR_TIMEOUT_SECONDS": "0"},
        {"VENDOR_TIMEOUT_SECONDS": "nan"},
        {"VENDOR_MAX_RETRIES": "1.5"},
        {"VENDOR_MAX_RETRIES": "-1"},
        {"LOAN_AMOUNT_MIN": "0"},
        {"LOAN_AMOUNT_MAX": "Infinity"},
        {"LOAN_AMOUNT_MAX_DECIMALS": "0"},
        {"LOAN_TERM_MONTHS_MIN": "0"},
        {"LOAN_AMOUNT_MIN": "5", "LOAN_AMOUNT_MAX": "2"},
        {"LOAN_TERM_MONTHS_MIN": "5", "LOAN_TERM_MONTHS_MAX": "2"},
        {"FRONTEND_REQUEST_TIMEOUT_SECONDS": "6"},
    ],
)
def test_invalid_config_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, env: dict[str, str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VENDOR_QUOTE_URL", "http://vendor.test/quotes")
    monkeypatch.setenv("VENDOR_API_KEY", KEY)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    config = load_config()
    assert config.settings is None
    assert config.problems


def test_default_settings_have_no_problems() -> None:
    assert (
        check_settings(make_settings(vendor_timeout_seconds=3, vendor_retry_backoff_ms=250)) == []
    )


# --- Vendor retry ---


def test_5xx_then_success_returns_quote(client_for: ClientFactory) -> None:
    replies = [httpx.Response(503), httpx.Response(200, content=GOOD_REPLY)]

    async def handler(_: httpx.Request) -> httpx.Response:
        return replies.pop(0)

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.status_code == 200
    assert replies == []


@pytest.mark.parametrize("status", [500, 503, 504])
def test_persistent_5xx_returns_vendor_unavailable(client_for: ClientFactory, status: int) -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, content=b"internal vendor detail")

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "VENDOR_UNAVAILABLE"
    assert "internal vendor detail" not in response.text
    assert calls == 2


def test_connection_error_returns_vendor_unavailable(client_for: ClientFactory) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "VENDOR_UNAVAILABLE"


def test_persistent_timeout_returns_vendor_timeout(client_for: ClientFactory) -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(5)
        return httpx.Response(200, content=GOOD_REPLY)

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "VENDOR_TIMEOUT"
    assert calls == 2


def test_401_is_not_retried(client_for: ClientFactory) -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, content=b'{"error":"Unauthorized"}')

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "VENDOR_AUTH_FAILED"
    assert calls == 1


def test_redirect_is_not_followed(client_for: ClientFactory) -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"location": "http://elsewhere.test/"})

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.json()["error"]["code"] == "VENDOR_BAD_RESPONSE"
    assert calls == 1


# --- Bad response ---


@pytest.mark.parametrize(
    ("status", "content"),
    [
        (200, b"not json"),
        (200, b"[]"),
        (200, b'{"commissionRate":0.015,"totalCommission":15}'),
        (200, b'{"quoteId":1,"commissionRate":0.015,"totalCommission":15}'),
        (200, b'{"quoteId":"","commissionRate":0.015,"totalCommission":15}'),
        (200, b'{"quoteId":"q","commissionRate":0.015,"totalCommission":"15"}'),
        (200, b'{"quoteId":"q","totalCommission":15}'),
        (200, b'{"quoteId":"q","commissionRate":0.015}'),
        (200, b'{"quoteId":"q","commissionRate":"0.015","totalCommission":15}'),
        (200, b'{"quoteId":"q","commissionRate":true,"totalCommission":15}'),
        (200, b'{"quoteId":"q","commissionRate":-1,"totalCommission":15}'),
        (200, b'{"quoteId":"q","commissionRate":0.015,"totalCommission":NaN}'),
        (200, b'{"quoteId":"q","commissionRate":0.015,"totalCommission":Infinity}'),
        (200, b'{"quoteId":"q","commissionRate":0.015,"totalCommission":1e99999999999999999999}'),
        (201, GOOD_REPLY),
        (400, b"{}"),
        (408, b"{}"),
        (429, b"{}"),
    ],
)
def test_contract_breaking_reply_returns_bad_response(
    client_for: ClientFactory, status: int, content: bytes
) -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, content=content)

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "VENDOR_BAD_RESPONSE"
    assert calls == 1


def test_undecodable_body_returns_bad_response(client_for: ClientFactory) -> None:
    class NotGzip(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"this is not gzip"

    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, headers={"content-encoding": "gzip"}, stream=NotGzip())

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "VENDOR_BAD_RESPONSE"
    assert calls == 1


# --- Unexpected error ---


def test_unhandled_exception_returns_internal_error(client_for: ClientFactory) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise RuntimeError("secret internal detail")

    response = client_for(handler).post("/api/v1/quotes", json=VALID_BODY)
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error["requestId"] == response.headers["X-Request-ID"]
    assert "secret" not in response.text
