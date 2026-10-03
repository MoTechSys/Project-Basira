"""Runtime configuration loaded from environment variables.

All settings have sensible defaults for local development.
Secrets (API keys) must come from .env, never from code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    rate_limit: int = 30  # requests per minute per IP

    llm_provider: str = "mock"  # mock | openai-compat
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"

    vision_provider: str = "mock"

    corpus_dir: Path = Path("./corpus/data")
    snapshot_dir: Path = Path("./corpus/snapshot")


def load_settings() -> Settings:
    """Build Settings from environment, with safe defaults."""
    return Settings(
        host=os.getenv("BASIRA_HOST", "0.0.0.0"),
        port=int(os.getenv("BASIRA_PORT", "8000")),
        log_level=os.getenv("BASIRA_LOG_LEVEL", "info"),
        rate_limit=int(os.getenv("BASIRA_RATE_LIMIT", "30")),
        llm_provider=os.getenv("BASIRA_LLM_PROVIDER", "mock"),
        llm_api_key=os.getenv("BASIRA_LLM_API_KEY"),
        llm_base_url=os.getenv("BASIRA_LLM_BASE_URL"),
        llm_model=os.getenv("BASIRA_LLM_MODEL", "gpt-4o-mini"),
        vision_provider=os.getenv("BASIRA_VISION_PROVIDER", "mock"),
        corpus_dir=Path(os.getenv("BASIRA_CORPUS_DIR", "./corpus/data")),
        snapshot_dir=Path(os.getenv("BASIRA_SNAPSHOT_DIR", "./corpus/snapshot")),
    )
