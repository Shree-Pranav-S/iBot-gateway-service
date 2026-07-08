"""Gateway security utilities."""

from jose import JWTError, jwt

from src.config.settings import settings
from src.core.exceptions.auth import (
    InvalidTokenClaimsException,
    InvalidTokenException,
    MissingAccessTokenException,
)


def decode_access_token(token: str | None) -> dict[str, str]:
    """Decode and validate a raw JWT access token string.

    Raises auth exceptions if the token is missing, malformed, expired,
    or is missing required claims.
    """

    if not token:
        raise MissingAccessTokenException()

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise InvalidTokenException() from exc

    if not payload.get("sub"):
        raise InvalidTokenClaimsException()

    return payload
