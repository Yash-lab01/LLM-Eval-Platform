"""Application Configuration Management.

Uses Pydantic v2 Settings (pydantic-settings) to validate all environment variables.
Never use `os.getenv` directly in business logic.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/llm_eval",
        description="Async PostgreSQL connection string with asyncpg driver",
    )

    # Redis (3 isolated logical databases per ADR-003)
    redis_cache_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis DB 0: Application cache and real-time WebSocket pub/sub",
    )
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        description="Redis DB 1: Celery task queue message broker",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2", description="Redis DB 2: Celery task result backend"
    )

    # Free-Tier LLM Provider Keys
    gemini_api_key: str | None = Field(default=None, description="Google Gemini free-tier API key")
    groq_api_key: str | None = Field(default=None, description="Groq free-tier API key")

    # Langfuse Observability
    langfuse_host: str = Field(
        default="http://localhost:3000", description="Langfuse server host endpoint"
    )
    langfuse_public_key: str | None = Field(default=None, description="Langfuse project public key")
    langfuse_secret_key: str | None = Field(default=None, description="Langfuse project secret key")

    # Application Settings
    secret_key: str = Field(
        default="development_insecure_secret_key_12345",
        description="Secret key for auth and token signatures",
    )
    environment: str = Field(
        default="development", description="Runtime environment (development, staging, production)"
    )
    api_host: str = Field(default="0.0.0.0", description="FastAPI listening host")
    api_port: int = Field(default=8000, description="FastAPI listening port")


settings = Settings()
