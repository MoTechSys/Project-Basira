"""Pydantic models for the public API (BUILD_SPEC §4 + audit §5 additions)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal["found", "partial_match", "needs_review", "not_found"]
Kind = Literal["quran", "hadith_matn", "isnad", "attributed_saying", "unknown"]
ReviewReason = Literal[
    "near_miss",
    "orthographic_difference",
    "short_quote",
    "stage_failure",
    "validator_reject",
    "non_arabic",
    "image_unconfirmed",
    "diacritic_difference",
]
CorpusName = Literal["tanzil", "ohd", "hadeethenc"]


class CheckOptions(BaseModel):
    max_candidates: int = Field(default=3, ge=1, le=5)
    # E-044 two-phase check. "rules": deterministic extraction only (explicit markers, model tags,
    # corpus anchors) — never calls the language model, answers in milliseconds. "full" (default):
    # the same plus the model's span proposals. Matching/decision code is identical in both stages,
    # so a quote found by both gets the same status; "full" can only ADD quotes (tested).
    stage: Literal["rules", "full"] = "full"


class CheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    ui_lang: Literal["ar", "en"] = "ar"
    source_modality: Literal["text", "image"] = "text"
    options: CheckOptions = Field(default_factory=CheckOptions)


class Span(BaseModel):
    start: int
    end: int


class DiffOpModel(BaseModel):
    op: Literal["equal", "replace", "insert", "delete"]
    quote_range: list[int]
    source_range: list[int]
    quote_chars: list[int]
    source_chars: list[int]
    # letter-level sub-ranges inside this op (char-by-char highlighting; diacritic conflicts)
    quote_letters: list[list[int]] = Field(default_factory=list)
    source_letters: list[list[int]] = Field(default_factory=list)


class Grade(BaseModel):
    text: str
    takhrij: str
    source: Literal["HadeethEnc"] = "HadeethEnc"
    version: str
    url: str


class Link(BaseModel):
    name: str
    url: str


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


class SegmentModel(BaseModel):
    """One typed part of a citation (IslamicEval 2026 schema): char offsets into the request text."""

    type: Literal["Ayah", "matn", "isnad", "claimed_source"]
    start: int
    end: int


class ClaimedSource(BaseModel):
    raw: str
    parsed: dict[str, Any]


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
    # E-044: which extraction stage produced these spans (two-phase UI; the final "full" response
    # replaces the preliminary "rules" one wholesale on the client).
    extraction_stage: Literal["rules", "full"] = "full"
    ocr_text: str | None = None  # image path only: the text as read, so the user can verify it (ADR-003)
    # E-032: sha256(index records sha + normalized input + every quote verdict). Same input on the same
    # corpus build ⇒ same hash — a judge can re-run and compare. Excludes request_id/timings.
    determinism_hash: str = ""


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
