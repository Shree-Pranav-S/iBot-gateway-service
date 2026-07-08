"""Application exceptions for gateway-service."""

from http import HTTPStatus
from typing import Any


class GatewayException(Exception):
    """Base exception rendered by gateway error handlers."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    message: str = "Internal server error."
    error_code: str = "GATEWAY_INTERNAL_ERROR"
    clear_auth_cookies: bool = False

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int | None = None,
        details: list[dict[str, Any]] | None = None,
        error_code: str | None = None,
        clear_auth_cookies: bool | None = None,
    ) -> None:
        """Initialize the exception with optional response metadata."""
        self.message = message or self.message
        self.status_code = status_code or self.status_code
        self.details = details
        self.error_code = error_code or self.error_code
        if clear_auth_cookies is not None:
            self.clear_auth_cookies = clear_auth_cookies
        super().__init__(self.message)


class BadRequestException(GatewayException):
    """Raised when a request is syntactically valid but semantically invalid."""

    status_code = HTTPStatus.BAD_REQUEST
    message = "Bad request."
    error_code = "GATEWAY_BAD_REQUEST"


class UnauthorizedException(GatewayException):
    """Raised for missing or invalid authentication."""

    status_code = HTTPStatus.UNAUTHORIZED
    message = "Unauthorized."
    error_code = "GATEWAY_UNAUTHORIZED"


class ForbiddenException(GatewayException):
    """Raised when a route is not externally accessible."""

    status_code = HTTPStatus.FORBIDDEN
    message = "Forbidden."
    error_code = "GATEWAY_FORBIDDEN"


class NotFoundException(GatewayException):
    """Raised when the gateway has no downstream route for a path."""

    status_code = HTTPStatus.NOT_FOUND
    message = "Route not found."
    error_code = "GATEWAY_NOT_FOUND"


class BadGatewayException(GatewayException):
    """Raised when a downstream service is unavailable or returns an invalid response."""

    status_code = HTTPStatus.BAD_GATEWAY
    message = "Bad gateway."
    error_code = "GATEWAY_BAD_GATEWAY"
