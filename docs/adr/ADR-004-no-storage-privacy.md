# ADR-004 — No storage, privacy, reporting

**Status:** Accepted · 2026-09-30

## Decision
- No DB, no accounts, no persistence of user text/images. Requests processed in memory; images re-encoded via Pillow (metadata stripped, downscaled, magic-byte validated) and discarded.
- Logs: `request_id, ts, duration, n_quotes, states, stage errors, provider name`. Never text, never reversible hashes of user text. Body logging disabled. IP logging to be disabled at edge/host and stated in SAFETY.md.
- Report button → pre-filled **GitHub Issue** (client-side URL); no server store.
- Client-side PII blocker (email / phone / @handle / 10-digit ID) before send, with a fixed message.
- `privacy_notice` includes the transparency sentence (AI-assisted tool, not a scholar/fatwa body) and states that text is sent to a named model provider.
- Demo cache: only for the fixed synthetic demo inputs, keyed by case id.
