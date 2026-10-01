# Brand Kit v1.0 — audit and integration record

**Input:** `basira_brand_kit_v1.0.zip` (1.03 MB, 96 files, produced by a second agent; owner request 2026-10-01).
**Method:** every claim in the kit's README was re-verified here with tooling, not trusted. Checksums,
SVG well-formedness, font coverage (fontTools), WCAG contrast (computed), official-template conformance
(pptx XML inspection), TypeScript strictness (`tsc -b` under our config). Then integrated with the
corrections listed in §3. Live screenshots: light / dark / mobile, home + result.

## 1. What was verified and accepted

| Claim | Verified how | Result |
|---|---|---|
| 96 files, `CHECKSUMS.sha256` | `sha256sum -c` | **96/96 OK** |
| All SVG valid, `viewBox` kept, no fixed width/height | `xml.etree` parse of 89 SVGs | all parse; logos have `<title>`+`<desc>`; icons intentionally have none (decorative, `aria-hidden` via React) |
| Palette = official template | pptx `slideLayout/slideMaster` XML: `F2F4FF`×124, `2EF2C2`×89, `12183F`×75, `6150EA`×44; font `Readex Pro`×8763 | **true** — the kit's four colours and typeface are the organisers' own |
| Readex Pro variable, OFL, 87 KB subset | fontTools: `wght` 160–700, 73 glyphs in U+0600–06FF, all core letters U+0621–064A present, all tashkeel present | accepted; licence file shipped at `public/fonts/OFL-ReadexPro.txt` |
| Contrast ≥ 4.5:1 for every text/background pair | computed WCAG relative luminance | navy/off-white **15.6**, white/violet **5.46**, badges 7.0–7.9, dark badges 11.6–12.5, dark link 5.93 — all pass AA (large text AAA) |
| React `Icon`/`Logo` compile under strict TS | `tsc -b` with `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` | clean, no changes needed |
| Logo concept (eye = مصحف pages, 8-point star + check) | visual review of PNG renders | coherent, scales to 16 px, works on dark |

## 2. What the kit got wrong or left open — and what was done

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 1 | **`not_found` coloured red (`#C62C45`).** Our safety contract says «لم يوجد في مصادرنا» is *information about coverage*, never a verdict; red reads as "wrong". | High (SAFETY §1.3) | Overridden in `index.css`: `not_found` → neutral slate `#4B5280` / `#ECEEF7` (contrast 7.45). Red is reserved for *errors* (`--bs-error`). Recorded as **E-032**. |
| 2 | **Mushaf font not shipped.** Kit referenced KFGQPC Uthmanic HAFS (non-commercial licence, external download) and relied on it for `.bs-mushaf`. | High | Shipped **Amiri Quran** (SIL OFL 1.1, aliftype) subset to 59 KB woff2; fontTools confirms every Uthmani mark used by Tanzil is present (U+06D6–06ED, U+0670, U+0671, U+0653–0655, ۝, ﴿﴾). Licence at `public/fonts/OFL-AmiriQuran.txt`. KFGQPC kept as a *fallback name* only. |
| 3 | Readex Pro subset lacks **ﷺ (U+FDFA)** and **۝ (U+06DD)**; also drops U+063B–063F (non-Arabic-language letters, acceptable). | Medium | ﷺ falls back to the system font in UI text (acceptable, ligature renders everywhere); corpus text never uses the UI font — it is always set in Amiri Quran, which has both. |
| 4 | `manifest.webmanifest` advertised `share_target: /share` and `?mode=` shortcuts — **routes that do not exist**. | Medium (broken promise to the OS) | Removed `share_target`; shortcuts reduced to `/`. Re-add when the route ships. |
| 5 | `head-snippet.html` carried `https://basira.example/` canonical/hreflang/OG URLs. | Low | Not copied verbatim. OG image paths made relative; canonical/hreflang omitted until the production domain exists (WP-10). |
| 6 | Kit's `tokens.css` sets `:focus-visible { outline: none; box-shadow }` globally. | Low | Kept (box-shadow is a visible focus indicator, passes 2.4.7); verified on buttons, links, textarea, file input. |
| 7 | OG image background uses the organisers' template artwork — kit's own LICENSE-NOTES restrict it to competition use. | Note | Accepted for the competition; `docs/brand-kit-LICENSE-NOTES.md` §4 records the obligation to swap the background (`tools/build_og.py`) before any post-competition publication. |
| 8 | README states «الأيقونات `aria-hidden` إلا بعنوان» — correct in React, but raw SVG files have no `<title>`, so direct `<img>` use would need `alt`. | Note | We only use the React component. |

## 3. Design decisions on top of the kit (application layer)

* **Information architecture of the result card** ("moment of truth"): status badge + kind chip in a raised header; the user's text as a quoted block; the fixed message; notices with icons; then per-position **two panes — «نصك — كما كتبته» / «نص المصدر — حرفيًا من المصدر»** — source pane set in Amiri Quran at 1.5 rem / 2.1 line-height, bordered teal so the eye lands on the Mushaf text first.
* **Empty state** with four live-verified examples (verbatim ayah, ayah with a common spelling slip, hadith with its source, mixed post). Clicking fills the composer; never auto-submits.
* **Pillars row** under the hero restates the five product guarantees with kit icons (byte-exact, no generation, no judgment, nothing stored, deterministic).
* **Footer** = "what Basira does and does not do" (4 principles) + sources with version/licence from `/v1/sources` + API/GitHub links.
* **Dark mode**: kit tokens + overrides for diff highlights, not_found, error; toggle persisted; applied before first paint by an inline script (no flash); honours `prefers-color-scheme` when unset.
* **No `text-transform` on any Arabic or corpus text** (only the Latin wordmark «BASIRA» is uppercased). Corpus text: `letter-spacing: 0 !important; font-synthesis: none; unicode-bidi: isolate`.
* **Touch targets** ≥ 44 px (`--bs-touch-min`) on every button, file input label, example button; icon-only buttons carry `aria-label`.

## 4. Measurements after integration

| | before | after |
|---|---|---|
| CSS | 149 lines, system fonts | 18.5 kB (4.4 kB gz), 2 self-hosted OFL fonts (87 + 59 kB, preloaded / lazy) |
| JS bundle | 249 kB (79 kB gz) | 269 kB (85 kB gz) — +6 kB gz for 40 inline icons + logo |
| vitest | 8/8 | 8/8 (one jsdom `matchMedia` guard added in code, not in tests) |
| tsc -b strict | clean | clean |
| Playwright Chromium | blocked (libatk) | **working** after `apt-get install libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libgbm1 libasound2 libnss3 …` → E2E unblocked (STATE §2 item 18) |

## 5. Open items

* ~~Run `npm run e2e` (axe WCAG 2.2 AA sweep now possible) and record results in `docs/UX_LOG.md`.~~ **Done** — 1/1 passed, axe 0 violations on light/dark × desktop/mobile; one real SC 2.5.8 defect (18 px footer links) fixed. See `docs/UX_LOG.md`.
* Production domain → canonical/hreflang/OG absolute URLs (WP-10).
* `/docs` footer link points at the backend's OpenAPI page; needs a reverse-proxy rule in production (see `docs/INTEGRATIONS.md`).
