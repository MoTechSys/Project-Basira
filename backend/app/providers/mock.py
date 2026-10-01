"""Offline, deterministic providers (default in dev/test/CI — D-004, ADR-005).

``MockLLM`` wraps the rules extractor plus one conservative heuristic: a *sentence* that
contains a strong Quran/hadith lexical marker («ﷺ», «تعالى», «رواه», «أخرجه») and ≥ 4 Arabic
tokens is proposed as an ``unknown`` span even without brackets/introducers. The pipeline
still verifies every proposal against the corpus, so a wrong proposal can only cost a
``not_found`` card, never a wrong ``found``.

``MockVision`` returns a fixture text (or raises when ``BASIRA_MOCK_OCR_FAIL=1``) so the
image path and its degradation branch can be exercised in tests without any API key.
"""

from __future__ import annotations

import os
import re
import time

from app.extract.rules import extract_spans
from app.normalize import loose_tokens
from app.providers.base import (
    ExtractionResult,
    LLMClient,
    OcrResult,
    ProposedQuote,
    ProviderError,
    VisionClient,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟\n؛])\s+|\n+")
_MARKERS = ("ﷺ", "تعالى", "رواه", "أخرجه", "صلى الله عليه وسلم", "عز وجل", "سبحانه")
_MIN_HEURISTIC_TOKENS = 4

MOCK_OCR_FIXTURE = "قال تعالى: ﴿إِنَّ اللَّهَ مَعَ الصَّابِرِينَ﴾"


class MockLLM(LLMClient):
    name = "mock"

    async def extract(self, text: str) -> ExtractionResult:
        t0 = time.perf_counter()
        quotes: list[ProposedQuote] = []
        for sp in extract_spans(text):
            quotes.append(
                ProposedQuote(
                    quoted_text=text[sp.start : sp.end],
                    kind=sp.kind,  # type: ignore[arg-type]
                    start=sp.start,
                    end=sp.end,
                    claimed_source_raw=(sp.claimed_source or {}).get("raw"),
                )
            )
        covered = [(q.start, q.end) for q in quotes]
        pos = 0
        for sent in _SENTENCE_SPLIT.split(text):
            if not sent:
                continue
            s = text.find(sent, pos)
            if s < 0:
                continue
            pos = s + len(sent)
            e = pos
            if any(a < e and s < b for a, b in covered):
                continue
            if any(m in sent for m in _MARKERS) and len(loose_tokens(sent)) >= _MIN_HEURISTIC_TOKENS:
                rel_start = _after_last_marker(sent)
                body = sent[rel_start:]
                lead = len(body) - len(body.lstrip(" :،,-–\t"))
                body = body.strip(" :،,-–\t.")
                bs = s + rel_start + lead
                if (
                    body
                    and text[bs : bs + len(body)] == body
                    and len(loose_tokens(body)) >= _MIN_HEURISTIC_TOKENS
                ):
                    quotes.append(ProposedQuote(body, "unknown", bs, bs + len(body)))
        return ExtractionResult(self.name, tuple(quotes), False, int((time.perf_counter() - t0) * 1000))


def _after_last_marker(sent: str) -> int:
    """Offset just after the last marker in the first half of the sentence (the matn follows it);
    0 when the marker sits late (then the whole sentence is proposed verbatim)."""
    best = 0
    for m in _MARKERS:
        i = sent.rfind(m)
        if i >= 0 and i + len(m) <= len(sent) // 2 + 1:
            best = max(best, i + len(m))
    return best


class MockVision(VisionClient):
    name = "mock"

    async def ocr(self, image: bytes, *, mime: str) -> OcrResult:
        if os.environ.get("BASIRA_MOCK_OCR_FAIL") == "1":
            raise ProviderError("mock vision configured to fail")
        if not image:
            raise ProviderError("empty image")
        if not mime.startswith("image/"):
            raise ProviderError(f"unsupported mime {mime!r}")
        return OcrResult(self.name, MOCK_OCR_FIXTURE, confidence=None, latency_ms=0, warnings=("fixture",))
