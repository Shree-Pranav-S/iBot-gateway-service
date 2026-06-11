"""In-memory sliding-window rate limiter."""

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from src.config.settings import settings
from src.core.exceptions import RateLimitException

_windows: dict[str, deque[float]] = defaultdict(deque)
_window_seconds = 60.0


def _limit_for(path: str) -> int:
    if path.startswith("/auth"):
        return settings.AUTH_RATE_LIMIT_PER_MINUTE
    return settings.GENERAL_RATE_LIMIT_PER_MINUTE


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Apply a per-IP sliding-window rate limit."""

    client_host = request.client.host if request.client else "unknown"
    key = (
        f"{client_host}:{'auth' if request.url.path.startswith('/auth') else 'general'}"
    )
    now = time.monotonic()
    window = _windows[key]

    while window and now - window[0] > _window_seconds:
        window.popleft()

    if len(window) >= _limit_for(request.url.path):
        raise RateLimitException()

    window.append(now)
    return await call_next(request)
