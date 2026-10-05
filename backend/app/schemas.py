"""Pydantic schemas للـ public API — بصيرة v0.1.

يُنظّم هذا الملف البنى التالية:
- Status (الأربع حالات I1-I9) + Kind (أنواع الاقتباسات)
- CheckRequest / CheckResponse (العقد مع الواجهة)
- Match / Quote / Grade / Diff (البنى الداخلية)
- openapi_examples() لتغذية /docs

المرجع:
- ADR 0001 (four-state model)
- ADR 0002 (deterministic matching)
- ADR 0003 (BYOK provider keys)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# أمثلة OpenAPI — تُقرأ من ملف JSON خارجي (openapi_examples.json)
# ---------------------------------------------------------------------------
_EXAMPLES_FILE = Path(__file__).with_name("openapi_examples.json")


@lru_cache(maxsize=1)
def openapi_examples() -> dict[str, dict[str, Any]]:
    """أزواج طلب/رد حقيقية للحالات الأربع، مُلتقطة من مجموعة اختبار كاملة.

    تُستخدم في Swagger UI عبر CheckRequest.model_config و docs/API.md.
    تعود بمعجم فارغ إذا الملف غير موجود — fallback آمن.
    """
    if not _EXAMPLES_FILE.exists():
        return {}
    raw: dict[str, dict[str, Any]] = json.loads(_EXAMPLES_FILE.read_text(encoding="utf-8"))
    return raw


# ---------------------------------------------------------------------------
# الأنواع المحدودة (Literal types) — نستخدم Literal بدل Enum لأن Pydantic v2
# يُولّد JSON Schema أنظف ويحافظ على سهولة التسلسل.
# ---------------------------------------------------------------------------
Status = Literal["found", "partial_match", "needs_review", "not_found"]

Kind = Literal["quran", "hadith_matn", "isnad", "attributed_saying", "unknown"]

# أسباب NEEDS_REVIEW — نُعلن قائمة مغلقة (لا نقبل أي سبب حر)
ReviewReason = Literal[
    "near_miss",
    "orthographic_difference",
    "short_quote",
    "stage_failure",
    "validator_reject",
    "non_arabic",
    "image_unconfirmed",
    "diacritic_difference",
    "diacritic_unverified",
    "foreign_material",
    "validator_unproven",
    "attribution_only",
]

CorpusName = Literal["tanzil", "ohd", "hadeethenc"]


# ---------------------------------------------------------------------------
# خيارات الطلب
# ---------------------------------------------------------------------------
class CheckOptions(BaseModel):
    """خيارات اختيارية للـ /v1/check."""

    max_candidates: int = Field(default=3, ge=1, le=5)


class CheckRequest(BaseModel):
    """جسم الطلب لـ POST /v1/check."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [v["request"] for v in openapi_examples().values()]
        }
    )

    text: str = Field(min_length=1, max_length=5000)
    ui_lang: Literal["ar", "en"] = "ar"
    source_modality: Literal["text", "image"] = "text"
    options: CheckOptions = Field(default_factory=CheckOptions)


# ---------------------------------------------------------------------------
# البنى الفرعية
# ---------------------------------------------------------------------------
class Span(BaseModel):
    """نطاق [start, end) داخل النص الأصلي بالأحرف (code points)."""

    start: int
    end: int


class DiffOpModel(BaseModel):
    """عملية diff واحدة بين الاقتباس والمصدر (char-level + letter-level)."""

    op: Literal["equal", "replace", "insert", "delete"]
    quote_range: list[int]
    source_range: list[int]
    quote_chars: list[int]
    source_chars: list[int]
    # نطاقات letter-level داخل العملية (للتظليل اللوني وفروق الحركات)
    quote_letters: list[list[int]] = Field(default_factory=list)
    source_letters: list[list[int]] = Field(default_factory=list)


class Grade(BaseModel):
    """تخريج حديث من HadeethEnc فقط — لا نُنشئ تخريجاً جديداً أبداً (I4)."""

    text: str
    takhrij: str
    source: Literal["HadeethEnc"] = "HadeethEnc"
    version: str
    url: str


class Link(BaseModel):
    name: str
    url: str


class SourceSegment(BaseModel):
    """B07: one corpus record of a multi-ayah quote, verbatim — never a generated joined line (V1 checks each)."""

    ref: dict[str, Any]
    ref_label_ar: str
    ref_label_en: str
    source_text: str  # the record's display field, byte-exact
    source_url: str


class Match(BaseModel):
    corpus: CorpusName
    ref: dict[str, Any]
    ref_label_ar: str
    ref_label_en: str
    collection_tier: Literal["quran", "sahihain", "other_nine", "hadeethenc"]
    source_text: str
    source_text_range: list[int] | None = None  # char range of the matched window inside source_text
    source_url: str
    links: list[Link] = Field(default_factory=list)
    diff: list[DiffOpModel] = Field(default_factory=list)
    diff_kinds: list[str] = Field(default_factory=list)
    score: float
    grade: Grade | None = None
    continues_to: dict[str, Any] | None = None  # Quran: last ayah ref when the quote spans several
    # B07: every ayah the quote covers, in Mushaf order, each one a verbatim record (empty unless > 1 ayah)
    source_segments: list[SourceSegment] = Field(default_factory=list)


class SegmentModel(BaseModel):
    """One typed part of a citation (IslamicEval 2026 schema): char offsets into the request text."""

    type: Literal["Ayah", "matn", "isnad", "claimed_source"]
    start: int
    end: int


class ClaimedSource(BaseModel):
    raw: str
    parsed: dict[str, Any]


class EnglishCandidate(BaseModel):
    """One candidate for a non-Arabic quote (English gate, docs/ENGLISH_GATE.md). Both texts are
    verbatim upstream strings: ``arabic_text`` is the corpus display field, ``translation_text`` the
    approved translation (QuranEnc / HadeethEnc). Nothing is generated."""

    kind: Literal["quran", "hadith"]
    ref: dict[str, Any]
    ref_label_ar: str
    ref_label_en: str
    arabic_text: str
    translation_text: str
    translation_source: str  # english_saheeh | english_rwwad | hadeethenc_en
    score: float
    source_url: str
    selected: bool = False  # chosen by the picker (rule or model); at most one per quote


class QuoteResult(BaseModel):
    id: str
    span: Span
    quoted_text: str
    kind: Kind
    language: Literal["ar", "en", "other"]
    source_modality: Literal["text", "image"]
    claimed_source: ClaimedSource | None = None
    claimed_source_mismatch: bool = False
    status: Status
    review_reason: ReviewReason | None = None
    score: float
    message_key: str
    notice_keys: list[str] = Field(default_factory=list)
    matches: list[Match] = Field(default_factory=list)
    total_positions: int = 0
    external_search_links: list[Link] = Field(default_factory=list)
    segments: list[SegmentModel] = Field(default_factory=list)
    repeated_spans: list[Span] = Field(default_factory=list)  # N-1: same quote again later in the text
    english_candidates: list[EnglishCandidate] = Field(default_factory=list)  # English gate (I7 quotes only)
    picker: Literal["", "rule", "model", "none"] = (
        ""  # how `selected` was decided ("" = not an English quote)
    )


class Flags(BaseModel):
    chain_message: bool = False
    refusal: bool = False
    pii_suspected: bool = False


class Timings(BaseModel):
    extract: int = 0
    retrieve: int = 0
    match: int = 0
    total: int = 0


class CheckResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [v["response"] for v in openapi_examples().values()]}
    )

    request_id: str
    disclaimer_key: str = "footer"
    transparency_key: str = "transparency_notice"
    corpus: dict[str, str]
    extraction_degraded: bool = False
    extraction_provider: str
    flags: Flags
    quotes: list[QuoteResult]
    validator_rejections: int = 0
    timings_ms: Timings
    # B10: never a silent cut. `quotes_detected` = spans found before the cap; `extraction_truncated` = true
    # when more than `max_quotes` were found and only the first ones were checked.
    quotes_detected: int = 0
    extraction_truncated: bool = False
    ocr_text: str | None = None
    ocr_truncated: bool = (
        False  # B10: the image text exceeded max_text_chars; only the first part was checked
    )
    # E-032: sha256(index records sha + normalized input + every quote verdict). Same input on the same
    # corpus build ⇒ same hash — a judge can re-run and compare. Excludes request_id/timings.
    determinism_hash: str = ""  # image path only: the text as read, so the user can verify it (ADR-003)


class ErrorBody(BaseModel):
    code: str
    message_ar: str
    message_en: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class SourceInfo(BaseModel):
    id: str
    name: str
    type: str
    url: str
    version: str
    license: str
    license_url: str
    purpose: str
    in_repo: bool
    records: int
    downloaded_at: str | None = None
    sha256: str = ""  # pinned upstream hash (developer gate; empty for multi-file sources like OHD)


# --------------------------------------------------------------------------- developer gate (docs/API.md)


class GuardRequest(BaseModel):
    """A chatbot answer to check before it reaches the user (docs/GUARD.md)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "answer": "قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «طلب العلم فريضة على كل مسلم ومسلمة»",
                    "ui_lang": "ar",
                }
            ]
        }
    )

    answer: str = Field(min_length=1, max_length=5000)
    ui_lang: Literal["ar", "en"] = "ar"


class GuardCounts(BaseModel):
    quotes: int
    found: int
    flagged: int
    by_status: dict[str, int]


class GuardResponse(BaseModel):
    verdict: Literal["clear", "flagged", "no_quotes"]
    counts: GuardCounts
    flagged_quote_ids: list[str]
    quotes: list[dict[str, Any]]  # compact quotes (same shape as the MCP verify_text tool)
    flags: dict[str, bool]
    extraction_degraded: bool
    summary_ar: str
    summary_en: str
    determinism_hash: str
    corpus: dict[str, str]


class ReceiptRequest(BaseModel):
    """Text to issue a stateless verification receipt for (docs/API.md §Receipt)."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"text": "قال تعالى: ﴿إن الله مع الصابرين﴾", "ui_lang": "ar"}]}
    )

    text: str = Field(min_length=1, max_length=5000)
    ui_lang: Literal["ar", "en"] = "ar"


class ReceiptSummary(BaseModel):
    quotes: int
    by_status: dict[str, int]


class ReceiptResponse(BaseModel):
    """The receipt is the input: `token` = base64url(zlib(json{v:1,t:text,l:ui_lang})). Nothing is stored."""

    receipt_id: str  # first 16 hex of determinism_hash
    determinism_hash: str
    corpus: dict[str, str]
    index_sha256: str
    build_sha: str
    issued_at: str  # UTC ISO-8601, second precision
    ui_lang: Literal["ar", "en"]
    summary: ReceiptSummary
    quotes: list[dict[str, Any]]  # compact quotes (same shape as the MCP verify_text tool)
    validator_rejections: int
    disclaimer: str
    token: str
    # GET /v/{token} only
    presented_hash: str | None = None
    verified_now: bool | None = None
    stale: bool | None = None


class RulesResponse(BaseModel):
    ui_lang: Literal["ar", "en"]
    text: str
    states: list[str]
    source: str
    safety_sha256: str


class HealthResponse(BaseModel):
    status: Literal["ok", "loading", "degraded"]
    build_sha: str
    corpus: dict[str, str]
    corpus_loaded: bool
    counts: dict[str, int]
    rss_mb: int
    providers: dict[str, str]
    index_sha256: str = ""  # sha256 of corpus/index/records.jsonl — pin for reproducibility
    boot: Literal["snapshot", "build", ""] = ""  # how the store was loaded (E-031)
    boot_seconds: float = 0.0
