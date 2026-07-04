"""Stateless helper utilities for the gateway HTTP proxy."""

import httpx
from fastapi import Request

from src.core.services.proxy_config import HOP_BY_HOP_HEADERS, STRIPPED_REQUEST_HEADERS


def copy_headers(request: Request) -> dict[str, str]:
    """Copy request headers, stripping hop-by-hop and cookie headers."""
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in STRIPPED_REQUEST_HEADERS and key.lower() != "host"
    }


def strip_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Strip hop-by-hop headers from a downstream response."""
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }
