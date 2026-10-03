"""Provider contracts (ADR-005): an LLM may only *propose* quote spans; it never decides.

Design rules (SAFETY §2, ADR-005):

* ``LLMClient.extract`` returns candidate quotes as *text* + a *kind guess*. The pipeline
  re-locates every ``quoted_text`` inside the user input (``relocate``) and **ignores model
  offsets**. A proposal whose text cannot be found verbatim in the input is dropped.
* Providers never see the corpus and never produce religious text that reaches the user;
  their output is used only to delimit which part of the *user's own text* to check.
* ``VisionClient.ocr`` returns extracted text; the pipeline treats it exactly like typed text
  but adds the ``image_extracted`` notice (``needs_review_image`` family).
* Every provider has a ``name`` (reported in ``/health`` and ``extraction_provider``) and may
  raise ``ProviderError``; the pipeline catches it and falls back to rules-only with
  ``extraction_degraded=true`` (HTTP 200, never 5xx).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Literal

ProposedKind = Literal["quran", "hadith_matn", "isnad", "attributed_saying", "unknown"]


class ProviderError(RuntimeError):
    """Any provider failure (network, schema, timeout). Pipeline downgrades, never crashes."""


@dataclass(frozen=True, slots=True)
class ProposedQuote:
    """A span *proposal*. ``start``/``end`` are hints only; the server re-locates ``quoted_text``."""

    quoted_text: str
    kind: ProposedKind = "unknown"
    start: int = -1
    end: int = -1
    claimed_source_raw: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    provider: str
    quotes: tuple[ProposedQuote, ...] = ()
    degraded: bool = False  # True when a fallback was used inside the provider chain
    latency_ms: int = 0


@dataclass(frozen=True, slots=True)
class OcrResult:
    provider: str
    text: str
    confidence: float | None = None  # None = provider does not report it
    latency_ms: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)


class LLMClient(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    async def extract(self, text: str) -> ExtractionResult:
        """Propose quote spans in ``text``. Must not raise anything but ``ProviderError``."""


class VisionClient(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    async def ocr(self, image: bytes, *, mime: str) -> OcrResult:
        """Extract text from an image. Must not raise anything but ``ProviderError``."""


# --------------------------------------------------------------------------- relocation


def relocate(text: str, proposal: ProposedQuote) -> tuple[int, int] | None:
    """Find ``proposal.quoted_text`` verbatim in ``text``; model offsets are only a tie-breaker.

    Returns ``(start, end)`` code-point offsets or ``None`` when the proposal is not a verbatim
    substring (then it is dropped — ADR-005 «ignores model offsets on mismatch»).
    """
    needle = proposal.quoted_text.strip()
    if not needle:
        return None
    hint = proposal.start if 0 <= proposal.start <= len(text) else 0
    # prefer the occurrence closest to the hint, then the first one
    best: tuple[int, int] | None = None
    i = text.find(needle)
    while i >= 0:
        cand = (i, i + len(needle))
        if best is None or abs(cand[0] - hint) < abs(best[0] - hint):
            best = cand
        i = text.find(needle, i + 1)
    return best
