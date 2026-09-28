"""Integration tests for WebSocket real-time token streaming and memory safety cleanup."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient

from backend.main import app


def test_websocket_streaming_and_cleanup():
    """Verify WebSocket client connects, receives streamed tokens, and cleans up Redis subscription on close."""
    run_id = uuid.uuid4()
    run_id_str = str(run_id)

    mock_pubsub = AsyncMock()
    mock_pubsub.psubscribe = AsyncMock()
    mock_pubsub.punsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    sample_token_event = json.dumps(
        {
            "run_id": run_id_str,
            "model_id": "gemini/gemini-3.5-flash",
            "token": "Hello world",
            "is_final": False,
        }
    )
    sample_final_event = json.dumps(
        {
            "run_id": run_id_str,
            "status": "completed",
        }
    )

    async def mock_listen():
        yield {"type": "pmessage", "data": sample_token_event}
        yield {"type": "pmessage", "data": sample_final_event}

    mock_pubsub.listen = mock_listen

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with patch("backend.api.routes.websocket.get_redis_client", return_value=mock_redis):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/eval/{run_id}") as websocket:
            data1 = websocket.receive_text()
            assert "Hello world" in data1

            data2 = websocket.receive_text()
            assert "completed" in data2

        # Verify pattern subscription was established
        mock_pubsub.psubscribe.assert_awaited_once_with(f"run:{run_id_str}:*")
        # Verify CRITICAL cleanup in finally block was called
        mock_pubsub.punsubscribe.assert_awaited_once_with(f"run:{run_id_str}:*")
        mock_pubsub.aclose.assert_awaited_once()


def test_websocket_error_resilience_and_cleanup():
    """Verify that if an exception occurs during streaming, Redis subscription cleanup still executes."""
    run_id = uuid.uuid4()
    run_id_str = str(run_id)

    mock_pubsub = AsyncMock()
    mock_pubsub.psubscribe = AsyncMock()
    mock_pubsub.punsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    async def mock_listen_error():
        raise RuntimeError("Redis connection abruptly dropped")
        yield  # make it a generator

    mock_pubsub.listen = mock_listen_error

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with patch("backend.api.routes.websocket.get_redis_client", return_value=mock_redis):
        client = TestClient(app)
        with client.websocket_connect(f"/ws/eval/{run_id}"):
            # Client connects and exits cleanly after server handles exception
            pass

        # Cleanup MUST still be called in finally
        mock_pubsub.punsubscribe.assert_awaited_once_with(f"run:{run_id_str}:*")
        mock_pubsub.aclose.assert_awaited_once()
