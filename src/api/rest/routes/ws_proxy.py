"""WebSocket proxy route - bridges interview traffic to the interview-engine service."""

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, WebSocket

from src.config.settings import settings
from src.core.services.ws_proxy_service import validate_candidate_token
from src.utils.proxy_utils import ws_base_url
from src.utils.websocket import _bridge_websocket

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/interview")
async def proxy_interview_websocket(
    websocket: WebSocket,
) -> None:
    """Bridge frontend interview WebSocket traffic to interview-service."""

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        claims = await validate_candidate_token(token, websocket.app.state.http_client)
    except Exception:
        logger.warning("Candidate token validation failed - closing WS with 1008")
        await websocket.close(code=1008)
        return

    await websocket.accept()

    query = dict(websocket.query_params)
    query_string = urlencode(query)
    suffix = "/ws/interview"
    service_url = f"{ws_base_url(settings.INTERVIEW_SERVICE_URL).rstrip('/')}{suffix}"
    if query_string:
        service_url = f"{service_url}?{query_string}"

    headers = {
        "X-Candidate-Id": claims["candidate_id"],
        "X-Assessment-Id": claims["assessment_id"],
        "X-Candidate-Assessment-Id": claims["candidate_assessment_id"],
        "X-Internal-Service": "gateway",
    }

    logger.info(
        "WS proxy established: candidate=%s assessment=%s ca=%s -> %s",
        claims["candidate_id"],
        claims["assessment_id"],
        claims["candidate_assessment_id"],
        service_url,
    )

    await _bridge_websocket(websocket, service_url, headers)


@router.websocket("/ws/interview/demo")
async def proxy_demo_websocket(
    websocket: WebSocket,
) -> None:
    """Bridge frontend demo interview WebSocket traffic to interview-service."""

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        claims = await validate_candidate_token(token, websocket.app.state.http_client)
    except Exception:
        logger.warning("Candidate token validation failed - closing WS with 1008")
        await websocket.close(code=1008)
        return

    await websocket.accept()

    query = dict(websocket.query_params)
    query_string = urlencode(query)
    suffix = "/ws/interview/demo"
    service_url = f"{ws_base_url(settings.INTERVIEW_SERVICE_URL).rstrip('/')}{suffix}"
    if query_string:
        service_url = f"{service_url}?{query_string}"

    headers = {
        "X-Candidate-Id": claims["candidate_id"],
        "X-Assessment-Id": claims["assessment_id"],
        "X-Candidate-Assessment-Id": claims["candidate_assessment_id"],
        "X-Internal-Service": "gateway",
    }

    logger.info(
        "WS demo proxy established: candidate=%s assessment=%s ca=%s -> %s",
        claims["candidate_id"],
        claims["assessment_id"],
        claims["candidate_assessment_id"],
        service_url,
    )

    await _bridge_websocket(websocket, service_url, headers)
