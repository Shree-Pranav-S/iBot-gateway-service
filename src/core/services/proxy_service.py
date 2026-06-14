"""HTTP proxy business logic for the gateway service.

Handles the auth-interceptor flows (login, refresh, logout) and the generic
authenticated proxy helper. Route handlers in ``routes/proxy.py`` delegate
all logic to this service.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from src.config.settings import settings
from src.core.services.proxy_config import resolve_downstream
from src.utils.cookie_utils import (
    clear_auth_cookies,
    get_refresh_token,
    set_auth_cookies,
)
from src.utils.proxy_utils import copy_headers, strip_response_headers
from src.utils.security import decode_access_token

logger = logging.getLogger(__name__)


# ── Internal refresh helper ───────────────────────────────────────────────────


async def do_refresh(
    refresh_token: str,
    client: httpx.AsyncClient,
) -> tuple[str, str] | None:
    """Call core-api's refresh endpoint internally and return (access, refresh).

    Returns None if the refresh token is invalid or the call fails.
    """
    try:
        resp = await client.post(
            f"{settings.CORE_API_URL.rstrip('/')}/auth/refresh",
            json={"refresh_token": refresh_token},
            headers={
                "Content-Type": "application/json",
                "X-Internal-Service": "gateway",
            },
        )
        if resp.status_code != 200:
            return None
        body = resp.json()
        data = body.get("data") or {}
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        if access and refresh:
            return access, refresh
    except Exception:
        logger.exception("Silent token refresh call to core-api failed")
    return None


# ── Auth interceptors ─────────────────────────────────────────────────────────


async def handle_login(request: Request) -> JSONResponse:
    """Proxy POST /auth/login, intercept tokens, set HttpOnly cookies.

    The browser never sees the raw JWT values.
    """
    body_bytes = await request.body()
    upstream_resp = await request.app.state.http_client.post(
        f"{settings.CORE_API_URL.rstrip('/')}/auth/login",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Internal-Service": "gateway",
        },
    )

    upstream_body = upstream_resp.json()

    if upstream_resp.status_code != 200:
        return JSONResponse(
            content=upstream_body, status_code=upstream_resp.status_code
        )

    data = upstream_body.get("data") or {}
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    if not access_token or not refresh_token:
        logger.error("core-api login response missing tokens")
        return JSONResponse(
            content={"success": False, "message": "Authentication backend error."},
            status_code=502,
        )

    # Core-api login returns tokens only — fetch the recruiter profile separately.
    claims = decode_access_token(access_token)
    profile_resp = await request.app.state.http_client.get(
        f"{settings.CORE_API_URL.rstrip('/')}/auth/me",
        headers={
            "X-Internal-Service": "gateway",
            "X-User-Id": str(claims["sub"]),
        },
    )
    if profile_resp.status_code != 200:
        logger.error(
            "Failed to fetch recruiter profile after login",
            extra={"status_code": profile_resp.status_code},
        )
        return JSONResponse(
            content={"success": False, "message": "Authentication backend error."},
            status_code=502,
        )

    profile_body = profile_resp.json()
    profile_data = profile_body.get("data")

    response_body = {
        "success": upstream_body.get("success", True),
        "message": upstream_body.get("message", "Login successful."),
        "data": profile_data,
    }

    json_response = JSONResponse(content=response_body, status_code=200)
    set_auth_cookies(json_response, access_token, refresh_token)
    logger.info("Login successful — HttpOnly cookies set")
    return json_response


async def handle_refresh(request: Request) -> JSONResponse:
    """Proxy POST /auth/refresh using the refresh cookie as the token source."""
    refresh_token = get_refresh_token(request)
    if not refresh_token:
        resp = JSONResponse(
            content={"success": False, "message": "No refresh token cookie present."},
            status_code=401,
        )
        clear_auth_cookies(resp)
        return resp

    result = await do_refresh(refresh_token, request.app.state.http_client)
    if result is None:
        resp = JSONResponse(
            content={
                "success": False,
                "message": "Session expired. Please log in again.",
            },
            status_code=401,
        )
        clear_auth_cookies(resp)
        return resp

    new_access, new_refresh = result
    json_response = JSONResponse(
        content={"success": True, "message": "Token refreshed.", "data": None},
        status_code=200,
    )
    set_auth_cookies(json_response, new_access, new_refresh)
    logger.info("Token refreshed — cookies updated")
    return json_response


async def handle_logout(request: Request) -> JSONResponse:
    """Proxy POST /auth/logout using the refresh cookie, then clear cookies."""
    refresh_token = get_refresh_token(request)

    if refresh_token:
        try:
            await request.app.state.http_client.post(
                f"{settings.CORE_API_URL.rstrip('/')}/auth/logout",
                json={"refresh_token": refresh_token},
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Service": "gateway",
                },
            )
        except Exception:
            logger.warning("core-api logout call failed — still clearing cookies")

    json_response = JSONResponse(
        content={"success": True, "message": "Logged out successfully.", "data": None},
        status_code=200,
    )
    clear_auth_cookies(json_response)
    logger.info("Logout — auth cookies cleared")
    return json_response


# ── Generic authenticated proxy ───────────────────────────────────────────────


async def proxy_authenticated(
    path: str,
    request: Request,
    access_token: str,
    claims: dict[str, str],
) -> StreamingResponse:
    """Proxy an authenticated request, injecting identity headers."""
    headers = copy_headers(request)
    headers["X-Internal-Service"] = "gateway"
    headers["X-User-Id"] = str(claims["sub"])
    headers["X-User-Role"] = str(claims["role"])

    downstream_url = resolve_downstream(f"/{path}")
    target_url = f"{downstream_url.rstrip('/')}/{path}"

    proxy_request = request.app.state.http_client.build_request(
        request.method,
        target_url,
        params=request.query_params,
        headers=headers,
        content=await request.body(),
    )
    response = await request.app.state.http_client.send(proxy_request, stream=True)

    response_headers = strip_response_headers(response.headers)
    return StreamingResponse(
        response.aiter_raw(),
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type"),
        background=BackgroundTask(response.aclose),
    )
