import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Visible ASCII, with spaces or tabs only between characters.
_HEADER_VALUE = re.compile(r"[\x21-\x7e]([\x20-\x7e\t]*[\x21-\x7e])?")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    vendor_quote_url: str
    vendor_api_key: str
    vendor_timeout_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 3
    vendor_max_retries: Annotated[int, Field(ge=0)] = 1
    vendor_retry_backoff_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 250
    frontend_request_timeout_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 15
    loan_amount_min: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)] = Decimal(1)
    loan_amount_max: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)] = Decimal(10000000)
    loan_amount_max_decimals: Annotated[int, Field(ge=1)] = 2
    loan_term_months_min: Annotated[int, Field(ge=1)] = 1
    loan_term_months_max: Annotated[int, Field(ge=0)] = 360

    @field_validator("vendor_quote_url")
    @classmethod
    def url_is_http(cls, value: str) -> str:
        # Parsed by httpx, so a URL that passes here is one the vendor client can use. httpx alone
        # accepts port 99999 and a space in the host, and reading .port is what checks the range.
        try:
            url = httpx.URL(value)
            urlsplit(value).port  # noqa: B018
        except (httpx.InvalidURL, ValueError) as error:
            raise ValueError("must be an http or https URL with a valid host and port") from error
        if url.scheme not in ("http", "https") or not url.host or re.search(r"\s", value):
            raise ValueError("must be an http or https URL with a valid host and port")
        return value

    @field_validator("vendor_api_key")
    @classmethod
    def key_fits_a_header(cls, value: str) -> str:
        if not _HEADER_VALUE.fullmatch(value):
            raise ValueError("must be visible ASCII usable in an HTTP header")
        return value

    def worst_case_seconds(self) -> float:
        retries = self.vendor_max_retries
        backoff_seconds = self.vendor_retry_backoff_ms / 1000
        return (retries + 1) * self.vendor_timeout_seconds + retries * 1.5 * backoff_seconds


@dataclass(frozen=True)
class LoadedConfig:
    """Settings, or None when any problem makes the backend unavailable."""

    settings: Settings | None
    problems: list[str]


def check_settings(settings: Settings) -> list[str]:
    problems = []
    if settings.loan_amount_min > settings.loan_amount_max:
        problems.append("LOAN_AMOUNT_MIN: must not be above LOAN_AMOUNT_MAX")
    if settings.loan_term_months_min > settings.loan_term_months_max:
        problems.append("LOAN_TERM_MONTHS_MIN: must not be above LOAN_TERM_MONTHS_MAX")
    if settings.frontend_request_timeout_seconds <= settings.worst_case_seconds():
        problems.append("FRONTEND_REQUEST_TIMEOUT_SECONDS: must be above the vendor worst case")
    return problems


def load_config() -> LoadedConfig:
    try:
        settings = Settings()
    except ValidationError as error:
        # Built from the name and message only; a pydantic error's input could be the key.
        problems = [f"{str(e['loc'][0]).upper()}: {e['msg']}" for e in error.errors()]
        return LoadedConfig(None, problems)
    problems = check_settings(settings)
    return LoadedConfig(None if problems else settings, problems)
