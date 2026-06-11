"""REST proxy handlers with HttpOnly cookie-based authentication.

Auth flow handled here:
- POST /auth/login   → proxy → intercept response → strip tokens from body
                       → set HttpOnly cookies → return recruiter profile only
- POST /auth/refresh → read refresh cookie → rewrite body → proxy → update cookies
- POST /auth/logout  → read refresh cookie → rewrite body → proxy → clear cookies
- All other authenticated routes → read access cookie → decode JWT
  → inject X-User-Id / X-User-Role → proxy downstream
  → on 401: silently refresh once using the refresh cookie → retry
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from src.config.settings import settings
from src.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from src.core.services.cookie_auth import (
    clear_auth_cookies,
    get_access_token,
    get_refresh_token,
    set_auth_cookies,
)
from src.core.services.proxy_config import (
    BLOCKED_ROUTES,
    HOP_BY_HOP_HEADERS,
    STRIPPED_REQUEST_HEADERS,
    UNAUTHENTICATED_ROUTES,
    resolve_downstream,
)
from src.utils.security import decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Header helpers ────────────────────────────────────────────────────────────


def _copy_headers(request: Request) -> dict[str, str]:
    """Copy request headers, stripping hop-by-hop and cookie headers."""
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in STRIPPED_REQUEST_HEADERS and key.lower() != "host"
    }


def _strip_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Strip hop-by-hop headers from a downstream response."""
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


# ── Internal refresh helper ───────────────────────────────────────────────────


async def _do_refresh(
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


async def _handle_login(request: Request) -> JSONResponse:
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


async def _handle_refresh(request: Request) -> JSONResponse:
    """Proxy POST /auth/refresh using the refresh cookie as the token source."""
    refresh_token = get_refresh_token(request)
    if not refresh_token:
        resp = JSONResponse(
            content={"success": False, "message": "No refresh token cookie present."},
            status_code=401,
        )
        clear_auth_cookies(resp)
        return resp

    result = await _do_refresh(refresh_token, request.app.state.http_client)
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


async def _handle_logout(request: Request) -> JSONResponse:
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


# ── Generic proxy with cookie auth ────────────────────────────────────────────


async def _proxy_authenticated(
    path: str,
    request: Request,
    access_token: str,
    claims: dict[str, str],
) -> StreamingResponse:
    """Proxy an authenticated request, injecting identity headers."""
    headers = _copy_headers(request)
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

    response_headers = _strip_response_headers(response.headers)
    return StreamingResponse(
        response.aiter_raw(),
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type"),
        background=BackgroundTask(response.aclose),
    )


# ── Main route handler ────────────────────────────────────────────────────────


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    response_model=None,
)
async def proxy_http_request(
    path: str, request: Request
) -> StreamingResponse | JSONResponse:
    """Gateway catch-all HTTP proxy with cookie-based auth."""

    request_path = f"/{path}"

    # ── Blocked internal routes ───────────────────────────────────────────────
    if any(request_path.startswith(blocked) for blocked in BLOCKED_ROUTES):
        raise ForbiddenException("Internal routes are not externally accessible.")

    # ── No downstream configured ──────────────────────────────────────────────
    downstream_url = resolve_downstream(request_path)
    if downstream_url is None or request_path.startswith("/ws/interview"):
        raise NotFoundException("No downstream route configured for this path.")

    # ── Auth interceptors for login / refresh / logout ────────────────────────
    if request.method == "POST" and request_path == "/auth/login":
        return await _handle_login(request)

    if request.method == "POST" and request_path == "/auth/refresh":
        return await _handle_refresh(request)

    if request.method == "POST" and request_path == "/auth/logout":
        return await _handle_logout(request)

    # ── Unauthenticated pass-through routes ───────────────────────────────────
    if (request.method, request_path) in UNAUTHENTICATED_ROUTES:
        headers = _copy_headers(request)
        headers["X-Internal-Service"] = "gateway"
        target_url = f"{downstream_url.rstrip('/')}{request_path}"
        proxy_request = request.app.state.http_client.build_request(
            request.method,
            target_url,
            params=request.query_params,
            headers=headers,
            content=await request.body(),
        )
        response = await request.app.state.http_client.send(proxy_request, stream=True)
        response_headers = _strip_response_headers(response.headers)
        return StreamingResponse(
            response.aiter_raw(),
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type"),
            background=BackgroundTask(response.aclose),
        )

    # ── Authenticated routes: read access cookie ──────────────────────────────
    access_token = get_access_token(request)

    try:
        claims = decode_access_token(access_token)
    except UnauthorizedException:
        # Access token missing or expired — attempt a silent refresh.
        refresh_token = get_refresh_token(request)
        if not refresh_token:
            raise UnauthorizedException("No valid session. Please log in.")

        result = await _do_refresh(refresh_token, request.app.state.http_client)
        if result is None:
            raise UnauthorizedException("Session expired. Please log in again.")

        new_access, new_refresh = result
        claims = decode_access_token(new_access)

        # Proxy the request with the freshly obtained claims and then
        # attach the updated cookies to the response.
        streaming = await _proxy_authenticated(path, request, new_access, claims)

        # We cannot set cookies on a StreamingResponse directly in Starlette
        # after the fact, so we buffer for auth refresh responses only
        # (this path is the minority case: only when the access token has
        # just expired mid-session).
        raw_headers = list(streaming.headers.items())
        from starlette.responses import Response as StarletteResponse  # local import

        # Consume the stream and re-emit so we can set-cookie on the response.
        chunks: list[bytes] = []
        async for chunk in streaming.body_iterator:
            chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
        body_bytes = b"".join(chunks)

        plain_response = StarletteResponse(
            content=body_bytes,
            status_code=streaming.status_code,
            headers=dict(raw_headers),
            media_type=streaming.media_type,
        )
        set_auth_cookies(plain_response, new_access, new_refresh)
        logger.info("Silent refresh succeeded — cookies updated on response")
        return plain_response  # type: ignore[return-value]

    return await _proxy_authenticated(path, request, access_token, claims)  # type: ignore[arg-type]
