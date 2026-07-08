"""Proxy and downstream service exceptions for the gateway."""

from src.core.exceptions.base import BadGatewayException


class DownstreamUnavailableException(BadGatewayException):
    message = "Service unavailable or starting up."
    error_code = "PROXY_DOWNSTREAM_UNAVAILABLE"


class DownstreamConnectionException(DownstreamUnavailableException):
    error_code = "PROXY_DOWNSTREAM_CONNECTION"


class InvalidUpstreamResponseException(BadGatewayException):
    message = "Invalid response from downstream service."
    error_code = "PROXY_INVALID_UPSTREAM_RESPONSE"
