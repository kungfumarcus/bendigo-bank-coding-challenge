from decimal import ROUND_HALF_UP, Context, Decimal

from app.config import Settings

CENTS = Decimal("0.01")
# Wide enough that no amount we can price is rounded before the final half-up to cents.
_PRICING_CONTEXT = Context(prec=100, rounding=ROUND_HALF_UP)


def rate_for_band(risk_band: str, settings: Settings) -> Decimal:
    return {
        "LOW": settings.commission_rate_low,
        "MEDIUM": settings.commission_rate_medium,
        "HIGH": settings.commission_rate_high,
    }[risk_band]


def total_commission(loan_amount: Decimal, rate: Decimal) -> Decimal:
    """Raises ArithmeticError (decimal's Overflow or InvalidOperation) when too large to price."""
    return _PRICING_CONTEXT.multiply(loan_amount, rate).quantize(CENTS, context=_PRICING_CONTEXT)
