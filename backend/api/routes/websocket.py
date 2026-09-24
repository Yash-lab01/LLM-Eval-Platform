"""WebSocket route for real-time evaluation streaming.

Subscribes to Redis pub/sub channels and forwards live model tokens to connected clients.
Ensures memory safety with try/finally pubsub cleanup.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Streaming"])


@router.websocket("/ws/eval/{run_id}")
async def websocket_eval_stream(websocket: WebSocket, run_id: UUID) -> None:
    """Stream model response tokens and evaluation events in real time.

    Connects to Redis DB 0 pub/sub on channel pattern `run:{run_id}:*`.
    Relays all events as JSON strings to the WebSocket client.
    """
    await websocket.accept()
    run_id_str = str(run_id)
    redis_client = get_redis_client()
    pubsub = redis_client.pubsub()

    pattern = f"run:{run_id_str}:*"
    logger.info(f"WebSocket client connected for run {run_id_str}, subscribing to {pattern}")

    try:
        await pubsub.psubscribe(pattern)
        async for message in pubsub.listen():
            # In pattern subscriptions, message type is 'pmessage'
            if message.get("type") in ("message", "pmessage"):
                data = message.get("data")
                if data:
                    await websocket.send_text(data)
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from run {run_id_str}")
    except Exception as exc:
        logger.warning(f"WebSocket streaming error for run {run_id_str}: {exc}")
    finally:
        # CRITICAL: Always clean up Redis subscriptions to prevent connection/memory leaks
        try:
            await pubsub.punsubscribe(pattern)
            await pubsub.aclose()
            logger.debug(f"Cleaned up Redis subscription for run {run_id_str}")
        except Exception as cleanup_exc:
            logger.warning(f"Error during Redis pubsub cleanup: {cleanup_exc}")
