"""Application exceptions for gateway-service."""

from http import HTTPStatus


class GatewayException(Exception):
    """Base exception rendered by gateway error handlers."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    message: str = "Internal server error."

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.status_code = status_code or self.status_code
        super().__init__(self.message)


class UnauthorizedException(GatewayException):
    """Raised for missing or invalid authentication."""

    status_code = HTTPStatus.UNAUTHORIZED
    message = "Unauthorized."


class ForbiddenException(GatewayException):
    """Raised when a route is not externally accessible."""

    status_code = HTTPStatus.FORBIDDEN
    message = "Forbidden."


class NotFoundException(GatewayException):
    """Raised when the gateway has no downstream route for a path."""

    status_code = HTTPStatus.NOT_FOUND
    message = "Route not found."


class RateLimitException(GatewayException):
    """Raised when an IP exceeds the configured request window."""

    status_code = HTTPStatus.TOO_MANY_REQUESTS
    message = "Too many requests."
