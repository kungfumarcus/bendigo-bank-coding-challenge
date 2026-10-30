import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Annotated, Any, Literal, NoReturn, Protocol

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, StrictStr

# What loads_exact raises on a body it can't decode, including a number too large for it.
DECODE_ERRORS = (ValueError, ArithmeticError, RecursionError)

_DECIMAL_STRING = re.compile(r"-?[0-9]+(\.[0-9]+)?")


def _reject_constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not allowed")


def loads_exact(body: bytes) -> Any:
    """Decode JSON with fractions as Decimal; Pydantic alone would read them through a float."""
    return json.loads(body, parse_float=Decimal, parse_constant=_reject_constant)


def dumps_exact(value: Any) -> str:
    """Write JSON with each Decimal as the number it holds; Pydantic would write a string."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        items = (f"{json.dumps(key)}:{dumps_exact(item)}" for key, item in value.items())
        return "{" + ",".join(items) + "}"
    return json.dumps(value)


def _decimal_string(value: Any) -> Decimal:
    if not isinstance(value, str) or not _DECIMAL_STRING.fullmatch(value):
        raise ValueError("must be a decimal string")
    return Decimal(value)


def _json_number(value: Any) -> Decimal:
    # Pydantic's Decimal also accepts numeric strings, even in strict mode.
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        raise ValueError("must be a JSON number")
    return Decimal(value)


VendorAmount = Annotated[Decimal, BeforeValidator(_json_number), Field(ge=0, allow_inf_nan=False)]


class LoanDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    loan_amount: Annotated[Decimal, BeforeValidator(_decimal_string)] = Field(alias="loanAmount")
    loan_term_in_months: StrictInt = Field(alias="loanTermInMonths")
    risk_band: Literal["LOW", "MEDIUM", "HIGH"] = Field(alias="riskBand")


class Quote(BaseModel):
    """The vendor's reply, checked against the contract."""

    model_config = ConfigDict(frozen=True)

    quote_id: Annotated[StrictStr, Field(min_length=1)] = Field(alias="quoteId")
    commission_rate: VendorAmount = Field(alias="commissionRate")
    total_commission: VendorAmount = Field(alias="totalCommission")


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
