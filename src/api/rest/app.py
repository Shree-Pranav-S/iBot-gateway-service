"""FastAPI application factory for gateway-service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.error_handler import register_exception_handlers
from src.api.middleware.logging import request_logging_middleware
from src.api.rest.routes.health import router as health_router
from src.api.rest.routes.proxy import router as proxy_router
from src.config.settings import settings
from src.data.clients.http_client import create_http_client
from src.observability.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = create_http_client()
    try:
        yield
    finally:
        await app.state.http_client.aclose()


def create_app() -> FastAPI:
    """Create and configure the gateway FastAPI application."""

    configure_logging()
    app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,  # required for HttpOnly cookie to be sent
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_logging_middleware)
    app.include_router(health_router)
    app.include_router(proxy_router)
    return app


app = create_app()
