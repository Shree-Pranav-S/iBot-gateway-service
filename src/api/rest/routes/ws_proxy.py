"""WebSocket proxy route — bridges interview traffic to the interview-engine service."""

import asyncio
import logging
from urllib.parse import urlencode

import websockets
import websockets.exceptions
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config.settings import settings
from src.core.services.ws_proxy_service import validate_candidate_token
from src.utils.proxy_utils import ws_base_url

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
        logger.warning("Candidate token validation failed — closing WS with 1008")
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
        "X-Internal-Service": "gateway",
    }

    logger.info(
        "WS proxy established: candidate=%s assessment=%s -> %s",
        claims["candidate_id"],
        claims["assessment_id"],
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
        logger.warning("Candidate token validation failed — closing WS with 1008")
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
        "X-Internal-Service": "gateway",
    }

    logger.info(
        "WS demo proxy established: candidate=%s assessment=%s -> %s",
        claims["candidate_id"],
        claims["assessment_id"],
        service_url,
    )

    await _bridge_websocket(websocket, service_url, headers)


async def _bridge_websocket(
    websocket: WebSocket, service_url: str, headers: dict[str, str]
) -> None:
    """Helper to bridge a client WebSocket connection to the downstream service."""
    try:
        async with websockets.connect(service_url, extra_headers=headers) as service_ws:

            async def client_to_service() -> None:
                """Forward frames from the browser client to the interview engine."""
                while True:
                    try:
                        message = await websocket.receive()
                    except WebSocketDisconnect:
                        break
                    if message.get("type") == "websocket.disconnect":
                        break
                    if "bytes" in message and message["bytes"]:
                        await service_ws.send(message["bytes"])
                    elif "text" in message and message["text"]:
                        await service_ws.send(message["text"])

                # Signal the backend we are done
                try:
                    await service_ws.close()
                except Exception:
                    pass

            async def service_to_client() -> None:
                """Forward frames from the interview engine back to the browser."""
                try:
                    async for message in service_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    pass

            tasks = {
                asyncio.create_task(client_to_service(), name="c2s"),
                asyncio.create_task(service_to_client(), name="s2c"),
            }
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in done:
                try:
                    task.result()
                except (
                    WebSocketDisconnect,
                    websockets.exceptions.ConnectionClosed,
                    asyncio.CancelledError,
                ):
                    pass
                except Exception:
                    logger.exception("Unhandled error in WS proxy task")

    except (websockets.exceptions.WebSocketException, OSError) as exc:
        logger.warning("Could not connect to interview-engine: %s", exc)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
