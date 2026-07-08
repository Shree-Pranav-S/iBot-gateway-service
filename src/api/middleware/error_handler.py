"""Exception handlers for gateway responses."""

import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.exceptions import DownstreamUnavailableException, GatewayException
from src.schemas.common import ErrorDetail, ErrorResponse
from src.utils.cookie_utils import clear_auth_cookies

logger = logging.getLogger(__name__)


def _json_error(
    *,
    status_code: int,
    message: str,
    errors: list[ErrorDetail] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(message=message, errors=errors)
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Register gateway exception handlers."""

    @app.exception_handler(GatewayException)
    async def gateway_exception_handler(
        request: Request,
        exc: GatewayException,
    ) -> JSONResponse:
        """Render known gateway exceptions as the public error envelope."""
        logger.warning(
            "Gateway exception",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": exc.status_code,
                "error_code": getattr(exc, "error_code", None),
                "exception_type": type(exc).__name__,
            },
        )
        errors = (
            [ErrorDetail(**detail) for detail in exc.details]
            if exc.details is not None
            else None
        )
        response = _json_error(
            status_code=exc.status_code,
            message=exc.message,
            errors=errors,
        )
        if getattr(exc, "clear_auth_cookies", False):
            clear_auth_cookies(response)
        return response

    @app.exception_handler(httpx.RequestError)
    async def httpx_request_error_handler(
        request: Request,
        exc: httpx.RequestError,
    ) -> JSONResponse:
        """Render downstream connection failures as a bad-gateway response."""
        downstream_exc = DownstreamUnavailableException()
        logger.error(
            "Downstream connection error",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": downstream_exc.status_code,
                "error_code": downstream_exc.error_code,
                "exception_type": type(exc).__name__,
            },
        )
        return _json_error(
            status_code=downstream_exc.status_code,
            message=downstream_exc.message,
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """Render Starlette HTTP exceptions as the public error envelope."""
        logger.warning(
            "HTTP exception occurred",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": exc.status_code,
            },
        )
        return _json_error(
            status_code=exc.status_code,
            message=exc.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Render request validation failures with normalized field errors."""
        logger.warning(
            "Request validation failed",
            extra={"path": request.url.path, "method": request.method},
        )
        errors = [
            ErrorDetail(
                field=".".join(str(part) for part in error["loc"]),
                message=str(error["msg"]),
            )
            for error in exc.errors()
        ]
        return _json_error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Request validation failed.",
            errors=errors,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Render unexpected exceptions without exposing internal details."""
        logger.exception(
            "Unhandled gateway exception",
            extra={"path": request.url.path, "method": request.method},
        )
        return _json_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error.",
        )
