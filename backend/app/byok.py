"""Server-side model configuration (E-051): one Genspark key, one model, set once from ``/settings``.

The key is entered once in the UI, stored **on the server** (``backend/.runtime/model.json``, mode 0600,
git-ignored) and used by the live providers for extraction (span proposals), OCR and the English picker.
It never travels in request headers, never appears in any response (``/v1/models`` only reports
``configured: true/false`` and a masked tail), never in logs (class-only logging everywhere).

The deterministic core does not depend on the model: the model only proposes *which substrings of the
user's own text* to check, reads images, and picks among approved translations. Same input ⇒ same
``determinism_hash`` whatever model is configured.

Catalog numbers were **measured on 2026-10-03** on this repository's real extraction prompt and a real OCR
image (``docs/MODELS.md``, ``scripts/bench_models.py``) — they are not vendor claims.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from app.english_gate import EnglishPicker
from app.providers.base import LLMClient, VisionClient

log = logging.getLogger(__name__)

GENSPARK_BASE = "https://www.genspark.ai/api/llm_proxy/v1"
ALLOWED_BASES: frozenset[str] = frozenset({GENSPARK_BASE, "https://api.openai.com/v1"})

Tier = Literal["flagship", "balanced", "fast"]


@dataclass(frozen=True, slots=True)
class ModelInfo:
    id: str
    label: str
    vendor: str
    tier: Tier
    cost_x: float
    extract_exact: int  # /6 extraction cases exact-span
    extract_p50_ms: int
    ocr_ok: bool
    ocr_ms: int | None
    vision: bool
    note_ar: str
    note_en: str


CATALOG: tuple[ModelInfo, ...] = (
    ModelInfo(
        "gpt-5.4-mini",
        "GPT-5.4 mini",
        "OpenAI",
        "fast",
        0.3,
        6,
        1220,
        True,
        1343,
        True,
        "الأدق والأسرع في قياسنا: 6/6 مواضع مطابقة، ~1.2 ث، قراءة الصورة مطابقة وبأقل تكلفة. الخيار الافتراضي.",
        "Best measured accuracy and speed: 6/6 exact spans, ~1.2 s, faithful OCR, lowest cost. Default.",
    ),
    ModelInfo(
        "glm-5p3-flash-low",
        "GLM-5.3 Flash (low)",
        "Z.ai",
        "fast",
        0.15,
        6,
        1517,
        True,
        1610,
        True,
        "6/6 مواضع، ~1.5 ث، أرخص خيار مقيس. قراءة الصورة مطابقة مع خطأ إملائي واحد في كلمة خارج الاقتباس.",
        "6/6 spans, ~1.5 s, cheapest measured option. OCR faithful with one spelling slip outside the quote.",
    ),
    ModelInfo(
        "gpt-6-luna",
        "GPT-6 Luna",
        "OpenAI",
        "fast",
        0.1,
        6,
        2690,
        True,
        4619,
        True,
        "6/6 مواضع، ~2.7 ث. قراءة الصورة مطابقة لكنها أبطأ (~4.6 ث).",
        "6/6 spans, ~2.7 s. Faithful OCR but slower (~4.6 s).",
    ),
    ModelInfo(
        "claude-sonnet-5-5",
        "Claude Sonnet 5.5",
        "Anthropic",
        "balanced",
        2.0,
        5,
        3016,
        True,
        1676,
        True,
        "5/6 (تجاهل قولًا غير مُعلَّم — وهذا ما يفعله المحرك أصلًا)، ~3 ث، أسرع قراءة صورة بين النماذج الكبيرة.",
        "5/6 (skipped an unmarked saying — the rule engine covers it), ~3 s, fastest OCR among large models.",
    ),
    ModelInfo(
        "gpt-6-sol",
        "GPT-6 Sol",
        "OpenAI",
        "balanced",
        2.0,
        5,
        2069,
        True,
        2662,
        True,
        "5/6، أسرع النماذج الكبيرة في الاستخراج (~2.1 ث)، قراءة صورة مطابقة.",
        "5/6, fastest large model on extraction (~2.1 s), faithful OCR.",
    ),
    ModelInfo(
        "claude-opus-5-5",
        "Claude Opus 5.5",
        "Anthropic",
        "flagship",
        4.0,
        4,
        4530,
        True,
        2545,
        True,
        "أقوى نموذج عام لكنه ليس الأفضل هنا: 4/6 ورفض مرة الإجابة بصيغة JSON (المحرك يُكمل بالقواعد). ~4.5 ث. قراءة الصورة مطابقة.",
        "Strongest general model but not the best here: 4/6 and once refused the JSON format (rules take over). ~4.5 s. Faithful OCR.",
    ),
    ModelInfo(
        "claude-fable-5-1",
        "Claude Fable 5.1",
        "Anthropic",
        "flagship",
        10.0,
        5,
        3833,
        True,
        None,
        True,
        "5/6، ~3.8 ث لكن بتذبذب يصل إلى 11 ث. الأغلى (10×). لا مبرر لاستخدامه هنا.",
        "5/6, ~3.8 s with spikes to 11 s. Most expensive (10×). Not justified for this task.",
    ),
    ModelInfo(
        "gpt-5.5",
        "GPT-5.5",
        "OpenAI",
        "flagship",
        5.0,
        4,
        7486,
        True,
        None,
        True,
        "4/6 وأبطأ النماذج الكبيرة (~7.5 ث)؛ أدرج عبارة العزو «رواه البخاري» كاقتباس.",
        "4/6 and the slowest flagship (~7.5 s); listed the attribution «رواه البخاري» as a quote.",
    ),
    ModelInfo(
        "gpt-5.4",
        "GPT-5.4",
        "OpenAI",
        "balanced",
        3.0,
        4,
        4124,
        True,
        6715,
        True,
        "4/6، ~4.1 ث مع ذروة 8 ث. كان النموذج المرجعي في E-030؛ تجاوزته النماذج الأخف.",
        "4/6, ~4.1 s with an 8 s spike. Was the E-030 reference; lighter models now beat it.",
    ),
    ModelInfo(
        "gpt-6-astra",
        "GPT-6 Astra",
        "OpenAI",
        "flagship",
        10.0,
        4,
        3022,
        True,
        None,
        True,
        "4/6، ~3 ث. 10× التكلفة بلا مكسب مقيس على هذه المهمة.",
        "4/6, ~3 s. 10× cost with no measured gain on this task.",
    ),
)
CATALOG_IDS: frozenset[str] = frozenset(m.id for m in CATALOG)
DEFAULT_MODEL = "gpt-5.4-mini"

_KEY_RE = re.compile(r"^[A-Za-z0-9_\-\.]{16,512}$")


class ByokError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ModelConfig:
    api_key: str
    model: str
    base_url: str = GENSPARK_BASE

    def __repr__(self) -> str:  # never leak the key through repr/logging
        return f"ModelConfig(model={self.model!r}, base_url={self.base_url!r}, api_key='***')"

    @property
    def masked(self) -> str:
        return "…" + self.api_key[-4:] if len(self.api_key) >= 8 else "…"


def validate(api_key: str, model: str, base_url: str | None = None) -> ModelConfig:
    key = (api_key or "").strip()
    if not _KEY_RE.match(key):
        raise ByokError("byok_key_invalid")
    model = (model or DEFAULT_MODEL).strip()
    if model not in CATALOG_IDS:
        raise ByokError("byok_model_unknown")
    base = (base_url or GENSPARK_BASE).strip().rstrip("/")
    if base not in ALLOWED_BASES:
        raise ByokError("byok_base_not_allowed")
    return ModelConfig(key, model, base)


# ----------------------------------------------------------------------------- persistence (server-side)


def config_path(repo_root: Path) -> Path:
    return Path(os.environ.get("BASIRA_MODEL_CONFIG", str(repo_root / "backend" / ".runtime" / "model.json")))


def load_config(path: Path) -> ModelConfig | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return validate(str(raw.get("api_key", "")), str(raw.get("model", "")), raw.get("base_url"))
    except (OSError, ValueError, ByokError):
        return None


def save_config(path: Path, cfg: ModelConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"api_key": cfg.api_key, "model": cfg.model, "base_url": cfg.base_url}), encoding="utf-8"
    )
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def clear_config(path: Path) -> None:
    path.unlink(missing_ok=True)


# ----------------------------------------------------------------------------- providers / verification


def build_providers(cfg: ModelConfig) -> tuple[LLMClient, VisionClient, EnglishPicker]:
    from app.providers.openai_compat import (  # noqa: PLC0415
        OpenAICompatLLM,
        OpenAICompatPicker,
        OpenAICompatVision,
    )

    llm = OpenAICompatLLM(base_url=cfg.base_url, api_key=cfg.api_key, model=cfg.model)
    vision = OpenAICompatVision(base_url=cfg.base_url, api_key=cfg.api_key, model=cfg.model)
    picker = OpenAICompatPicker(base_url=cfg.base_url, api_key=cfg.api_key, model=cfg.model)
    return llm, vision, picker


def catalog_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": m.id,
            "label": m.label,
            "vendor": m.vendor,
            "tier": m.tier,
            "cost_x": m.cost_x,
            "extract_exact": m.extract_exact,
            "extract_total": 6,
            "extract_p50_ms": m.extract_p50_ms,
            "ocr_ok": m.ocr_ok,
            "ocr_ms": m.ocr_ms,
            "vision": m.vision,
            "note_ar": m.note_ar,
            "note_en": m.note_en,
            "default": m.id == DEFAULT_MODEL,
        }
        for m in CATALOG
    ]


async def verify_key(cfg: ModelConfig, timeout_s: float = 15.0) -> dict[str, Any]:
    """One 5-token completion proves the key+model pair works. The reason is a class (``auth`` /
    ``model`` / ``transport``), never the upstream body."""
    body = {
        "model": cfg.model,
        "temperature": 0,
        "max_tokens": 5,
        "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
    }
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(
                cfg.base_url + "/chat/completions",
                headers={"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"},
                json=body,
            )
    except httpx.HTTPError as exc:
        return {"ok": False, "reason": "transport", "detail": exc.__class__.__name__}
    ms = int((time.perf_counter() - t0) * 1000)
    reason = _classify(r)
    if reason is not None:
        return {"ok": False, "reason": reason, "latency_ms": ms}
    return {"ok": True, "model": cfg.model, "latency_ms": ms}


def _classify(r: httpx.Response) -> str | None:
    if r.status_code in (401, 403):
        return "auth"
    if r.status_code == 400:
        return "model"
    if r.status_code != 200:
        return "transport"
    try:
        content = r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        return "transport"
    return None if isinstance(content, str) else "transport"
