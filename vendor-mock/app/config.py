from decimal import Decimal
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
CommissionRate = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    vendor_api_key: str
    commission_rate_low: CommissionRate = Decimal("0.01")
    commission_rate_medium: CommissionRate = Decimal("0.015")
    commission_rate_high: CommissionRate = Decimal("0.0225")
    failure_rate: Probability = 0.2
    slow_response_rate: Probability = 0.1
    slow_response_delay_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 5

    @field_validator("vendor_api_key")
    @classmethod
    def key_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value
