import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, NoReturn, Protocol


class JsonInteger(Decimal):
    """A number written in JSON without a fraction or exponent."""


def _parse_float(text: str) -> Decimal:
    try:
        return Decimal(text)
    except InvalidOperation:
        # Exponent too large even for Decimal. Infinity can't be sent any other way, as the
        # constants are rejected, and it fails every range check and every vendor reply check.
        return Decimal("Infinity")


def _reject_constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not allowed")


def loads_exact(body: bytes) -> Any:
    """Parse JSON keeping numbers as Decimal. Raises ValueError or RecursionError."""
    return json.loads(
        body, parse_float=_parse_float, parse_int=JsonInteger, parse_constant=_reject_constant
    )


def dumps_exact(value: Any) -> str:
    """Write JSON with each Decimal as the number it holds, never via a float."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        items = (f"{json.dumps(key)}:{dumps_exact(item)}" for key, item in value.items())
        return "{" + ",".join(items) + "}"
    return json.dumps(value)


@dataclass(frozen=True)
class LoanDetails:
    loan_amount: Decimal
    loan_term_in_months: Decimal
    risk_band: str


@dataclass(frozen=True)
class Quote:
    quote_id: str
    commission_rate: Decimal
    total_commission: Decimal


@dataclass(frozen=True)
class Limits:
    loan_amount_min: Decimal
    loan_amount_max: Decimal
    loan_amount_max_decimals: int
    loan_term_months_min: int
    loan_term_months_max: int


@dataclass(frozen=True)
class FieldError:
    field: str
    code: str


class VendorClient(Protocol):
    async def get_quote(self, loan: LoanDetails) -> Quote: ...


class QuoteError(Exception):
    """Base of the domain errors; the API layer maps each to a code and status."""


@dataclass
class ValidationFailed(QuoteError):
    fields: list[FieldError] = field(default_factory=list)


class MalformedBody(QuoteError):
    pass


class QuotesUnavailable(QuoteError):
    pass


class VendorAuthFailed(QuoteError):
    pass


class VendorUnavailable(QuoteError):
    pass


class VendorTimeout(QuoteError):
    pass


class VendorBadResponse(QuoteError):
    pass
