"""Pydantic schemas for the public API.

ADR-0001: four-state model (found, partial_match, not_found, needs_review).
ADR-0003: LLM extracts only; never generates reference text.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class QuoteKind(str, Enum):
    """Type of citation extracted from user text."""

    QURAN = "quran"
    HADITH = "hadith"
    ISNAD = "isnad"
    CLAIMED_SOURCE = "claimed_source"


class Status(str, Enum):
    """Final verification status — the four-state model (I1-I9)."""

    FOUND = "found"
    PARTIAL_MATCH = "partial_match"
    NOT_FOUND = "not_found"
    NEEDS_REVIEW = "needs_review"


class CheckRequest(BaseModel):
    """Request body for POST /v1/check."""

    text: str = Field(..., min_length=1, max_length=50_000)
    lang: Literal["ar", "en"] = "ar"


class Match(BaseModel):
    """A verified match against the corpus."""

    source_id: str
    source_kind: Literal["quran", "hadith"]
    ref: str
    verbatim: str
    diff: list[dict] | None = None


class Quote(BaseModel):
    """One extracted citation with its verification result."""

    span: tuple[int, int]
    kind: QuoteKind
    status: Status
    match: Match | None = None
    reason: str | None = None


class CheckResponse(BaseModel):
    """Response body for POST /v1/check."""

    quotes: list[Quote]
    determinism_hash: str


class HealthResponse(BaseModel):
    """GET /health response."""

    status: Literal["ready", "loading"]
    boot_seconds: float | None = None
    corpus_sha: str | None = None
