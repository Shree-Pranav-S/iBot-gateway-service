"""Gateway security utilities."""

from jose import JWTError, jwt

from src.config.settings import settings
from src.core.exceptions import UnauthorizedException


def decode_access_token(token: str | None) -> dict[str, str]:
    """Decode and validate a raw JWT access token string.

    Raises ``UnauthorizedException`` if the token is missing, malformed,
    expired, or is missing required claims.
    """

    if not token:
        raise UnauthorizedException("Missing access token.")

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise UnauthorizedException("Invalid or expired token.") from exc

    if not payload.get("sub"):
        raise UnauthorizedException("Invalid token claims.")

    return payload
