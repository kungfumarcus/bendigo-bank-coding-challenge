import asyncio
import hmac
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, NoReturn

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.config import Settings
from app.quotes.pricing import rate_for_band, total_commission

logger = logging.getLogger("vendor_mock")
router = APIRouter()

FIELDS = {"loanAmount", "loanTermInMonths", "riskBand"}
RISK_BANDS = {"LOW", "MEDIUM", "HIGH"}
FAULT_STATUSES = (500, 502, 503)


class InvalidBody(Exception):
    pass


@dataclass(frozen=True)
class QuoteRequest:
    loan_amount: Decimal
    risk_band: str


def _key_is_valid(request: Request, expected: str) -> bool:
    values = request.headers.getlist("api-key")
    if len(values) != 1 or not values[0].isascii():
        return False
    return hmac.compare_digest(values[0].encode(), expected.encode())


def _reject_constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not allowed")


def _parse_body(body: bytes, content_type: str) -> QuoteRequest:
    if content_type.split(";")[0].strip().lower() != "application/json":
        raise InvalidBody("Content-Type must be application/json")
    try:
        data: Any = json.loads(body, parse_float=Decimal, parse_constant=_reject_constant)
    except (ValueError, ArithmeticError, RecursionError) as error:
        raise InvalidBody("Body is not valid JSON") from error
    if not isinstance(data, dict):
        raise InvalidBody("Body must be a JSON object")
    if set(data) != FIELDS:
        raise InvalidBody("Body must hold exactly loanAmount, loanTermInMonths and riskBand")

    amount, term, risk_band = data["loanAmount"], data["loanTermInMonths"], data["riskBand"]
    if isinstance(amount, bool) or not isinstance(amount, int | Decimal) or amount <= 0:
        raise InvalidBody("loanAmount must be a number greater than 0")
    if isinstance(term, bool) or not isinstance(term, int) or term <= 0:
        raise InvalidBody("loanTermInMonths must be an integer greater than 0")
    if not isinstance(risk_band, str) or risk_band not in RISK_BANDS:
        raise InvalidBody("riskBand must be LOW, MEDIUM or HIGH")
    return QuoteRequest(Decimal(amount), risk_band)


def _quote_response(rate: Decimal, total: Decimal) -> Response:
    # Written by hand so both amounts are JSON numbers with no float conversion.
    body = f'{{"quoteId":"{uuid.uuid4()}","commissionRate":{rate},"totalCommission":{total}}}'
    return Response(content=body, media_type="application/json")


async def _handle(request: Request, settings: Settings) -> tuple[str, Response]:
    if not _key_is_valid(request, settings.vendor_api_key):
        return "auth rejected", JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        quote_request = _parse_body(await request.body(), request.headers.get("content-type", ""))
        rate = rate_for_band(quote_request.risk_band, settings)
        total = total_commission(quote_request.loan_amount, rate)
    except InvalidBody as error:
        return "invalid", JSONResponse({"error": str(error)}, status_code=422)
    except ArithmeticError:
        return "invalid", JSONResponse({"error": "loanAmount is too large"}, status_code=422)

    if random.random() < settings.failure_rate:
        status = random.choice(FAULT_STATUSES)
        return "fault injected", JSONResponse({"error": "Simulated fault"}, status_code=status)
    if random.random() < settings.slow_response_rate:
        await asyncio.sleep(settings.slow_response_delay_seconds)
    return "quote issued", _quote_response(rate, total)


@router.post("/commission-quotes")
async def create_quote(request: Request) -> Response:
    started = time.perf_counter()
    outcome, response = await _handle(request, request.app.state.settings)
    latency_ms = round((time.perf_counter() - started) * 1000)
    logger.info(
        "quote request",
        extra={
            "fields": {"outcome": outcome, "status": response.status_code, "latencyMs": latency_ms}
        },
    )
    return response
