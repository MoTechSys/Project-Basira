# ADR-005 — Provider abstraction & offline-first development

**Status:** Accepted · 2026-09-30

## Decision
- `backend/app/providers/base.py`: `LLMClient.extract(text) -> ExtractionResult`, `VisionClient.ocr(image) -> OcrResult`.
- `MockLLM` (default): deterministic, wraps `rules.py` + a small heuristic; `MockVision`: returns a fixture text.
- Real adapters (OpenAI-compatible, Anthropic, Gemini) live in `providers/` but are inert without env keys; selected via `LLM_PRIMARY`, `LLM_FALLBACK`, `VISION_PRIMARY`.
- Structured output enforced by JSON schema; server re-locates `quoted_text` in input and ignores model offsets on mismatch.
- Failure chain: primary → fallback → rules-only with `extraction_degraded=true` (HTTP 200).
