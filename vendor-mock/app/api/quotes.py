import asyncio
import hmac
import json
import logging
import random
import time
import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal, NoReturn

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, ValidationError

from app.config import Settings
from app.quotes.pricing import rate_for_band, total_commission

logger = logging.getLogger("vendor_mock")
router = APIRouter()

FAULT_STATUSES = (500, 502, 503)


class InvalidBody(Exception):
    pass


def _json_number(value: Any) -> Decimal:
    # Pydantic's Decimal also accepts numeric strings, even in strict mode.
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        raise ValueError("must be a JSON number")
    return Decimal(value)


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    loan_amount: Annotated[
        Decimal, BeforeValidator(_json_number), Field(gt=0, allow_inf_nan=False)
    ] = Field(alias="loanAmount")
    loan_term_in_months: Annotated[StrictInt, Field(gt=0)] = Field(alias="loanTermInMonths")
    risk_band: Literal["LOW", "MEDIUM", "HIGH"] = Field(alias="riskBand")


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
    try:
        return QuoteRequest.model_validate(data)
    except ValidationError as error:
        fields = ", ".join(sorted({str(item["loc"][0]) for item in error.errors() if item["loc"]}))
        raise InvalidBody(f"Invalid request body: {fields or 'not a JSON object'}") from error


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
