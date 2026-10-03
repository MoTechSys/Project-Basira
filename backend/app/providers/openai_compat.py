"""OpenAI-compatible chat-completions adapter (inert without ``LLM_API_KEY`` — D-004, ADR-005).

The model is asked for a strict JSON object ``{"quotes":[{"text":..., "kind":...}]}``.
Nothing the model says is shown to the user; its only effect is *which substrings of the
user's own input* get checked. Offsets are not requested — the server re-locates text.

Vision OCR uses the same endpoint with an image part. Both calls have a hard timeout and
map every failure to ``ProviderError`` so the pipeline degrades to rules-only.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import httpx

from app.english_gate import EnglishPicker
from app.providers.base import (
    ExtractionResult,
    LLMClient,
    OcrResult,
    ProposedKind,
    ProposedQuote,
    ProviderError,
    VisionClient,
)
from app.schemas import EnglishCandidate

_KINDS: frozenset[str] = frozenset({"quran", "hadith_matn", "isnad", "attributed_saying", "unknown"})

EXTRACT_SYSTEM = (
    "You are a span locator. Given Arabic/English text, list every passage that is PRESENTED as a "
    'quotation of the Quran or of a hadith (inside brackets ﴿﴾ «» "" or after phrases like قال تعالى / '
    "قال رسول الله / رواه). Copy each passage EXACTLY as it appears (character-for-character). Never "
    "correct, complete, translate or judge it. Never add passages that are not in the text. "
    'Reply with JSON only: {"quotes":[{"text":"<verbatim>","kind":"quran|hadith_matn|isnad|attributed_saying|unknown"}]}'
)
OCR_SYSTEM = (
    "Transcribe ALL text visible in the image exactly as written, preserving Arabic diacritics and line "
    "breaks. Do not translate, correct, summarise or add anything. Reply with the raw text only."
)


class OpenAICompatLLM(LLMClient):
    """``reasoning_effort`` matters for latency, not quality, in this task: span location is
    copy-work, and reasoning models spend 5–15 s "thinking" before emitting ~50 tokens of JSON
    (measured 2026-10-01 on the proxy: gpt-5.4 default 8.7–14.9 s, ``low`` 4.5–6.9 s,
    ``none`` 2.0–2.8 s with identical spans). The value is passed through verbatim only when
    set, because the allowed vocabulary differs per model (gpt-5.4: none/low/…; gpt-5-mini:
    minimal/low/…). An unsupported value → HTTP 400 → ``ProviderError`` → rules-only, visibly.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 20.0,
        reasoning_effort: str | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("LLM_API_KEY missing")
        self.name = f"openai-compatible:{model}"
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._model = model
        self._timeout = timeout_s
        self._reasoning_effort = (reasoning_effort or "").strip() or None

    def request_body(self, text: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": EXTRACT_SYSTEM},
                {"role": "user", "content": text},
            ],
        }
        if self._reasoning_effort is not None:
            body["reasoning_effort"] = self._reasoning_effort
        return body

    async def extract(self, text: str) -> ExtractionResult:
        t0 = time.perf_counter()
        body = self.request_body(text)
        content = await _post(self._url, self._headers, body, self._timeout)
        quotes = _parse_quotes(content)
        return ExtractionResult(self.name, quotes, False, int((time.perf_counter() - t0) * 1000))


class OpenAICompatVision(VisionClient):
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_s: float = 40.0) -> None:
        if not api_key:
            raise ProviderError("VISION_API_KEY missing")
        self.name = f"openai-compatible:{model}"
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._model = model
        self._timeout = timeout_s

    async def ocr(self, image: bytes, *, mime: str) -> OcrResult:
        if not image:
            raise ProviderError("empty image")
        t0 = time.perf_counter()
        data_url = f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"
        body: dict[str, Any] = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": OCR_SYSTEM},
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": data_url}}],
                },
            ],
        }
        content = await _post(self._url, self._headers, body, self._timeout)
        return OcrResult(self.name, content.strip(), None, int((time.perf_counter() - t0) * 1000))


async def _post(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:  # network / timeout
        raise ProviderError(f"transport: {exc.__class__.__name__}") from exc
    if r.status_code != 200:
        raise ProviderError(f"http {r.status_code}")
    try:
        content = r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderError("malformed completion") from exc
    if not isinstance(content, str):
        raise ProviderError("non-string content")
    return content


def _parse_quotes(content: str) -> tuple[ProposedQuote, ...]:
    try:
        obj = json.loads(content)
    except ValueError as exc:
        raise ProviderError("non-JSON extraction") from exc
    items = obj.get("quotes") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        raise ProviderError("schema: quotes[] missing")
    out: list[ProposedQuote] = []
    for it in items[:60]:
        if not isinstance(it, dict):
            continue
        txt = it.get("text")
        if not isinstance(txt, str) or not txt.strip():
            continue
        kind_raw = it.get("kind", "unknown")
        kind: ProposedKind = kind_raw if kind_raw in _KINDS else "unknown"
        out.append(ProposedQuote(txt, kind))
    return tuple(out)


# --------------------------------------------------------------------------- English picker (E-048)

PICK_SYSTEM = (
    "You are a strict matcher. The user gives an English quotation and a numbered list of approved "
    "translations (Quran ayat or hadith). Decide whether a listed translation is the SAME PASSAGE as the "
    "quotation (same meaning, allowing a different translator's wording). If yes, answer with its number; "
    "when several candidates are the same passage (duplicate entries, or adjacent ayat with the same "
    "wording), answer the LOWEST number among them. If no candidate is the same passage, or you are not "
    'sure, answer 0. Never explain, never quote, never add text. Reply with JSON only: {"pick": <integer>}'
)


class OpenAICompatPicker(EnglishPicker):
    """Model-backed chooser for the English gate: constrained to an index into the candidate list.

    The model never sees the Arabic corpus, never produces text that reaches the user; its only effect
    is which *approved* translation (if any) is marked ``selected``. Any failure → ``None`` (refuse).
    """

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_s: float = 12.0) -> None:
        if not api_key:
            raise ProviderError("LLM_API_KEY missing")
        self.name = f"openai-compatible:{model}"
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._model = model
        self._timeout = timeout_s

    @staticmethod
    def prompt(quote: str, translations: list[str]) -> str:
        lines = [f"QUOTATION: {quote}", "", "CANDIDATES:"]
        for i, t in enumerate(translations, 1):
            lines.append(f"{i}. {t}")
        return "\n".join(lines)

    async def pick(self, quote: str, candidates: list[EnglishCandidate]) -> int | None:
        if not candidates:
            return None
        texts = [c.translation_text for c in candidates]
        body: dict[str, Any] = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": PICK_SYSTEM},
                {"role": "user", "content": self.prompt(quote, texts)},
            ],
        }
        content = await _post(self._url, self._headers, body, self._timeout)
        return parse_pick(content, len(candidates))


def parse_pick(content: str, n: int) -> int | None:
    """``{"pick": k}`` with 1 ≤ k ≤ n → k-1; anything else (0, out of range, garbage) → None."""
    try:
        obj = json.loads(content)
    except ValueError:
        return None
    k = obj.get("pick") if isinstance(obj, dict) else None
    if isinstance(k, bool) or not isinstance(k, int):
        return None
    return k - 1 if 1 <= k <= n else None
