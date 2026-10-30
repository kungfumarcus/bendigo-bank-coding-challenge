import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from app.log import request_id_var
from app.quotes.models import (
    DECODE_ERRORS,
    FieldError,
    LoanDetails,
    MalformedBody,
    QuoteError,
    QuotesUnavailable,
    ValidationFailed,
    VendorAuthFailed,
    VendorBadResponse,
    VendorTimeout,
    VendorUnavailable,
    dumps_exact,
    loads_exact,
)
from app.quotes.service import QuoteService

logger = logging.getLogger("backend.quotes")
router = APIRouter(prefix="/api/v1")

ERROR_CODES: dict[type[QuoteError], tuple[str, int]] = {
    ValidationFailed: ("VALIDATION_FAILED", 422),
    MalformedBody: ("VALIDATION_FAILED", 400),
    QuotesUnavailable: ("QUOTES_UNAVAILABLE", 503),
    VendorAuthFailed: ("VENDOR_AUTH_FAILED", 502),
    VendorUnavailable: ("VENDOR_UNAVAILABLE", 502),
    VendorTimeout: ("VENDOR_TIMEOUT", 504),
    VendorBadResponse: ("VENDOR_BAD_RESPONSE", 502),
}


def json_response(payload: dict[str, Any], status_code: int = 200) -> Response:
    return Response(dumps_exact(payload), status_code, media_type="application/json")


def error_response(code: str, status_code: int, fields: list[FieldError] | None = None) -> Response:
    error: dict[str, Any] = {"code": code, "requestId": request_id_var.get()}
    if fields:
        error["fields"] = [{"field": item.field, "code": item.code} for item in fields]
    return Response(json.dumps({"error": error}), status_code, media_type="application/json")


def parse_loan_details(body: bytes, content_type: str) -> LoanDetails:
    if content_type.split(";")[0].strip().lower() != "application/json":
        raise MalformedBody
    try:
        data = loads_exact(body)
    except DECODE_ERRORS as error:
        raise MalformedBody from error
    if not isinstance(data, dict):
        raise MalformedBody
    try:
        return LoanDetails.model_validate(data)
    except ValidationError as error:
        raise ValidationFailed([_field_error(item) for item in error.errors()]) from error


def _field_error(error: ErrorDetails) -> FieldError:
    name = str(error["loc"][0])
    if error["type"] == "missing":
        return FieldError(name, "REQUIRED")
    if error["type"] == "extra_forbidden":
        return FieldError(name, "UNKNOWN_FIELD")
    return FieldError(name, "NOT_A_NUMBER" if name == "loanAmount" else "INVALID_VALUE")


@router.get("/health")
async def health() -> Response:
    return json_response({"status": "ok"})


@router.get("/quotes/status")
async def quotes_status(request: Request) -> Response:
    service: QuoteService = request.app.state.service
    limits = service.limits
    if limits is None or not service.available:
        return json_response({"available": False, "requestTimeoutSeconds": None, "limits": None})
    return json_response(
        {
            "available": True,
            "requestTimeoutSeconds": request.app.state.request_timeout_seconds,
            "limits": {
                "loanAmountMin": limits.loan_amount_min,
                "loanAmountMax": limits.loan_amount_max,
                "loanAmountMaxDecimals": limits.loan_amount_max_decimals,
                "loanTermMonthsMin": limits.loan_term_months_min,
                "loanTermMonthsMax": limits.loan_term_months_max,
            },
        }
    )


@router.post("/quotes")
async def create_quote(request: Request) -> Response:
    service: QuoteService = request.app.state.service
    started = time.perf_counter()
    outcome = "INTERNAL_ERROR"
    fields: dict[str, Any] = {}
    try:
        service.ensure_available()
        loan = parse_loan_details(await request.body(), request.headers.get("content-type", ""))
        fields = {
            "loanAmount": str(loan.loan_amount),
            "loanTermInMonths": loan.loan_term_in_months,
            "riskBand": loan.risk_band,
        }
        quote = await service.get_quote(loan)
        outcome = "OK"
        return json_response(
            {
                "quoteId": quote.quote_id,
                "commissionRate": quote.commission_rate,
                "totalCommission": format(quote.total_commission, "f"),
            }
        )
    except QuoteError as error:
        outcome, status_code = ERROR_CODES[type(error)]
        return error_response(
            outcome, status_code, error.fields if isinstance(error, ValidationFailed) else None
        )
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "quote request",
            extra={"fields": {"outcome": outcome, "latencyMs": latency_ms, **fields}},
        )
