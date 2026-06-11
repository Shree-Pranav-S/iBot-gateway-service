"""Shared HTTP client for downstream proxy calls."""

import httpx

from src.config.settings import settings


def create_http_client() -> httpx.AsyncClient:
    """Create the gateway's pooled async HTTP client."""

    limits = httpx.Limits(
        max_connections=settings.HTTP_CLIENT_MAX_CONNECTIONS,
        max_keepalive_connections=settings.HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS,
    )
    return httpx.AsyncClient(timeout=settings.HTTP_CLIENT_TIMEOUT, limits=limits)
