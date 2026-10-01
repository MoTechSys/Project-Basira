# UX / accessibility log — بصيرة

Every entry is a measurement that was actually run, with the command, the environment and the result. No projected numbers.

## 2026-10-01 — first full E2E + axe sweep after brand kit v1.0 integration

**Environment**: sandbox, Chromium (Playwright 1.x bundled build) after `sudo apt-get install libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libgbm1 libasound2 libnss3 libxcomposite1 libxdamage1 libxrandr2 libpango-1.0-0 libcairo2`. Backend on :8000 with **real providers** (gpt-5.4 span proposals via the sandbox proxy), Vite dev server on :5173.

**Command**: `cd frontend && npx playwright test` (spec `e2e/check.spec.ts`), plus an ad-hoc sweep of three more contexts with the same axe tag set (`wcag2a wcag2aa wcag21aa wcag22aa`).

| Context | axe violations | interactive targets < 24 px | result |
|---|---|---|---|
| light · 1280×720 (spec) | **0** | **0** | ✓ 1 passed (12.9 s incl. a real check) |
| dark · 1280×900 | **0** | **0** | ✓ (28 rule groups passed) |
| light · 390×844 (mobile) | **0** | **0** | ✓ |
| dark · 390×844 (mobile) | **0** | **0** | ✓ |

What the spec asserts beyond axe: `<html dir="rtl" lang="ar">`; health gate («جاهز») before typing; the real check returns two `role="status"` badges — «يحتاج مراجعة» (Quran, typo «علي») then «وُجد» (Muslim); the user's typo is the only `mark.d-quote`; the source pane is byte-exact (`letter-spacing: normal`, `text-transform: none`); every `button, a` is ≥ 24 px (WCAG 2.2 SC 2.5.8); language switch flips `dir` to `ltr`.

### Defects found and fixed in this run

| # | Finding | Fix | Where |
|---|---|---|---|
| 1 | `expect(getByRole('status')).toHaveCount(2)` timed out at Playwright's default 5 s — the real check (LLM extraction, `PROVIDER_TIMEOUT` 8 s) legitimately takes longer. Not a UI bug. | Explicit `{ timeout: 45_000 }` on that one assertion (same budget as the health gate). | `frontend/e2e/check.spec.ts` |
| 2 | **Real WCAG 2.2 SC 2.5.8 failure**: the 8 inline licence/source links in the footer («CC BY 3.0», «tanzil.net», «ODbL 1.0», «hadeethenc.com» …) rendered 18 px tall. | `.source a { display:inline-block; min-block-size:24px; line-height:24px; padding-inline:2px }` — hit area grows, line layout unchanged. | `frontend/src/index.css` |

### Not yet measured (honest gaps)

* Lighthouse (performance / best-practices / SEO) — needs a production build served over HTTP; planned with WP-10.
* Screen-reader walkthrough (NVDA/VoiceOver) — axe cannot replace it; manual pass planned before the deck video.
* Keyboard-only flow is exercised implicitly (Ctrl+↵) but not asserted tab-by-tab in the spec.

### Screenshots (git-ignored, regenerated on each run)

`frontend/e2e/screenshot-ar.png` (spec), `screenshot-dark-desktop.png`, `screenshot-light-mobile.png`, `screenshot-dark-mobile.png`.
