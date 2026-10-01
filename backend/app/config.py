"""Runtime configuration — env vars only, safe defaults for offline local runs (D-004).

Every value is documented in `.env.example`. Nothing here is a secret.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Initial values (BUILD_SPEC §3.4 + audit T2). Recalibrated and published in eval/REPORT.md."""

    hadith_partial: float = 0.75  # hadith: sim ≥ → partial_match
    hadith_review: float = 0.70  # hadith: sim ≥ → needs_review, else not_found
    quran_review: float = 0.60  # quran: sim ≥ → needs_review (never partial), else not_found
    short_quote_tokens: int = 5  # quotes shorter than this: only exact → found; review needs ≥ short_review
    short_review: float = 0.75
    min_tokens_quran: int = 2  # ADR-003 / E-012
    min_tokens_hadith: int = 3


@dataclass(frozen=True, slots=True)
class Settings:
    index_dir: Path = field(
        default_factory=lambda: Path(_env("BASIRA_INDEX_DIR", str(REPO_ROOT / "corpus" / "index")))
    )
    manifest_path: Path = field(
        default_factory=lambda: Path(_env("BASIRA_MANIFEST", str(REPO_ROOT / "corpus" / "manifest.json")))
    )
    messages_dir: Path = field(
        default_factory=lambda: Path(_env("BASIRA_MESSAGES_DIR", str(REPO_ROOT / "messages")))
    )
    llm_provider: str = field(
        default_factory=lambda: _env("LLM_PROVIDER", "mock")
    )  # mock | openai-compatible
    vision_provider: str = field(default_factory=lambda: _env("VISION_PROVIDER", "mock"))
    hadeethenc_mode: str = field(default_factory=lambda: _env("HADEETHENC_MODE", "link"))  # link | embed
    ohd_mode: str = field(default_factory=lambda: _env("OHD_MODE", "display"))  # display | off (kill-switch)
    retrieval_vectors: bool = field(default_factory=lambda: _env_bool("RETRIEVAL_VECTORS", False))
    anchor_detect: bool = field(default_factory=lambda: _env_bool("ANCHOR_DETECT", True))
    static_dir: Path | None = field(
        default_factory=lambda: Path(_env("BASIRA_STATIC_DIR", str(REPO_ROOT / "frontend" / "dist"))) or None
    )
    snapshot_write: bool = field(default_factory=lambda: _env_bool("BASIRA_SNAPSHOT_WRITE", True))
    max_text_chars: int = field(default_factory=lambda: int(_env("BASIRA_MAX_TEXT_CHARS", "5000")))
    max_quotes: int = 30
    max_positions_shown: int = 5
    rate_limit_per_min: int = field(default_factory=lambda: int(_env("BASIRA_RATE_LIMIT_PER_MIN", "30")))
    eval_key: str = field(default_factory=lambda: _env("BASIRA_EVAL_KEY", ""))  # X-Eval-Key bypass (T5)
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in _env("BASIRA_CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
        )
    )
    build_sha: str = field(default_factory=lambda: _env("BUILD_SHA", "dev"))
    thresholds: Thresholds = field(default_factory=Thresholds)


settings = Settings()
