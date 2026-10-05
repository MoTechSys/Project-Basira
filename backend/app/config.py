"""إعدادات التشغيل — متغيرات بيئة فقط مع قيم افتراضية آمنة للتشغيل المحلي (D-004).

كل قيمة موثّقة في `.env.example`. لا يوجد هنا أي سر أو مفتاح.

ADR-004: تجنّب أي بنية Settings معقّدة (BaseSettings من pydantic-settings) للحفاظ على
صفر tomli/toml dependency وتسريع cold-start في بيئات الـ serverless.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# جذر المستودع — ثلاث مستويات فوق هذا الملف (backend/app/config.py)
REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# قارئات متغيرات البيئة
# ---------------------------------------------------------------------------
def _env(name: str, default: str) -> str:
    """قارئ متغير بيئة نصي مع fallback."""
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool) -> bool:
    """قارئ متغير بيئة منطقي — نقبل 1/true/yes/on (case-insensitive)."""
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# العتبات (Thresholds) — القيم الابتدائية ومحطّة إعادة المعايرة في eval/REPORT.md
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Thresholds:
    """عتبات مطابقة الاقتباسات (BUILD_SPEC §3.4 + audit T2)."""

    hadith_partial: float = 0.75  # حديث: sim ≥ → partial_match
    hadith_review: float = 0.70   # حديث: sim ≥ → needs_review وإلا not_found
    quran_review: float = 0.60    # قرآن: sim ≥ → needs_review (never partial)
    short_quote_tokens: int = 5   # اقتباسات أقصر من هذا: exact فقط لـ found
    short_review: float = 0.75
    min_tokens_quran: int = 2     # ADR-003 / E-012
    min_tokens_hadith: int = 3


# ---------------------------------------------------------------------------
# الإعدادات الرئيسية
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Settings:
    """إعدادات التشغيل الكاملة — غير قابلة للتعديل بعد الـ init (frozen)."""

    # ─── مسارات الذخيرة ─────────────────────────────────────────────────
    index_dir: Path = field(
        default_factory=lambda: Path(
            _env("BASIRA_INDEX_DIR", str(REPO_ROOT / "corpus" / "index"))
        )
    )
    manifest_path: Path = field(
        default_factory=lambda: Path(
            _env("BASIRA_MANIFEST", str(REPO_ROOT / "corpus" / "manifest.json"))
        )
    )
    messages_dir: Path = field(
        default_factory=lambda: Path(
            _env("BASIRA_MESSAGES_DIR", str(REPO_ROOT / "messages"))
        )
    )

    # ─── الموفّرون (Providers) ──────────────────────────────────────────
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "mock"))
    vision_provider: str = field(default_factory=lambda: _env("VISION_PROVIDER", "mock"))

    # ─── أوضاع الاستخدام للمصادر ────────────────────────────────────────
    hadeethenc_mode: str = field(default_factory=lambda: _env("HADEETHENC_MODE", "link"))
    ohd_mode: str = field(default_factory=lambda: _env("OHD_MODE", "display"))  # kill-switch
    retrieval_vectors: bool = field(default_factory=lambda: _env_bool("RETRIEVAL_VECTORS", False))
    anchor_detect: bool = field(default_factory=lambda: _env_bool("ANCHOR_DETECT", True))

    # ─── الواجهة الأمامية ───────────────────────────────────────────────
    static_dir: Path | None = field(
        default_factory=lambda: Path(
            _env("BASIRA_STATIC_DIR", str(REPO_ROOT / "frontend" / "dist"))
        )
        or None
    )

    # ─── اللقطات والتخزين ───────────────────────────────────────────────
    snapshot_write: bool = field(default_factory=lambda: _env_bool("BASIRA_SNAPSHOT_WRITE", True))

    # ─── حدود الطلب ─────────────────────────────────────────────────────
    max_text_chars: int = field(default_factory=lambda: int(_env("BASIRA_MAX_TEXT_CHARS", "5000")))
    max_quotes: int = 30
    max_positions_shown: int = 5

    # ─── Rate Limiting ─────────────────────────────────────────────────
    rate_limit_per_min: int = field(default_factory=lambda: int(_env("BASIRA_RATE_LIMIT_PER_MIN", "30")))

    # X-Eval-Key يسمح بتجاوز rate limit للـ harness فقط (T5)
    eval_key: str = field(default_factory=lambda: _env("BASIRA_EVAL_KEY", ""))

    # B12: X-Forwarded-For يُحترم فقط إذا الـ peer من هذه القائمة
    trusted_proxies: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            p.strip()
            for p in _env("BASIRA_TRUSTED_PROXIES", "").split(",")
            if p.strip()
        )
    )

    # ─── CORS ──────────────────────────────────────────────────────────
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in _env("BASIRA_CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        )
    )

    # ─── Metadata ─────────────────────────────────────────────────────
    build_sha: str = field(default_factory=lambda: _env("BUILD_SHA", "dev"))
    thresholds: Thresholds = field(default_factory=Thresholds)

    # ─── MCP ──────────────────────────────────────────────────────────
    # Developer gate (docs/API.md, docs/INTEGRATIONS.md §3.1): MCP على /mcp
    mcp_enabled: bool = field(default_factory=lambda: _env_bool("BASIRA_MCP", False))


# instance عام للاستخدام في بقية الكود
settings = Settings()
