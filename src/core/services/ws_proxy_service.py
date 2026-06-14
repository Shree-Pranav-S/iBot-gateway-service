"""WebSocket proxy business logic for the gateway service.

Handles candidate token validation before bridging WebSocket connections
to the interview-engine service. Route handlers in ``routes/ws_proxy.py``
delegate to this service.
"""

import httpx

from src.config.settings import settings


async def validate_candidate_token(
    token: str, client: httpx.AsyncClient
) -> dict[str, str]:
    """Call core-api's internal endpoint to resolve an invitation token.
      Returns a dict with ``candidate_id`` and ``assessment_id`` on success.
    Raises ``httpx.HTTPStatusError`` if the token is invalid or the call fails.
    """
    response = await client.get(
        f"{settings.CORE_API_URL.rstrip('/')}/internal/validate-candidate-token",
        params={"token": token},
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", payload)
    return {
        "candidate_id": str(data["candidate_id"]),
        "assessment_id": str(data["assessment_id"]),
    }
