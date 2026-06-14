"""Cookie helpers for the gateway's HttpOnly auth cookie strategy.

The gateway is the only service that ever touches auth cookies.
Downstream services only see the ``X-User-Id`` / ``X-User-Role`` headers
that the gateway injects after validating the cookie.
"""

from fastapi import Request, Response

from src.config.settings import settings

# ── Cookie names ──────────────────────────────────────────────────────────────
ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """Attach both HttpOnly auth cookies to *response*.

    Cookie attributes:
    - ``HttpOnly``  – JS cannot read the value (XSS protection)
    - ``Secure``    – only sent over HTTPS; controlled by ``COOKIE_SECURE`` env var
    - ``SameSite``  – controlled by ``COOKIE_SAME_SITE`` env var (default: lax)
    - ``Path=/``    – sent with every request to the gateway origin
    - ``Max-Age``   – access token uses ``COOKIE_ACCESS_MAX_AGE``,
                      refresh token uses ``COOKIE_REFRESH_MAX_AGE``
    """

    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAME_SITE,  # type: ignore[arg-type]
        max_age=settings.COOKIE_ACCESS_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAME_SITE,  # type: ignore[arg-type]
        max_age=settings.COOKIE_REFRESH_MAX_AGE,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire both auth cookies immediately (sets Max-Age=0)."""

    response.delete_cookie(
        key=ACCESS_COOKIE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAME_SITE,  # type: ignore[arg-type]
        path="/",
    )
    response.delete_cookie(
        key=REFRESH_COOKIE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAME_SITE,  # type: ignore[arg-type]
        path="/",
    )


def get_access_token(request: Request) -> str | None:
    """Return the raw access token string from the HttpOnly cookie, or None."""

    return request.cookies.get(ACCESS_COOKIE)


def get_refresh_token(request: Request) -> str | None:
    """Return the raw refresh token string from the HttpOnly cookie, or None."""

    return request.cookies.get(REFRESH_COOKIE)
