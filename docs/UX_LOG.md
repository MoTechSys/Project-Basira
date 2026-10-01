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

## 2026-10-01 — Lighthouse on the production bundle + pixel audit

**Setup**: `npm run build` → `vite preview` on :4173 (same proxy as dev; added to `vite.config.ts`), Lighthouse 13.5 with Playwright's Chromium (`CHROME_PATH=…/ms-playwright/chromium-1243/chrome-linux64/chrome`), backend real providers.

| Run | Perf | A11y | Best-practices | SEO | FCP | LCP | TBT | CLS |
|---|---|---|---|---|---|---|---|---|
| mobile, before fixes | 98 | 100 | 100 | 91 | 1.5 s | 2.1 s | 80 ms | 0.002 |
| **mobile, after** | **99** | **100** | **100** | **100** | 1.5 s | 2.1 s | 50 ms | 0.002 |
| **desktop, after** | **100** | **100** | **100** | **100** | 0.4 s | 0.5 s | 10 ms | 0 |

Fixed (E-037): `label-content-name-mismatch` on the brand link; invalid `robots.txt` (SPA fallback). Remaining informational items, deliberately not "fixed": `unused-javascript` 37 KiB (React 19 runtime — the whole bundle is 85 kB gz; code-splitting a one-screen app would add requests), `render-blocking` 4.7 kB CSS (inlining it would defeat caching).

**Pixel audit** (2× screenshots, 320–1440 px, light/dark, home/result): one defect — topbar overflow at 360 px (E-036), fixed and re-swept: `scrollWidth == clientWidth` at all 7 widths. Result card verified: Mushaf pane in Amiri Quran, user typo «علي» marked, source words «على» marked, byte-exact pane, referral links visible.

**Speed** (E-035): `/v1/check` wall 8.0 s → **1.96 s** on the smoke text; 16 concurrent short checks p50 2.1 s / p95 2.3 s; 8 concurrent 1 500-char texts p95 8.3 s (LLM-bound; `match` ≤ 6 ms). Long texts remain the open latency item — see INTEGRATIONS §5.
