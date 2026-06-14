"""REST proxy route — catch-all HTTP gateway with cookie-based authentication.

Auth flow:
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

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import Response as StarletteResponse

from src.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from src.core.services.proxy_config import (
    BLOCKED_ROUTES,
    UNAUTHENTICATED_ROUTES,
    resolve_downstream,
)
from src.core.services.proxy_service import (
    do_refresh,
    handle_login,
    handle_logout,
    handle_refresh,
    proxy_authenticated,
)
from src.utils.cookie_utils import get_access_token, get_refresh_token, set_auth_cookies
from src.utils.proxy_utils import copy_headers, strip_response_headers
from src.utils.security import decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter()


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
    if downstream_url is None:
        raise NotFoundException("No downstream route configured for this path.")

    # ── Auth interceptors for login / refresh / logout ────────────────────────
    if request.method == "POST" and request_path == "/auth/login":
        return await handle_login(request)

    if request.method == "POST" and request_path == "/auth/refresh":
        return await handle_refresh(request)

    if request.method == "POST" and request_path == "/auth/logout":
        return await handle_logout(request)

    # ── Unauthenticated pass-through routes ───────────────────────────────────
    if (request.method, request_path) in UNAUTHENTICATED_ROUTES:
        headers = copy_headers(request)
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
        response_headers = strip_response_headers(response.headers)
        from starlette.background import BackgroundTask

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

        result = await do_refresh(refresh_token, request.app.state.http_client)
        if result is None:
            raise UnauthorizedException("Session expired. Please log in again.")

        new_access, new_refresh = result
        claims = decode_access_token(new_access)

        # Proxy the request with the freshly obtained claims and then
        # attach the updated cookies to the response.
        streaming = await proxy_authenticated(path, request, new_access, claims)

        # We cannot set cookies on a StreamingResponse directly in Starlette
        # after the fact, so we buffer for auth refresh responses only
        # (this path is the minority case: only when the access token has
        # just expired mid-session).
        raw_headers = list(streaming.headers.items())

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

    return await proxy_authenticated(path, request, access_token, claims)  # type: ignore[arg-type]
