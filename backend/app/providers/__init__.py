"""Provider factory (ADR-005). Selection by env only; defaults are offline mocks (D-004).

Env (all optional, see ``.env.example``)::

    LLM_PROVIDER     = mock | openai-compatible
    LLM_BASE_URL     = https://api.openai.com/v1   (any OpenAI-compatible endpoint)
    LLM_API_KEY      = …                            (absent → factory falls back to mock, logged)
    LLM_MODEL        = gpt-4o-mini
    LLM_REASONING_EFFORT = (unset) | none | minimal | low | …   (passed through verbatim; see openai_compat)
    VISION_PROVIDER  = mock | openai-compatible
    VISION_BASE_URL / VISION_API_KEY / VISION_MODEL  (default to the LLM_* values)
"""

from __future__ import annotations

import logging
import os

from app.providers.base import (
    ExtractionResult,
    LLMClient,
    OcrResult,
    ProposedQuote,
    ProviderError,
    VisionClient,
    relocate,
)
from app.providers.mock import MockLLM, MockVision

log = logging.getLogger(__name__)

__all__ = [
    "ExtractionResult",
    "LLMClient",
    "MockLLM",
    "MockVision",
    "OcrResult",
    "ProposedQuote",
    "ProviderError",
    "VisionClient",
    "make_llm",
    "make_vision",
    "relocate",
]


def make_llm(provider: str | None = None) -> LLMClient:
    name = (provider or os.environ.get("LLM_PROVIDER", "mock")).strip().lower()
    if name == "mock":
        return MockLLM()
    if name == "openai-compatible":
        key = os.environ.get("LLM_API_KEY", "")
        if not key:
            log.warning("LLM_PROVIDER=openai-compatible but LLM_API_KEY is empty → using mock")
            return MockLLM()
        from app.providers.openai_compat import OpenAICompatLLM  # noqa: PLC0415  (httpx only when needed)

        return OpenAICompatLLM(
            base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=key,
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            reasoning_effort=os.environ.get("LLM_REASONING_EFFORT") or None,
        )
    log.warning("unknown LLM_PROVIDER=%r → using mock", name)
    return MockLLM()


def make_vision(provider: str | None = None) -> VisionClient:
    name = (provider or os.environ.get("VISION_PROVIDER", "mock")).strip().lower()
    if name == "mock":
        return MockVision()
    if name == "openai-compatible":
        key = os.environ.get("VISION_API_KEY") or os.environ.get("LLM_API_KEY", "")
        if not key:
            log.warning("VISION_PROVIDER=openai-compatible but no API key → using mock")
            return MockVision()
        from app.providers.openai_compat import OpenAICompatVision  # noqa: PLC0415

        return OpenAICompatVision(
            base_url=os.environ.get("VISION_BASE_URL")
            or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=key,
            model=os.environ.get("VISION_MODEL") or os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        )
    log.warning("unknown VISION_PROVIDER=%r → using mock", name)
    return MockVision()
