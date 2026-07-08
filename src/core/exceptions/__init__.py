"""Gateway exception exports."""

from src.core.exceptions.auth import (
    AuthenticationBackendException,
    AuthenticationServiceUnavailableException,
    InvalidTokenClaimsException,
    InvalidTokenException,
    MissingAccessTokenException,
    MissingRefreshTokenException,
    NoValidSessionException,
    SessionExpiredException,
)
from src.core.exceptions.base import (
    BadGatewayException,
    BadRequestException,
    ForbiddenException,
    GatewayException,
    NotFoundException,
    UnauthorizedException,
)
from src.core.exceptions.proxy import (
    DownstreamConnectionException,
    DownstreamUnavailableException,
    InvalidUpstreamResponseException,
)

__all__ = [
    "AuthenticationBackendException",
    "AuthenticationServiceUnavailableException",
    "BadGatewayException",
    "BadRequestException",
    "DownstreamConnectionException",
    "DownstreamUnavailableException",
    "ForbiddenException",
    "GatewayException",
    "InvalidTokenClaimsException",
    "InvalidTokenException",
    "InvalidUpstreamResponseException",
    "MissingAccessTokenException",
    "MissingRefreshTokenException",
    "NoValidSessionException",
    "NotFoundException",
    "SessionExpiredException",
    "UnauthorizedException",
]
