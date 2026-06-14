"""Exception handlers for gateway responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        logger.warning(
            "HTTP exception occurred",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "Request validation failed",
            extra={"path": request.url.path, "method": request.method},
        )
        errors = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": str(error["msg"]),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Request validation failed.",
                "errors": errors,
            },
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
