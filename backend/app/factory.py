import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response

from app.api.quotes import error_response, router
from app.config import LoadedConfig, load_config
from app.log import configure_logging, request_id_var
from app.quotes.models import Limits
from app.quotes.service import QuoteService
from app.quotes.vendor import HttpVendorClient

logger = logging.getLogger("backend")


def create_app(
    config: LoadedConfig | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    configure_logging()
    loaded = config if config is not None else load_config()
    for problem in loaded.problems:
        logger.error("invalid config", extra={"fields": {"problem": problem}})

    # Redirects stay off: following one could send the api-key to another host.
    # The total deadline per attempt is set in the vendor client.
    client = httpx.AsyncClient(
        transport=transport, follow_redirects=False, timeout=None, trust_env=False
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await client.aclose()

    app = FastAPI(
        title="Commission Quote backend",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    settings = loaded.settings
    if settings is None:
        app.state.service = QuoteService(None, None)
    else:
        app.state.service = QuoteService(
            Limits(
                loan_amount_min=settings.loan_amount_min,
                loan_amount_max=settings.loan_amount_max,
                loan_amount_max_decimals=settings.loan_amount_max_decimals,
                loan_term_months_min=settings.loan_term_months_min,
                loan_term_months_max=settings.loan_term_months_max,
            ),
            HttpVendorClient(
                client,
                url=settings.vendor_quote_url,
                api_key=settings.vendor_api_key,
                timeout_seconds=settings.vendor_timeout_seconds,
                max_retries=settings.vendor_max_retries,
                backoff_ms=settings.vendor_retry_backoff_ms,
            ),
        )
        app.state.request_timeout_seconds = settings.frontend_request_timeout_seconds

    @app.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        value = str(uuid.uuid4())
        token = request_id_var.set(value)
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("unhandled error")
                response = error_response("INTERNAL_ERROR", 500)
            response.headers["X-Request-ID"] = value
            return response
        finally:
            request_id_var.reset(token)

    app.include_router(router)
    return app
