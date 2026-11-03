"""Application settings, loaded from environment variables (and an optional .env file).

Secrets are only read from the environment and are never returned by the API.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PoolerMode = Literal["auto", "direct", "session", "transaction"]
SslMode = Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AgentForge"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Database: Supabase (managed PostgreSQL) in deployed environments, the local Docker
    # PostgreSQL for offline development. SQLite is accepted for the automated tests only.
    database_url: str = "postgresql+psycopg://agentforge:agentforge@127.0.0.1:5432/agentforge"
    # `None` leaves libpq's default; Supabase requires "require" or stricter.
    database_ssl_mode: SslMode | None = None
    # Supabase's transaction pooler (port 6543) cannot use prepared statements.
    # "auto" detects it from the port.
    database_pooler_mode: PoolerMode = "auto"
    database_connect_timeout_seconds: int = Field(default=10, ge=1, le=120)
    database_echo: bool = False

    # HTTP
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    max_request_bytes: int = 1_000_000

    # Authentication (Supabase Auth). Only the public project URL is needed: tokens are
    # verified with the project's published signing keys. Unset = all protected routes 503.
    supabase_url: str | None = None
    auth_audience: str = "authenticated"

    # LLM provider. Only the presence of the key is ever reported.
    #   google   - Gemini via langchain-google-genai (needs LLM_API_KEY)
    #   ollama   - local model via Ollama (LLM_BASE_URL, default http://127.0.0.1:11434)
    #   scripted - deterministic demo model; produces a fixed sample project, no AI
    llm_provider: Literal["google", "ollama", "scripted"] | None = None
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    llm_timeout_seconds: int = Field(default=180, ge=5, le=900)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    # Hard cap on one answer's length. Without it a model stuck in a repetition loop keeps
    # generating (observed: 56 minutes and 164k tokens for one call).
    llm_max_output_tokens: int = Field(default=8192, ge=256, le=65_536)
    # Wall-clock budget for one agent call including its retries.
    llm_call_budget_seconds: int = Field(default=600, ge=30, le=3600)
    # Ollama "thinking" models (Qwen3 family): false turns it off, which keeps answers within
    # the output cap. Unset = the model's default (and nothing is sent to models without it).
    llm_thinking: bool | None = None
    # Optional pricing for cost estimates. Unset = cost reported as unknown, never guessed.
    llm_input_usd_per_mtok: float | None = Field(default=None, ge=0)
    llm_output_usd_per_mtok: float | None = Field(default=None, ge=0)

    # Embeddings for retrieval (Phase 4). "hash" is a deterministic local embedder.
    embedding_provider: Literal["google", "ollama", "hash"] = "hash"
    embedding_model: str | None = None
    # Retrieval pipeline: dense + sparse candidates, fused, reranked, gated, top k.
    rag_mode: Literal["dense", "sparse", "hybrid"] = "hybrid"
    rag_reranker: Literal["lexical", "llm", "none"] = "lexical"
    rag_candidates: int = Field(default=20, ge=1, le=100)
    rag_top_k: int = Field(default=4, ge=1, le=20)
    rag_min_score: float = Field(default=0.15, ge=0.0, le=1.0)

    # Workflow policy
    max_debug_iterations: int = Field(default=3, ge=0, le=10)
    max_review_corrections: int = Field(default=1, ge=0, le=3)

    # Run execution
    worker_enabled: bool = True
    worker_concurrency: int = Field(default=2, ge=1, le=16)
    worker_poll_seconds: float = Field(default=1.0, gt=0, le=30)
    run_heartbeat_timeout_seconds: int = Field(default=120, ge=10, le=3600)
    max_active_runs_per_user: int = Field(default=2, ge=1, le=20)
    max_runs_per_user_per_hour: int = Field(default=20, ge=1, le=1000)

    # Sandbox (Docker). Generated code never runs on the backend host.
    sandbox_enabled: bool = True
    sandbox_image: str = "agentforge-sandbox-python:2"
    # Throwaway PostgreSQL for projects with a database (pulled once: docker pull postgres:17-alpine).
    sandbox_database_image: str = "postgres:17-alpine"
    sandbox_timeout_seconds: int = Field(default=120, ge=10, le=900)
    sandbox_memory_mb: int = Field(default=512, ge=128, le=8192)
    sandbox_cpus: float = Field(default=1.0, gt=0, le=8)

    @field_validator(
        "database_ssl_mode",
        "supabase_url",
        "llm_provider",
        "llm_model",
        "llm_api_key",
        "llm_base_url",
        "embedding_model",
        "llm_thinking",
        "llm_input_usd_per_mtok",
        "llm_output_usd_per_mtok",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value):
        # Compose and CI often pass `VAR=` for "not set".
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def llm_api_key_present(self) -> bool:
        return self.llm_api_key is not None and bool(self.llm_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
