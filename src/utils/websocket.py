import asyncio
import logging

import websockets
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


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
