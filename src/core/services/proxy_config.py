"""Gateway route mapping and access rules."""

from src.config.settings import settings

ROUTE_MAP: tuple[tuple[str, str], ...] = (
    ("/livekit", settings.INTERVIEW_SERVICE_URL),
    ("/sse", settings.CORE_API_URL),
    ("/auth", settings.CORE_API_URL),
    ("/assessments", settings.CORE_API_URL),
    ("/candidates", settings.CORE_API_URL),
    ("/recruiter", settings.CORE_API_URL),
    ("/notifications", settings.CORE_API_URL),
    ("/interview", settings.CORE_API_URL),
)

UNAUTHENTICATED_ROUTES = {
    ("POST", "/auth/register"),
    ("POST", "/auth/forgot-password"),
    ("POST", "/auth/verify-otp"),
    ("POST", "/auth/resend-otp"),
    ("GET", "/interview/validate-token"),
    ("POST", "/livekit/candidate-token"),
    ("POST", "/livekit/demo-token"),
    ("POST", "/livekit/session-entry"),
    ("POST", "/livekit/session-context"),
}

BLOCKED_ROUTES = ("/internal",)

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

# Cookies are read by the gateway itself - never forwarded to downstream services.
STRIPPED_REQUEST_HEADERS = HOP_BY_HOP_HEADERS | {"cookie"}


def resolve_downstream(path: str) -> str | None:
    """Return the downstream base URL for a request path."""

    for prefix, downstream_url in ROUTE_MAP:
        if path == prefix or path.startswith(f"{prefix}/"):
            return downstream_url
    return None


def matches_prefix(path: str, prefix: str) -> bool:
    """Return whether a route path belongs to an exact prefix boundary."""
    return path == prefix or path.startswith(f"{prefix}/")
