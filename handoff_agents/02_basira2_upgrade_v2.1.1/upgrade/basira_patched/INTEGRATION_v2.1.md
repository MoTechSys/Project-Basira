# Basira upgrade v2.1 — integration guide for the dev agent

This tree (`upgrade/basira_patched/`) is a **complete patched copy** of the Basira repo at `c62db17`
plus every v2/v2.1 change. Upstream `main` has moved since (implicit-quote detector, GS2/G2 index,
dark mode, brand application, Lighthouse work). Do **not** overwrite upstream files blindly — port
file-by-file using the table below. Everything here passes: `pytest` 133, `ruff`, `mypy` strict,
`eval` 150/150 + FA 0/500 on the full index, `vitest` 23, `tsc -b` strict, bundle 85.05 kB gz.

## 0. What changed vs v2 (the pack the other agent ported as "Pack A")

| Critique received | Fix in v2.1 | Where |
|---|---|---|
| CSP `script-src 'self'` broke inline dark-mode + JSON-LD | Per-request **nonce** stamped on inline `<script>` tags; header `script-src 'self' 'nonce-…'`; no `unsafe-inline` | `backend/app/csp.py`, `main.py` (`security_headers`, `spa`), tests in `test_api.py` |
| Dockerfile assumed `brand/dist` exists | `COPY brand/dis[t]/` — glob makes a missing dir a no-op | `Dockerfile` |
| `scan.py` duplicated upstream's detector | **Removed** (module, config toggles, notice key, tests, 2 eval cases rewritten) | `pipeline.py`, `config.py`, `messages/*.json`, `test_scholar_lens.py`, `eval/scholar_lens_cases.yaml` |
| I10/I11 collided with upstream numbering | Renumbered **I12/I13** everywhere; I10–I11 marked reserved | `state.py`, `rules.py`, `SAFETY.md`, `AI_USAGE.md`, `CHANGELOG.md` |
| "UI was prompts, not code" | **Real components + tests** (see §2) | `frontend/src/**` |
| Patch base drift | No more mega-diff. Port by file; each file below is self-contained | this guide |

## 0b. NEW in v2.1.1 — E-037 harakat layer (the "ضمة بدل فتحة" problem)

| File | Action |
|---|---|
| `corpus/manifest.json` | new pinned source `tanzil_simple` (Tanzil Simple, vocalized; sha256 `f3268cfe…`) |
| `corpus/build_index.py` | `build_tanzil(..., src_voc)` writes `tv` per ayah after asserting token alignment with simple-clean |
| `backend/app/store.py` | `Record.text_vocalized` from `tv` (optional → old indexes still load) |
| `backend/app/match/harakat.py` | **new** — skeleton/compare_token/compare_quote (pure, 0 deps) |
| `backend/app/schemas.py` | `HarakatConflict`; `Match.harakat_verdict/_conflicts/_reference/_reference_range` |
| `backend/app/pipeline.py` | `_harakat()` called from `_match_for`; notices `harakat_conflict` / `harakat_consistent` |
| `messages/{ar,en}.json` | the two keys (`{n}` var) |
| `backend/tests/test_harakat.py` | 23 tests incl. pipeline on fixture (2:124) |
| `frontend/src/components/HarakatView.tsx` | **new** — two verbatim lines, exact letter marked on both |
| `frontend/src/components/QuoteCard.tsx` | renders `HarakatView`; `noticeVars` fills `{n}`; `harakat_conflict` pinned (never folded) |
| `frontend/src/__fixtures__/check_response_harakat.json` | **real** server response for 35:28 used by the test |

Run after porting: `make fetch` (downloads tanzil-simple.txt — tanzil.net had an expired TLS cert on 2026-10-01; `fetch.py` already documents the `-k` fallback), `make index`, then the whole-Quran zero-false-alarm check in `docs/evidence/harakat_fa_check.py`.

## 1. Backend — port these files (in order)

| File | Action | Depends on |
|---|---|---|
| `backend/app/csp.py` | **new** — copy as is | — |
| `backend/app/main.py` | merge 3 hunks: `import secrets` + `from app.csp import stamp_nonce`; `_csp(nonce)` + nonce in middleware; `spa()` returns `HTMLResponse(stamp_nonce(index_html, nonce))` | upstream's own `main.py` |
| `backend/app/schemas.py` | add `CheckOptions.stage: Literal["rules","full"]="full"`; `CheckResponse.extraction_stage` | — |
| `backend/app/pipeline.py` | add `_extract(text, stage)` method; `check()` calls it; `extraction_stage=stage` in response | upstream's extractor: call **your** implicit detector inside `_extract` only when `stage == "full"` |
| `backend/app/state.py`, `extract/rules.py` | I12/I13 logic (already ported in Pack A as I12/I13 — just verify names) | — |
| `backend/app/snapshot.py` | already ported; make sure it serialises **your** GS2/G2 arrays too (add them to `_ARRAYS`) | — |
| `backend/tests/test_api.py` | append the two CSP tests (`test_stamp_nonce_only_inline_scripts`, `test_spa_index_served_with_matching_nonce`) | `test_settings` fixture with `static_dir` |
| `backend/tests/test_scholar_lens.py` | append the two `options.stage` tests; drop any `quran_scan*` tests you ported | — |
| `eval/scholar_lens_cases.yaml` | N-009/N-010 now use explicit markers (no scanner) | — |

Smoke after porting:
```bash
cd backend && pytest -q && ruff check app tests && mypy app
curl -s localhost:8000/ -D - -o /dev/null | grep -i content-security-policy   # must contain 'nonce-'
curl -s localhost:8000/ | grep -c 'nonce="'                                  # == number of inline <script>
curl -s -XPOST localhost:8000/v1/check -H 'content-type: application/json' \
  -d '{"text":"قال تعالى: ﴿قل هو الله أحد﴾","options":{"stage":"rules"}}' | jq .extraction_stage,.timings_ms.extract
```

## 2. Frontend — new files (copy) and modified files (merge)

**Copy as is** (no upstream equivalents):

| File | Purpose | Tests |
|---|---|---|
| `src/components/AnnotatedText.tsx` | user's text with inline `<a class="hl" data-status>` per quote; verbatim `slice()`; `segment()` + `baseDirection()` exported | `ux_v21.test.tsx › AnnotatedText` (3) |
| `src/components/AyahText.tsx` | long source: full text always in DOM; visual clamp or window with **word-counter buttons**, never a bare "…" | `› AyahText` (3) |
| `src/components/ProgressiveStatus.tsx` | 3-step strip + preliminary/final/degraded/failed note | via Check tests |
| `src/useProgressiveCheck.ts` | two parallel requests; final **replaces** preliminary; failure matrix; `ruleSpans`/`changed` for tags | `› Check — progressive flow` (4) |
| `src/share.ts` | `#t=` deflate-raw+base64url link, 0 kB (native `CompressionStream`), `decodeShare` never throws, `fitsQr` | `› share link` (3) |
| `src/print.css` | print-only report (A4, open `<details>`, fixed disclaimer footer, underline styles per status) | manual: `window.print()` |
| `src/ux_v21.test.tsx` | 15 tests | — |

**Merge into upstream's versions:**

| File | Hunks |
|---|---|
| `src/api.ts` | `Stage` type; `check(text, lang, signal, stage="full")` sends `options.stage`; `extraction_stage?`, `determinism_hash?` on `CheckResponse` |
| `src/i18n.ts` | the `// --- v2.1 UX` block (≈45 keys) in **both** `ar` and `en` (the key-parity test enforces it) |
| `src/components/DiffView.tsx` | `export function ranges(...)` (was private) |
| `src/components/QuoteCard.tsx` | new props `compact`, `updated`, `addedByLlm`, `onFocusChange`; `id={q.id} tabIndex={-1}` on the section (hash target); `<details class="fold">` for notices / extra positions / extra links in compact mode; `ALWAYS_VISIBLE` safety notices never folded; `AyahText` in compact mode; `×N` repeat tag |
| `src/Check.tsx` | this is the integration point — see §3 |
| `src/index.css` | the three appended blocks (`v2.1 UX`, `progressive`, `compact card`) — keep **your** tokens/dark-mode variables; the new rules only reference existing `--found*`, `--partial*`, `--review*`, `--notfound*`, `--line`, `--card`, `--paper`, `--violet`, `--teal`, `--focus` |
| `src/main.tsx` | `import "./print.css";` |
| `src/Check.test.tsx` | `getAllByText(ar.fixed.footer)` (footer now also exists in the print block) |

## 3. `Check.tsx` wiring (what the component tree looks like)

```
<main class={showAnnotated ? "results-grid" : ""}>
  <div>                                   ← column 1
    <form class="card input-card">
      {showAnnotated
        ? <AnnotatedText text={checkedText} quotes={result.quotes} activeId onActivate/>
          + .annotated-bar ("edit text" button + legend)
        : <textarea id="text" …/>}
      .input-row (chars · upload · clear · check[disabled unless editing])
    </form>
    {error && <div role="alert">}
    <ProgressiveStatus phase totalMs hash onRetry/>
    <div class="sr-only" aria-live="polite"/>   ← exactly two announcements: preliminary, final
  </div>
  <div id="results" class="results results-col" tabIndex=-1>   ← column 2 (sticky ≥960px)
    .summary (count · ms · [copy report | share link | save PDF] — all disabled until isFinal)
    flags banner · ocr block · no-quotes banner
    {quotes.map(q => <QuoteCard compact={!matchMedia(min-width:960px)} updated addedByLlm onFocusChange/>)}
    <a href="#annotated" class="back-to-text">  (mobile only)
  </div>
</main>
<p class="print-footer">{fixed.footer}</p>      ← repeats on every printed page
```

Rules enforced in code (and tested):
- Editing invalidates results: "edit text" drops the result and returns the textarea (no stale highlights).
- Final **replaces** preliminary wholesale; `changed` ids get an "updated" tag; spans absent from the rules pass get "added by implicit analysis".
- Share link opens with a banner and **never auto-checks**; hash is stripped from history after intake.
- Report/share/PDF buttons are disabled while `!isFinal`.
- Image checks stay single-shot (OCR is the slow part); they reset the progressive state.

## 4. Things upstream must still do (not in this tree because they need your live assets)

1. **Home page live demo** (spec §4): render one of your four real examples from a recorded fixture, CSS-only animation, `aria-hidden`, LCP = text. Target ≤ 2.5 s mobile.
2. **Lighthouse/axe re-run** after merge on 3 states × 2 langs × 320/1440. Budget: initial JS ≤ 90 kB gz (we're at 85.05 with everything).
3. **QR** (optional, lazy chunk ≤ 8 kB): `import("./qr")` on click; `fitsQr(url)` already gates it.
4. **Dark-mode tokens** for the four `--hl-*` backgrounds: keep ≥ 4.5:1 against your dark `--ink`.
5. Deploy `print.css` check: Playwright `page.pdf()` → `pdftotext` → assert an ayah string is byte-identical.
