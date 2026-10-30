from decimal import Decimal

from app.quotes.models import (
    FieldError,
    Limits,
    LoanDetails,
    Quote,
    QuotesUnavailable,
    ValidationFailed,
    VendorClient,
)


def decimal_places(value: Decimal) -> int:
    """Decimal places the value needs; trailing zeros don't count, so 1.100 needs 1."""
    if not value.is_finite() or value.is_zero():
        return 0
    digits, exponent = value.as_tuple()[1:]
    assert isinstance(exponent, int)
    trailing_zeros = len(digits) - len("".join(map(str, digits)).rstrip("0"))
    return max(0, -(exponent + trailing_zeros))


class QuoteService:
    """Holds limits and vendor as None when config made quotes unavailable."""

    def __init__(self, limits: Limits | None, vendor: VendorClient | None) -> None:
        self.limits = limits
        self._vendor = vendor

    @property
    def available(self) -> bool:
        return self.limits is not None and self._vendor is not None

    def ensure_available(self) -> None:
        self._ready()

    async def get_quote(self, loan: LoanDetails) -> Quote:
        limits, vendor = self._ready()
        errors = _check_bounds(loan, limits)
        if errors:
            raise ValidationFailed(errors)
        return await vendor.get_quote(loan)

    def _ready(self) -> tuple[Limits, VendorClient]:
        if self.limits is None or self._vendor is None:
            raise QuotesUnavailable
        return self.limits, self._vendor


def _check_bounds(loan: LoanDetails, limits: Limits) -> list[FieldError]:
    errors = []
    if decimal_places(loan.loan_amount) > limits.loan_amount_max_decimals:
        errors.append(FieldError("loanAmount", "TOO_MANY_DECIMALS"))
    elif not limits.loan_amount_min <= loan.loan_amount <= limits.loan_amount_max:
        errors.append(FieldError("loanAmount", "OUT_OF_RANGE"))
    if not limits.loan_term_months_min <= loan.loan_term_in_months <= limits.loan_term_months_max:
        errors.append(FieldError("loanTermInMonths", "OUT_OF_RANGE"))
    return errors
