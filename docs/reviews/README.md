# docs/reviews — cross-family review artefacts (raw agent output, triaged in STATE §2)

Each file is the verbatim output of one reviewer role from `scripts/agents/orchestrator.py`
(model named in the heading). Findings are **inputs**, not decisions: the engineer verifies each
against the code and records accepted fixes in DECISIONS/STATE. Reviews that failed with HTTP 524
are not stored.

| date | file | role · model | status |
|---|---|---|---|
| 2026-10-01 | `2026-10-01-security-main-gpt6-astra.md` | reviewer · gpt-6-astra (high) — `main.py`, providers | **open** — P1s: X-Forwarded-For trust, guards after body parsing, limiter key bound, `log.exception` traceback; P2s: HTTPException envelope, MIME sniffing |
| 2026-10-01 | `2026-10-01-safety-messages-opus55.md` | safety · claude-opus-5-5 (16k) — messages + pipeline notices | **open** — #1 `grade_line` only when status is `found` for THAT record + wording «حكم الموسوعة على الحديث رقم N، لا على نصك»; #2 `hadeethenc_link_only` wording on partial; others see file |
