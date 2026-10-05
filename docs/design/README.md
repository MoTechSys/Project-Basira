# docs/design — Visual identity, information architecture, mobile UX

> **Status:** identity v4 «ختم المعارضة» = **implemented in `frontend/`** (E-056, §7).
> UX fixes E-UX-01…05 = **shipped in code** (see §6).
> Every number below was produced by a command; the command or evidence file is named next to it.

| Folder | Contents |
|---|---|
| `brand/` | Seal + state glyphs as SVG, the generators (`seal.py`, `glyph.py`), palette + contrast check (`tokens.py`), `logo-sheet.png` |
| `mockups/` | v4 screens (phone + laptop, input + result), `NEW_STRINGS.proposed.json` (12 UI strings not yet in `messages/` or `site/strings.ts`) |
| `evidence/` | `battery-before.txt` / `battery-after.txt` — the 66-check mobile battery run against the live server |

---

## 1. Research → decisions

| Question | Finding (source) | Decision |
|---|---|---|
| What does Basira *do*, in one gesture? | It collates a quoted text against its source, letter for letter (product, `docs/ARCHITECTURE.md`). | The mark must express *collation*, not "AI" or "an eye". |
| Is there a native sign for "collated against its source"? | Ibn al-Ṣalāḥ, *al-Muqaddima*, type 25, rule 7: scholars put a **dāra** (circle) between hadiths, left empty; once the text was collated against its source **a dot was placed inside**. Verified on islamweb (text captured in the research workspace). | Empty dāra = not matched, dotted dāra = collated. This becomes both the logo and the four state glyphs. |
| What is the unit of the dot? | Ibn Muqla's proportioned script measures letters in rhombic pen dots (nuqta). | The dot is a **rhombus**, not a circle. |
| What frames it? | The 8-pointed khatam (two squares) is the rub' al-hizb ۞ printed in every mushaf to mark quarters. | Seal = khatam with the dāra cut through it. |
| Must not resemble the Star of David | Hexagram = 6 tips at 60° from two triangles. | Khatam = **8 tips at 45° from two squares**. Enforced by `python3 brand/seal.py --check` (fails the build if the geometry ever drifts). |
| Competition visual context | IslamicAIch site: navy #0E1237, violet #6251EB, Readex Pro (screenshots in the research workspace). | Keep navy + violet lineage and Readex for UI, add manuscript gold and paper so Basira does not look like a copy. |

### 1.1 Seal geometry (`brand/seal.py`)

```
grid 24 × 24, centre (12,12)
khatam   two squares, half-side 7.6, one rotated 45°   → 16 vertices, 8 tips, tips every 45°
dāra     window r = 5, even-odd cut                     → reads at 16 px (logo-sheet.png, "16")
nuqta    rhombus, half-diagonal 2.6, gold
```

`$ python3 docs/design/brand/seal.py --check`
```
vertices: 16 | outer tips: 8 | tip angles: [0, 45, 90, 135, 180, 225, 270, 315] | gaps: [45]
OK: 8-fold khatam (a hexagram would be 6 tips at 60°)
```

### 1.2 State glyphs (`brand/glyph.py`) — one construction, four states

| Status (API) | Glyph | Meaning carried from the manuscript convention |
|---|---|---|
| `found` | ring + **filled** rhombus | collated: the dot is placed |
| `partial_match` | ring + **hollow** rhombus | collated, wording differs |
| `needs_review` | ring + **bar** | not settled — look again |
| `not_found` | **empty** ring (ghufl) | not matched in *our* sources (never "does not exist") |

Colour is never the only carrier (WCAG 1.4.1): the inner shape alone distinguishes the four states.

### 1.3 Palette (`brand/tokens.py`)

| Token | Hex | Use |
|---|---|---|
| night | `#0B0F2E` | header/hero band, app icon |
| ink | `#12183F` | text on paper, seal on light |
| paper / sheet | `#F6F2E9` / `#FFFDF8` | page / cards |
| gold / gold-light | `#B8893A` / `#D9B66E` | nuqta, jadwal rules, active-nav rhombus (decor only on light; text only on night) |
| found / partial / review / nf | `#0B6B52` / `#2E42B5` / `#8A4300` / `#4B5070` | the four states, each with its own tint background |

`$ python3 docs/design/brand/tokens.py | tail -1` → `text failures: 0` (21 text pairs ≥ 4.5:1).
Night-band pairs (measured in the design workspace): gold-light on night **9.69**, moon `#C4C8E0` on night **11.31**, mist `#9AA0C3` on night **7.30**.
Gold `#B8893A` on sheet is **3.09** → used for graphics only, never for text.

### 1.4 Type

| Role | Face | Why |
|---|---|---|
| UI | Readex Pro (already shipped, `frontend/public/fonts`) | competition lineage, Arabic + Latin, variable weight |
| Scripture (API `source_text`) | Amiri Quran (already shipped) | Uthmani marks render; text is never transformed (rule 4) |
| Headings (proposal) | Amiri 700 (OFL) | Naskh = the hand of the manuscripts the concept comes from |
| Wordmark (proposal) | Reem Kufi 600 (OFL) | Kufic = the hand of seals and early mushaf headings |

Rules: Arabic line-height 1.6–2.4, **no letter-spacing on Arabic**, ≤ 7 font sizes per screen (measured 5–6, §5).

---

## 2. Information architecture — what appears where

Measured on the live build (`/` and `/check`, `screens` = page height ÷ viewport height, iPhone 13 = 390×664 visible).

### 2.1 Page 1 — `/` (landing: the hook)

| Order | Section | Phone (top / height) | Laptop | Job |
|---|---|---|---|---|
| 1 | Hero «قبل أن ينتشر النص… تأكّد أنه نُقل بحرفه.» + Lens demo | 0.10 s / 1264 px | 0.08 s / 862 px | promise + a recorded real response |
| 2 | «ثلاث خطوات. دور كل طرف واضح.» | 2.01 s | 1.03 s | who does what (AI extracts, engine matches) |
| 3 | «أربع حالات فقط. بلا أحكام.» | 3.68 s | 1.76 s | the four states, no verdicts |
| 4 | «الخدمات» | 5.20 s | 2.38 s | text / image / English / guard / MCP / receipt |
| 5 | Trust band + footer | 7.97 s | 3.35 s | sources, limits |
| — | **Total** | **9.48 screens** | **4.36 screens** | |

**Finding:** on a phone the landing page is 9.48 screens long, and the *first tappable action into the product* («جرّب بنصّك») is inside the 1264 px hero. Proposal (pending owner): keep `/` as the hook, but the v4 mockup moves the composer itself into the hero (`mockups/mobile-1-input-full.png`), so a visitor can check text without leaving page 1.

### 2.2 Page 2 — `/check` (the workspace)

| State | What is on screen | Phone | Laptop |
|---|---|---|---|
| **Empty** | title · mode tabs (نص عربي / صورة / اقتباس إنجليزي / الحارس) · composer · «افحص» · examples · two fixed notices | 3.25 screens; button bottom **546 px** of 664 | 1.79 screens; button bottom 638 of 900 |
| **Busy** | button label «جارٍ الفحص…», disabled; results region `aria-busy="true"` | same | same |
| **Result** | summary («٤ اقتباسات · زمن المعالجة …») · status strip (also a filter) · the user's own text with each quote highlighted in place · pipeline strip («ما الذي حدث في هذا الفحص») · receipt | stack: highlights first, details in a **bottom sheet** on tap | split: text left, details panel right (sticky), first "attention" quote pre-selected |
| **Error** | alert banner (API message in UI language); the previous report is cleared | banner focused + scrolled to | same |

### 2.3 Phone interaction — what happens when people tap

```
paste ─▶ «افحص» (visible without scrolling on 320×568 and up)
          │  label → «جارٍ الفحص…», results region aria-busy
          ▼
result arrives ─▶ page scrolls to the summary (smooth; instant if prefers-reduced-motion)
                  focus moves to #results → screen readers announce it
          │
tap a highlight ─▶ bottom sheet (role="dialog"), focus inside, body scroll locked
          │        header: «الاقتباس ١ من ٤» · ← → · ✕
          │        body scrolls inside the sheet (e.g. 2172 px content in a 517 px body)
          ▼
✕ / Escape / tap outside ─▶ sheet closes, focus returns to the highlight, body scroll restored
```

---

## 3. Mockups (v4 proposal)

| | Phone | Laptop |
|---|---|---|
| Input | `mockups/mobile-1-input-full.png` | `mockups/laptop-1-input.png` |
| Result | `mockups/mobile-2-result-full.png` | `mockups/laptop-2-result.png` |
| Brand | `brand/logo-sheet.png` | |

All religious text in the mockups is copied from a live `/v1/check` response for `example_mixed`; nothing is hand-typed. UI strings come from `messages/ar.json`, `frontend/src/i18n.ts`, `frontend/src/site/strings.ts`; the 12 new ones are listed in `mockups/NEW_STRINGS.proposed.json` and must be added to those files before implementation.

---

## 4. Red lines checked against the design

| Rule | How the design respects it |
|---|---|
| No hand-written religious text | mockups render only API `quoted_text` / `source_text` / `ref_label_ar` |
| No verdict words | labels are `messages/ar.json` `labels.*` verbatim; `not_found` = «لم يوجد في مصادرنا» |
| No user data stored | design adds no storage; receipt stays stateless (E-052) |
| `state.py` / thresholds | untouched |
| Strings from catalogues | new strings listed, not inlined (`NEW_STRINGS.proposed.json`) |

---

## 5. Mockup audit (v4)

Script: Playwright, viewports 390×844 @2x and 1440×900, every text node's computed colour vs. its effective background.

```
mobile 1-input  {"screens":"1.22","hover":false,"sizes":["12px","14px","16px","21px","24px","34px"],"minT":44,"fails":[]}
mobile 2-result {"screens":"1.49","hover":false,"sizes":["12px","14px","16px","21px","24px"],"minT":36,"fails":[]}
laptop 1-input  {"screens":"1.00","hover":false,"sizes":["12px","14px","16px","21px","24px","46px"],"minT":44,"fails":[]}
laptop 2-result {"screens":"1.00","hover":false,"sizes":["12px","14px","16px","21px","24px","34px"],"minT":36,"fails":[]}
```

0 contrast failures · 0 horizontal overflow · smallest target 36 px (WCAG 2.2 minimum 24 px) · ≤ 6 type sizes per screen.

---

## 6. Mobile UX defects found in the shipped product, and fixes (code)

Battery: 66 checks × 6 viewports (Galaxy S8 360×740, iPhone SE 320×568, iPhone 13 390×664, Pixel 7 412×839, laptops 1440×900 and 1280×720) against the live server.

| | Before | After |
|---|---|---|
| `evidence/battery-*.txt` | **47 PASS · 19 FAIL** | **66 PASS · 0 FAIL** |

| ID | Defect (measured) | Root cause | Fix | Guard |
|---|---|---|---|---|
| **E-UX-01** | After «افحص» the report rendered below the fold on every phone (iPhone 13: summary at y = 711 on a 664 px screen, `scrollY 0`); focus stayed on `<body>` on all 6 viewports. | `setTimeout(() => results.focus(), 0)` ran **before React committed** the results: `#results` had 0 children and 0 px height (instrumented), so `focus()` silently failed and nothing scrolled. | Focus + `scrollIntoView` moved into a `useEffect` keyed on the result (runs after commit); `scroll-margin-block-start: 96px` clears the sticky header; reduced-motion → no animation. `Check.tsx`, `index.css` | vitest «moves focus to the filled results region…»; e2e «mobile 320x568 / 390x664 … result revealed» |
| **E-UX-02** | iPhone SE (320×568): «افحص» at y = 671, below the screen. | Page intro + 190 px composer above the button. | `@media (max-height:700px) and (max-width:959px)`: tighter intro, composer min 120 px (4 lines). Fonts stay ≥ 16 px. `lux.css` | e2e asserts button bottom ≤ viewport height |
| **E-UX-03** | On error the old report stayed under the new error banner (4 stale highlights). | A new check never cleared the previous result. | `setResult(null)` when a check starts; error banner focused and scrolled to. `Check.tsx` | vitest «an error clears the previous report and receives focus» |
| **E-UX-04** | At 320 px the four status chips stacked one per line (~190 px), pushing the text below the fold. | `flex-wrap` with long Arabic labels. | `≤ 420px`: 2 × 2 grid, chips keep ≥ 40 px height. `lux.css` | battery T04 |
| **E-UX-05** | At 320 px the header menu button sat at x = −18 px (half off-screen); page `scrollWidth` 338 > 320. | brand 102 px + 4 × 44 px actions + gaps > 320 px. | `≤ 359px`: action gap 0, header padding 12 px; every target keeps 44 px. `lux.css` | e2e asserts `scrollWidth ≤ innerWidth` |
| (also) | Results region did not announce loading. | no `aria-busy`. | `aria-busy={busy}` on `#results`. | vitest asserts `aria-busy="false"` after load |
| (also) | Two existing e2e tests opened `/` and waited for `#text`, which only exists on `/check` since f69e4df → both timed out. | stale test after the multi-page shell. | tests now open `/check`. | `npx playwright test` → 4 passed |

### 6.1 Reproduce

```bash
make gates                                                # ruff + mypy + pytest
cd frontend && npx tsc -b && npx oxlint && npx vitest run # 28 passed
npm run build && E2E_BASE=http://127.0.0.1:8000 npx playwright test   # 4 passed (server on :8000)
python3 ../docs/design/brand/seal.py --check              # 8-fold khatam
python3 ../docs/design/brand/tokens.py | tail -1          # text failures: 0
```

### 6.2 Known, not fixed here (needs an owner decision)

- `/` is 9.48 screens on a phone; the composer is not on page 1 (§2.1 proposal).
- oxlint: 9 pre-existing warnings (0 errors), none introduced by this change.
- ~~v4 identity is a proposal~~ → implemented, see §7.

---

## 7. Implementation of identity v4 (E-056)

| Where | What changed | Why this way |
|---|---|---|
| `src/site/identity.css` (new, loaded last in `main.tsx`) | tokens re-pointed to the manuscript palette; night band (header + page heads + footer) with the khatam lattice; gold chain closing the band; jadwal (double gold rule) on composer and annotated text; Naskh headings; gold primary action on night; dāra-coloured badges; teal accent → gold | one reviewable, revertible layer; layout/behaviour CSS underneath untouched |
| `src/brand/Logo.tsx` | eye-mark replaced by the seal; paths **generated** from `seal.py`; theme-aware via `--seal-ink` / `--seal-dot` | the geometry has one source of truth |
| `src/brand/Icon.tsx` | `state-found / partial / review / notfound` = dāra glyphs | same icon names → every caller (chips, badges, legend, cards) updated with zero component edits |
| `public/fonts/` | `Amiri-Bold.woff2` 99 968 B, `ReemKufi.woff2` 12 348 B + their `OFL-*.txt` | Naskh headings, Kufic wordmark; `font-display: swap`, Arabic `unicode-range` |
| `public/brand/{favicon,pwa,og,logo}` | all icons, social cards and logo files regenerated from `seal.py`; 6 eye-mark lockups deleted | no trace of the old mark anywhere (grep: 0 references) |
| `index.html`, `manifest.webmanifest` | theme colour `#0B0F2E`, og alt text describes the seal | browser chrome matches the night band |
| `src/site/Settings.tsx` | radiogroup `<ul>/<li>` → `<div>` | axe `listitem×3` (pre-existing) |

### 7.1 Guards (run in CI with the existing commands)

| Guard | Command | Result |
|---|---|---|
| Seal never becomes a hexagram | `npx vitest run src/brand/seal.test.ts` (parses `Logo.tsx` **and** `favicon.svg`) | 8 tips at 45° |
| Same, from the generator | `python3 docs/design/brand/seal.py --check` | `OK: 8-fold khatam` |
| Accessibility | axe WCAG 2.2 AA, 8 pages × light/dark × phone/laptop = 32 runs (`evidence/axe-v4.txt`) | **0 violations** (was 8 before v4: settings contrast ×12 nodes, listitem ×3, trust reveal) |
| Mobile battery | 66 checks × 6 viewports (`evidence/battery-v4.txt`) | **66/66** |
| Unit / e2e | `npx vitest run` · `npx playwright test` | 30 passed · 4 passed |
| Backend | `make gates` | exit 0 |

### 7.2 Live screenshots (after implementation)

`mockups/live-laptop-home.png` · `live-laptop-check.png` · `live-laptop-result.png` · `live-phone-check.png` · `live-phone-sheet.png` · `live-phone-check-dark.png`

### 7.3 Defects found while implementing, fixed

| Defect (measured) | Fix |
|---|---|
| Dark theme: wordmark and page title invisible (dark text on night) — `--paper` is redefined by the dark theme | `--on-night` constant for every text on the night band |
| iPhone SE: tabs-on-the-chain pushed «افحص» to y = 582 on a 568 px viewport | short-screen rule in `identity.css` → 562 |
| Mode tabs overlapped the page subtitle at 390 px | page head reserves the overlap (`padding-block-end`) |
| `needs_review` badge text was the old violet on the new amber tint | badges bound to the state tokens |
| /settings dark: key field 2.24:1, vendor 2.0:1, «المزيد» 3.11:1 (undefined `--lux-surface-2`/`--lux-text`) | bound to identity tokens → axe 0 |
