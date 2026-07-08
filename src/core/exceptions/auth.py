"""Authentication and session exceptions for the gateway."""

from src.core.exceptions.base import (
    BadGatewayException,
    UnauthorizedException,
)


class MissingAccessTokenException(UnauthorizedException):
    message = "Missing access token."
    error_code = "AUTH_MISSING_ACCESS_TOKEN"


class InvalidTokenException(UnauthorizedException):
    message = "Invalid or expired token."
    error_code = "AUTH_INVALID_TOKEN"


class InvalidTokenClaimsException(UnauthorizedException):
    message = "Invalid token claims."
    error_code = "AUTH_INVALID_TOKEN_CLAIMS"


class MissingRefreshTokenException(UnauthorizedException):
    message = "No refresh token cookie present."
    error_code = "AUTH_MISSING_REFRESH_TOKEN"
    clear_auth_cookies = True


class SessionExpiredException(UnauthorizedException):
    message = "Session expired. Please log in again."
    error_code = "AUTH_SESSION_EXPIRED"
    clear_auth_cookies = True


class NoValidSessionException(UnauthorizedException):
    message = "No valid session. Please log in."
    error_code = "AUTH_NO_VALID_SESSION"


class AuthenticationBackendException(BadGatewayException):
    message = "Authentication backend error."
    error_code = "AUTH_BACKEND_ERROR"


class AuthenticationServiceUnavailableException(BadGatewayException):
    message = "Authentication service unavailable."
    error_code = "AUTH_SERVICE_UNAVAILABLE"
