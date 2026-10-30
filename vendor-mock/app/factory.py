from fastapi import FastAPI

from app.api.quotes import router
from app.config import Settings
from app.log import configure_logging


def create_app(settings: Settings) -> FastAPI:
    configure_logging()
    app = FastAPI(title="Vendor mock", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.include_router(router)
    return app
