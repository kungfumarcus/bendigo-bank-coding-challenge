import asyncio
import logging
import random
import time
from decimal import Decimal
from typing import Any

import httpx

from app.quotes.models import (
    LoanDetails,
    Quote,
    QuoteError,
    VendorAuthFailed,
    VendorBadResponse,
    VendorTimeout,
    VendorUnavailable,
    dumps_exact,
    loads_exact,
)

logger = logging.getLogger("backend.vendor")


class HttpVendorClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        url: str,
        api_key: str,
        timeout_seconds: float,
        max_retries: int,
        backoff_ms: float,
    ) -> None:
        self._client = client
        self._url = url
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._backoff_seconds = backoff_ms / 1000

    async def get_quote(self, loan: LoanDetails) -> Quote:
        body = dumps_exact(
            {
                "loanAmount": loan.loan_amount,
                "loanTermInMonths": loan.loan_term_in_months,
                "riskBand": loan.risk_band,
            }
        )
        attempt = 1
        while True:
            try:
                return await self._attempt(body, attempt)
            except (VendorUnavailable, VendorTimeout):
                if attempt > self._max_retries:
                    raise
            await asyncio.sleep(self._backoff_seconds * (1 + random.random() / 2))
            attempt += 1

    async def _attempt(self, body: str, attempt: int) -> Quote:
        started = time.perf_counter()
        outcome: dict[str, Any] = {}
        try:
            # asyncio.timeout is the total deadline; httpx's own timeouts are per phase.
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._client.post(
                    self._url,
                    content=body,
                    headers={"api-key": self._api_key, "content-type": "application/json"},
                )
            outcome["status"] = response.status_code
            quote = _read_reply(response)
            outcome["quoteId"] = quote.quote_id
            return quote
        except (TimeoutError, httpx.TimeoutException) as error:
            outcome["failure"] = "timeout"
            raise VendorTimeout from error
        except httpx.TransportError as error:
            outcome["failure"] = "connection error"
            raise VendorUnavailable from error
        except httpx.DecodingError as error:
            outcome["failure"] = "undecodable body"
            raise VendorBadResponse from error
        except QuoteError as error:
            outcome["failure"] = type(error).__name__
            raise
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000)
            fields = {"attempt": attempt, "latencyMs": latency_ms, **outcome}
            logger.info("vendor attempt", extra={"fields": fields})


def _read_reply(response: httpx.Response) -> Quote:
    status = response.status_code
    if status == 401:
        logger.error("vendor rejected our api-key", extra={"fields": {"failure": "auth"}})
        raise VendorAuthFailed
    if status >= 500:
        raise VendorUnavailable
    if status != 200:
        raise VendorBadResponse
    try:
        data = loads_exact(response.content)
    except (ValueError, RecursionError) as error:
        raise VendorBadResponse from error
    if not isinstance(data, dict) or not isinstance(data.get("quoteId"), str):
        raise VendorBadResponse
    return Quote(
        quote_id=data["quoteId"],
        commission_rate=_amount(data.get("commissionRate")),
        total_commission=_amount(data.get("totalCommission")),
    )


def _amount(value: Any) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise VendorBadResponse
    return value
