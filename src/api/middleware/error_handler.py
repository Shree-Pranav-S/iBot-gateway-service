"""Exception handlers for gateway responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.core.exceptions import GatewayException

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register gateway exception handlers."""

    @app.exception_handler(GatewayException)
    async def gateway_exception_handler(
        request: Request,
        exc: GatewayException,
    ) -> JSONResponse:
        logger.warning(
            "Gateway exception",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "Unhandled gateway exception",
            extra={"path": request.url.path, "method": request.method},
        )
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Internal server error."},
        )
