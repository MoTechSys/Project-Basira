# Basira (بصيرة) — Citation Verification for Islamic Content

> Submission to **IslamicAIch 2026 — Track 4 (Knowledge & Verification Tools)**
> Team: MoTechSys + 5 AI agents (backend, frontend, corpus, qa, devops)

## What it does
Given free-form Arabic (or English) text, Basira extracts quoted Qur'anic and
Hadith spans and classifies each one into one of **4 states**:

| State | Meaning |
|-------|---------|
| `FOUND` | Exact match found in an authenticated source |
| `PARTIAL_MATCH` | Close match with reported diff |
| `NOT_FOUND` | No match in the authenticated corpus |
| `NEEDS_REVIEW` | Signal below confidence floor — defer to human |

Each result carries the source id, hash of the matched span, and a canonical
link to quran.com / sunnah.com.

## Non-goals
- No fatwā. No shariah ruling. No hadith grading.
- No text generation of religious content.
- No training on Islamic text.

## Sources
Tanzil (Uthmani + Simple Clean), Open-Hadith-Data, HadeethEnc — pinned by
SHA-256 in `corpus/manifest.json`.

## Architecture
```
User → React 19 (RTL) → FastAPI → [Extract → Retrieve → Match → Decide → Verify]
                                       ↓
                              Tanzil / OHD / HadeethEnc (hash-verified)
```

## Running
```bash
./scripts/bootstrap.sh
./scripts/serve.sh
# API: http://localhost:8080
```

## Evaluation
`eval/REPORT.md` — Macro-F1 **0.89**, zero false `FOUND`.
