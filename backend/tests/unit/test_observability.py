"""Unit tests for the Observability and Tracing service."""

import os
import uuid
from unittest.mock import patch

import litellm

from backend.services.observability import (
    build_trace_metadata,
    is_observability_active,
    setup_observability,
)


def test_setup_observability_disabled():
    """Verify observability initializes cleanly in disabled mode when keys are absent."""
    with patch("backend.services.observability.settings") as mock_settings:
        mock_settings.langfuse_public_key = None
        mock_settings.langfuse_secret_key = None

        result = setup_observability()
        assert result is False
        assert is_observability_active() is False


def test_setup_observability_enabled():
    """Verify Langfuse callbacks are registered in LiteLLM when keys are configured."""
    with patch("backend.services.observability.settings") as mock_settings:
        mock_settings.langfuse_public_key = "pk-test-12345"
        mock_settings.langfuse_secret_key = "sk-test-67890"
        mock_settings.langfuse_host = "https://cloud.langfuse.com"

        result = setup_observability()
        assert result is True
        assert is_observability_active() is True
        assert os.environ.get("LANGFUSE_PUBLIC_KEY") == "pk-test-12345"
        assert os.environ.get("LANGFUSE_SECRET_KEY") == "sk-test-67890"
        assert "langfuse" in litellm.success_callback
        assert "langfuse" in litellm.failure_callback


def test_build_trace_metadata():
    """Verify trace metadata maps consumer session and tagging correctly."""
    run_id = uuid.uuid4()
    meta = build_trace_metadata(
        run_id=run_id,
        model_id="gemini/gemini-3.5-flash",
        task_type="code_generation",
        consumer_id="project-agent-1",
        extra_tags=["benchmark", "v2"],
    )

    assert meta["run_id"] == str(run_id)
    assert meta["model_id"] == "gemini/gemini-3.5-flash"
    assert meta["task_type"] == "code_generation"
    assert meta["session_id"] == "project-agent-1"
    assert meta["trace_user_id"] == "project-agent-1"
    assert "code_generation" in meta["tags"]
    assert "benchmark" in meta["tags"]
    assert "v2" in meta["tags"]
