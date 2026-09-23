"""Pydantic v2 schemas for Supported LLM Models and Providers.

Contains the canonical ModelID enum matching LiteLLM prefixes.
Never hardcode model identifiers outside of this module.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ModelID(StrEnum):
    """Canonical model identifiers with exact LiteLLM provider prefixes."""

    # Google Gemini Free Tier
    GEMINI_3_5_FLASH = "gemini/gemini-3.5-flash"
    GEMINI_3_8_FLASH = "gemini/gemini-3.8-flash"

    # Groq Open-Weights Free Tier
    GROQ_GPT_OSS_120B = "groq/openai/gpt-oss-120b"
    GROQ_GPT_OSS_20B = "groq/openai/gpt-oss-20b"
    GROQ_QWEN_27B = "groq/qwen/qwen3.8-27b"
    GROQ_QWEN_32B = "groq/qwen/qwen3-32b"

    # Local Ollama Free Models
    OLLAMA_LLAMA_3_2 = "ollama/llama3.2"
    OLLAMA_MISTRAL = "ollama/mistral"
    OLLAMA_PHI3 = "ollama/phi3"


class ModelProvider(StrEnum):
    """Model host or provider taxonomy."""

    GOOGLE = "google"
    GROQ = "groq"
    OLLAMA = "ollama"


def get_model_provider(model_id: ModelID) -> ModelProvider:
    """Derive provider from ModelID prefix."""
    val = model_id.value
    if val.startswith("gemini/"):
        return ModelProvider.GOOGLE
    if val.startswith("groq/"):
        return ModelProvider.GROQ
    if val.startswith("ollama/"):
        return ModelProvider.OLLAMA
    raise ValueError(f"Unknown provider for model: {model_id}")


class ModelInfo(BaseModel):
    """Metadata regarding a supported model."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    model_id: ModelID = Field(description="LiteLLM model string")
    provider: ModelProvider = Field(description="Underlying provider")
    display_name: str = Field(description="Human-readable display name")
    is_local: bool = Field(default=False, description="Whether the model executes locally")
