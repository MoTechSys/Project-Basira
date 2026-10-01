# Audit Report — Basira Handoff Package (v1.x, 30 Sep 2026)

> **Document ID:** BASIRA-AUD-001 · **Auditor:** AI Development Engineer · **Date:** 2026-09-30
> **Scope:** The 55-file handoff package (`d1djem.zip`, sha256 `c069fbd4…6b63f`) — read in the mandated order (README → ANNEX_ALIGNMENT → HANDOFF_MASTER → SAFETY_AND_SHARIA → BUILD_SPEC → idea_description → registration_final_solo), plus the official participant guide (44 pp), the official scientific annex (8 pp), the competition terms (22 clauses), the submitted 10-slide deck, the organizer PPTX template, `max_architecture`, `devils_advocate`, `features_basira`, `selling_numbers`, and the tail of the 405 KB chat log.
> **Method:** Every externally checkable factual claim in BUILD_SPEC §2 was **re-verified live** from the primary source on 2026-09-30 (results in §2 below). Findings are graded **P0** (blocks delivery / scientific-integrity or legal violation), **P1** (will cost rubric points), **P2** (quality).

---

## 0. Executive verdict

| Dimension | Verdict |
|---|---|
| Research quality of the package | **Exceptional.** 12-axis research, three formal review rounds, every claim source-tagged, unverified items explicitly marked. This is well above hackathon norm. |
| Factual accuracy of technical claims | **100 % of the 14 claims I re-verified are correct** (hashes, row counts, licences, label distributions, ayah references, OHD numbering) — see §2. |
| Internal consistency | **Good but not perfect** — 9 contradictions/ambiguities found (§3), 2 of them P0. |
| Readiness to start coding on Oct 4 | **~85 %.** Blocked by 6 owner decisions (§6) and the P0 items in §3–§4. |
| Biggest single risk | A judge pastes a famous *sahih* hadith whose wording is not in the 62,169-row OHD corpus → tool says «لم يوجد في مصادرنا». Mitigated by wording only; **coverage rate must be measured and published** (HANDOFF §ز-15). |

**Bottom line:** Build exactly what is specified. Do not add scope. Fix the items in §3–§5 in the spec *before* Oct 4 (they are text edits, permitted). Get the 6 owner decisions now.

---

## 1. What the package is (one paragraph, for the record)

**Basira (بصيرة)** — Track 4 («أدوات المعرفة والتحقق») entry, solo participant, in the *AI in Service of Islamic Content Challenge* (Bathel Foundation, Riyadh). A bilingual (AR/EN) web tool: paste a post or upload its image → LLM extracts citation **spans only** (structured JSON, temperature 0) → deterministic Arabic normalization → hybrid retrieval (BM25 + char-3gram + optional vectors, RRF) over a build-time in-memory corpus (Tanzil Hafs 6,236 ayat; Open-Hadith-Data 62,169 rows / 9 books; HadeethEnc 3,582 entries) → exact then windowed token-Levenshtein match → **one of four states** `found / partial_match / needs_review / not_found` with word-level diff → post-validator rejects any output whose `source_text` is not byte-equal to the corpus. **Never** grades a hadith, never says «محرّف», never issues a fatwa, never generates religious text; relays HadeethEnc `grade` verbatim with attribution only on a direct match. Build window: **Oct 4 09:00 → Oct 6 23:59 Riyadh**, code only in that window (terms §8), everything before is a documented `baseline-pre-oct4` of text-only assets.

---

## 2. Live re-verification of BUILD_SPEC §2 factual claims (2026-09-30)

| # | Claim (BUILD_SPEC) | Verified value | Result |
|---|---|---|---|
| 1 | Tanzil licence CC BY 3.0, «CHANGING IT IS NOT ALLOWED» | tanzil.net/docs/text_license — exact text present | ✅ |
| 2 | Tanzil simple-clean sha256 `228df2a7…67610`, 6,236 lines | `228df2a717671aeb9d2ff573002bd28d6b3f973f4bc7153554e3a81663d67610`, 6,236 | ✅ byte-identical |
| 3 | Tanzil uthmani sha256 `bf4f57b9…312c8`, 6,236 lines | `bf4f57b968d03f4131c070b1e285da9be0e0a108a21c910e872801ca273312c8`, 6,236 | ✅ byte-identical |
| 4 | Basmala fused into ayah 1 in **112** surahs | Ayah-1 lines starting with basmala: **113** (= 112 fused + 1:1 itself). 9:1 has none. | ✅ (spec phrasing correct once 1:1 is excluded) |
| 5 | 3,985 ayat differ between rasm variants after normalization | **3,985** with the exact §3.1 pipeline | ✅ exact |
| 6 | OHD: ODbL 1.0 + DbCL 1.0, last commit `1515f6cb` 2022-07-30, 9 folders | LICENSE file confirms; commit `1515f6cb` 2022-07-30T12:35:57Z; 9 book dirs | ✅ |
| 7 | OHD row counts per book, total 62,169 | 7008 / 5362 / 4590 / 3891 / 5662 / 4332 / 1594 / 26363 / 3367 = **62,169** | ✅ all nine exact |
| 8 | OHD CSV 2 cols no header; mushakkala 3 cols with U+200F | Bukhari row 1: 2 cols; mushakkala: 3 cols, RLM present | ✅ |
| 9 | HadeethEnc AR xlsx v1.7.0, 3,584 rows incl. 2 header rows → 3,582 hadith; grade صحيح 3,213 / حسن 275; takhrij متفق عليه 1,256 | v1.7.0 (2025-11-12); 3,584 rows; 3,582 data; grade & takhrij counts **identical** | ✅ |
| 10 | HadeethEnc terms speak of «محتوى الترجمات» | Home page: «يتاح تنزيل محتوى الترجمات وإعادة نشره…» — scope ambiguity confirmed | ✅ (risk stands) |
| 11 | quran-validator MIT v1.3.0, data from QUL/Tarteel not Tanzil | package.json `license=MIT` v1.3.0; README credits QUL Uthmani + Imlaei Simple | ✅ |
| 12 | IslamicEval-2025-Subtask-1 Apache-2.0; dev.tsv 150 Q / 798 labels: 309/228/154/91/16 | Apache-2.0; 150 questions; 798 rows; CorrectAyah 309, WrongAyah 228, WrongHadith 154, CorrectHadith 91, NoAnnotation 16 | ✅ exact |
| 13 | `Evaluation_scripts` exists (content unverified) | Contains `Subtask_1A / 1B / 1C` | ✅ + resolved |
| 14 | dorar.net & sunnah.com return 403 to servers | dorar 403, sunnah 403; quranpedia 200, shamela 200 | ✅ |
| 15 | Example refs: 2:153 & 8:46; 31 hits «فبأي آلاء»; 2:255 & 3:2; 9:11; 21:30; 3:146; Ibn-Maja/220; Bukhari/1 | All reproduced with my own matcher; plus Bukhari/4639 for «خيركم من تعلم القرآن» | ✅ |
| 16 | MAHADDAT: README says CC BY 4.0, no LICENSE file | GitHub API licence `null`; README has a License section | ✅ (unresolved as stated) |

**Conclusion:** The Research Engineer's numbers are trustworthy. `corpus/manifest.json` can pin these hashes on day 1 with confidence.

---

## 3. Internal contradictions & ambiguities (must be resolved in the spec text before Oct 4)

| # | Sev | Where | Finding | Resolution I recommend |
|---|---|---|---|---|
| C1 | **P0** | SAFETY §1.3 forbidden words include **«صحيح»**; ANNEX §3 + HANDOFF decision 19 require UI to distinguish «وُجد في **صحيح** البخاري/مسلم» | The mandatory book name contains a forbidden lexeme. The §7.3 automated forbidden-word test would fail on every Sahihain hit. | Forbidden-word scanner must whitelist **book-name tokens from the corpus manifest** (`صحيح البخاري`, `صحيح مسلم`) and the literal `grade_text`/`takhrij` fields. Scan on whole-word basis outside those fields. Document in SAFETY §1.3. |
| C2 | **P0** | HANDOFF §(د) decision 12 & BUILD_SPEC §1: «**لا قاعدة بيانات، لا حسابات، لا تخزين**» vs SAFETY §7.1: report form «سنحفظ هذا البلاغ للمراجعة» | Storage of user-typed quote text on the server contradicts the no-storage guarantee and the PDPL stance. | Adopt SAFETY's own «تقدير» option as the **only** path: report button opens a pre-filled GitHub Issue (`.github/ISSUE_TEMPLATE/report.md`). Server stores nothing. Delete «سنحفظ هذا البلاغ» wording. |
| C3 | P1 | BUILD_SPEC §3.4 table says «**اقتباس أقل من 5 tokens**: `needs_review` if sim ≥ 0.75» vs HANDOFF §ز Peer item 24: «<5 words is not a quote at all unless quote-marked or attributed» | Two different rules for short spans. | Rule: <5 tokens **and** no quote markers/attribution → not extracted. <5 tokens **with** markers → exact-only; else `needs_review`. Write it once in §3.5. |
| C4 | P1 | BUILD_SPEC §3.5 rule 6: non-Arabic quote → **always `needs_review`** vs SAFETY §2.2 case 1 («Quran 9:11» English) → **`not_found`** + show Tanzil 9:11 | HANDOFF §ز item 6 already flags this and says SAFETY wins. BUILD_SPEC text not yet updated. | Update BUILD_SPEC §3.5-6: `language != ar` → `not_found` with `annex_note` showing the referenced ayah verbatim + `translation_note`. Add the SAFETY line to `messages/*.json`. |
| C5 | P1 | HANDOFF/registration say **"500 correct segments"**; `selling_numbers.md` says **1,000** stratified | Old doc. HANDOFF §(هـ) already says 500 is the commitment. | Nothing to change in HANDOFF; but **adopt selling_numbers' stratification** inside the 500 (rasm variants, partial quotes, other hadith wordings) — BUILD_SPEC §6.2 currently only stratifies by corpus. |
| C6 | P1 | BUILD_SPEC §2.2 says `messages/{ar,en}.json` is the **single source** imported by frontend at build; BUILD_SPEC §8 tree still lists `frontend/src/i18n/{ar,en}.json` | Two copies invite drift = forbidden-word leak. | Delete `frontend/src/i18n/` from the tree; frontend imports `backend/app/messages/*.json` via a build step (or a shared `packages/messages/`). |
| C7 | P1 | BUILD_SPEC §4 `/v1/check` response has `disclaimer_key` but §3.6 validator rule 5 checks a field named `disclaimer`; §4 also has no `collection_tier`, `known_claim`, `transparency_notice` fields required by ANNEX §6 / BUILD_SPEC §10-5 | Schema incomplete vs. its own requirements. | Finalize the JSON schema (see §5 below) **as a text artifact before Oct 4** — `docs/API.md` + `schemas/check_response.schema.json`. |
| C8 | P2 | BUILD_SPEC §9 M6 says demo runs «بالحالات الخمس»; HANDOFF §(ح)-6 says demo story is rewritten on the **four** states | Stale word. | «بالسيناريوهات الاصطناعية على الحالات الأربع». |
| C9 | P2 | `registration_final_solo.md` §8 still says «إطار مؤقت من أربع طبقات» | Historical (already submitted) — ANNEX §6-4 acknowledges. | Leave as record; ensure **no new artifact** reuses this phrase. |

---

## 4. Risks not (fully) covered by the package

| # | Sev | Risk | Why it matters | Mitigation to add to spec |
|---|---|---|---|---|
| R1 | **P0** | **Live-demo hosting single point of failure** (Render, one region, one process). Judging window 7–22 Oct; solo dev. | Rubric «جودة الحل التقني» level 1 = «لا يعمل المنتج». | Ship a **static fallback**: pre-computed results for all synthetic demo posts served from Cloudflare Pages when `/health` fails (allowed: cache is for synthetic demo inputs only, BUILD_SPEC §7-1). UptimeRobot + second region or Fly.io mirror (max_architecture §1). |
| R2 | **P0** | **Isnad-inclusive hadith rows**. OHD `text` = sanad + matn in one field (verified). User quotes are matn-only. Windowed matching handles it, but BM25 over full rows dilutes scores; `needs_review` false alarms on short matn likely. | False alarm on a correct matn is «أخطر خطأ» (HANDOFF §ز-16). | Add a **deterministic sanad-stripper for indexing only**: cut at the last occurrence of `قال رسول الله ﷺ / قال النبي ﷺ / أن رسول الله ﷺ قال / عن النبي ﷺ قال` patterns; index both `full` and `matn_guess` docs pointing to the same `num`. Display always the full verbatim row. Measure recall gain on the 500 set. |
| R3 | P1 | **LLM structured-output quality for Arabic spans** — offsets returned as integers may be code-point vs UTF-16 vs byte offsets depending on provider. | Silent span misalignment → wrong `quoted_text` → validator rejects → everything `needs_review`. | Require the model to return the **exact substring** *and* offsets; server re-locates substring in input (`str.find`, then fuzzy fallback) and ignores model offsets if mismatch. Test category J already covers injection; add category **M: offset robustness** (emoji, tashkeel, ZWJ). |
| R4 | P1 | **Vector channel** (MiniLM multilingual) unmeasured on classical Arabic; adds ~0.5 GB RAM + cold start. | Render Standard 2 GB; index ≈ <1 GB estimate. | Keep it behind `RETRIEVAL_VECTORS=off` default; enable only if M5 shows recall gain. Already the spirit of BUILD_SPEC §2.3 — make it a **config flag** explicitly. |
| R5 | P1 | **Rate-limit by IP** will throttle a judging panel behind one NAT (10/min). | Judges test in a group → 429s. | 30/min per IP for `/v1/check`, plus a `DEMO_MODE` bypass for pre-computed synthetic examples. Document in README «for judges». |
| R6 | P1 | **Sealed cases** (30) stored «outside repo, encrypted». Solo dev; if lost, integrity claim collapses. | — | Store the encrypted blob **in** the repo (`eval/sealed/cases.enc`) + `hashes.txt`; key kept by owner. Opening = committing the key on Oct 6. Verifiable, no loss risk. |
| R7 | P1 | **`collection_tier`** (ANNEX §3): OHD numbering ≠ canonical numbering (verified: Tirmidhi 3,891 rows). Saying «وُجد في صحيح البخاري» is Level-أ-safe, but the **number** shown is OHD-internal. | A hadith-science judge will check the number against Fath al-Bari numbering. | Always render «رقمه في مجموعة Open-Hadith-Data: N» (already required); additionally show the **first 8 words of the matn** as the human-verifiable anchor + dorar search link. |
| R8 | P2 | **HadeethEnc `explanation`** shown «كاملًا أو لا» — it is a *generated-by-humans commentary*; ANNEX Level ب content. | Basira is Level أ only. | Do **not** show `explanation` in v1. Show `hadith_text`, `grade`, `takhrij`, `link` only. |
| R9 | P2 | Deck slide 7 states HadeethEnc licence as fact (HANDOFF §ز-5). | Judges may compare deck vs SOURCES.md. | SOURCES.md row for HadeethEnc: `verified: partially — scope of “translations” wording to Arabic file unconfirmed; mode=link by default`. Consistency beats optics. |

---

## 5. API / data-model corrections to freeze as text before Oct 4

Add to `/v1/check` response (all deterministic, all from corpus or templates):

```jsonc
{
  "request_id": "uuid4",
  "disclaimer_key": "footer",               // rename target of validator rule 5
  "transparency_key": "transparency_notice",// ANNEX transparency clause
  "corpus": {"tanzil":"1.1","ohd_commit":"1515f6cb","hadeethenc":"1.7.0"},
  "extraction_degraded": false,
  "flags": {"chain_message": false, "refusal": false},   // refusal = level ب/ج/د detector fired
  "quotes": [{
    "id":"q1", "span":{"start":12,"end":58}, "quoted_text":"…",
    "kind":"quran|hadith_matn|isnad|attributed_saying|unknown",
    "language":"ar|en|other",
    "source_modality":"text|image",
    "claimed_source":{"raw":"رواه البخاري","parsed":{"book":"sahih_al-bukhari"}},
    "claimed_source_mismatch":false,
    "status":"found|partial_match|needs_review|not_found",
    "score":1.0,
    "message_key":"found_sahihain|found_other_book|hadith_partial|quran_needs_review|needs_review|not_found|…",
    "matches":[{
      "corpus":"tanzil|ohd|hadeethenc",
      "ref":{"surah":9,"ayah":11} /* or {"book":"sunan_ibn-maja","num":220,"numbering":"ohd","collection_tier":"sahihain|other_nine"} */,
      "source_text":"<verbatim>", "source_url":"…",
      "links":[{"name":"quranpedia","url":"…"},{"name":"dorar","url":"…"}],
      "diff":[{"op":"equal|replace|insert|delete","quote_range":[0,4],"source_range":[0,4]}],
      "grade":null /* or {"text":"صحيح","takhrij":"متفق عليه","source":"HadeethEnc","version":"1.7.0","url":"…"} */
    }],
    "known_claim": null /* or {"source_name":"…","source_url":"…"} — no grade text stored */,
    "external_search_links":[…]
  }],
  "timings_ms":{"extract":0,"retrieve":0,"match":0,"total":0}
}
```

Forbidden-word scanner exemptions: `source_text`, `grade.text`, `grade.takhrij`, `quoted_text`, and manifest book names.

---

## 6. Decisions only the owner can make (blocking; ask now)

1. **Repository licence** (Apache-2.0 recommended by team; interacts with terms §13/7). Nothing can be pushed publicly without `LICENSE`.
2. **HadeethEnc mode** — `embed` vs `link` for the Arabic file. Default `link` until a written confirmation. Do you want me to draft the enquiry email?
3. **Confirmation of acceptance** into the challenge (announced 30 Sep). All timelines depend on it.
4. **Hosting accounts**: Render paid plan (Standard $25), Cloudflare, GitHub public repo, **two** LLM providers with zero-retention settings, one vision provider. Account creation is not code — do it before Oct 4.
5. **AI_USAGE.md disclosure wording** about the pre-challenge research team (SAFETY §10-6).
6. **Guard API / model leaderboard**: confirm it stays *conditional P2* and is not promised anywhere new.

---

## 7. What is allowed **now** (before Oct 4) — text-only baseline

Per terms §8 and BUILD_SPEC §8 «نسخة البداية». I recommend producing all of these in this repo, tagged `baseline-pre-oct4`:

| Artifact | Status |
|---|---|
| `README.md` skeleton, `SAFETY.md`, `SOURCES.md` (with the hashes verified above), `AI_USAGE.md` draft, `CHANGELOG.md` first line | to do |
| `messages/ar.json`, `messages/en.json` — templates copied **verbatim** from SAFETY §1 + ANNEX additions | to do |
| `eval/PLAN.md` (pre-registered hypotheses), `eval/cases.yaml` (150 incl. `annex_case_*`), sealed 30 as encrypted blob + hashes | to do |
| `corpus/known_claims.json` (links only, retrieval dates) | to do |
| `docs/API.md` + JSON schema (from §5) , `docs/ARCHITECTURE.md`, ADR-001 (stack), ADR-002 (four states & thresholds), ADR-003 (no-storage) | to do |
| Screen wireframes (images) | to do |
| **No** `.py`, `.ts`, workflows, or download scripts | enforced by a pre-Oct-4 CI check that fails if any code file exists |

---

## 8. Stack decision vs. my environment baseline

BUILD_SPEC mandates **FastAPI/Python + React/Vite/TS**, hosted on **Render + Cloudflare Pages**. My sandbox has Python 3.13 and Node 22; all required libs (`fastapi`, `uvicorn`, `rapidfuzz`, `rank-bm25`, `fastembed`, `slowapi`, `openpyxl`) resolve from PyPI (verified). This **overrides** the generic Hono/D1 recommendation in `ENVIRONMENT_ANALYSIS.md §10` — the spec is authoritative and Render was chosen deliberately for an in-memory index that Workers cannot hold. I will record this as **ADR-001**.

---

## 9. Parallel adversarial reviews dispatched

Two independent agents were launched (30 Sep) to attack the spec from angles I might share blind spots with; their reports will be merged into this audit as **Annex A** (technical) and **Annex B** (sharia-safety & compliance):

| Agent | Task | ID |
|---|---|---|
| A | Hostile senior architect/NLP review of BUILD_SPEC + SAFETY | `d8052dd6-e81d-5d50-bedc-d46214997041` |
| B | Hostile sharia-scholar + legal/PDPL/licensing review of HANDOFF + ANNEX + SAFETY + Terms | `7b09dcb9-2c88-5d07-a671-8ce27697745e` |

---

## 10. Confidentiality handling

The package contains organizer materials behind login (scientific annex, PPTX template — terms §15) and 405 KB of internal chat logs. The entire intake directory is **git-ignored** (`.intake/`) and will never be committed. Only derived, non-confidential artifacts (this audit, specs, templates) enter the repository. The annex is *referenced*, never reproduced.

---

---

## 11. Triage of Annex B (independent sharia-safety & compliance agent)

Annex B (`docs/internal/ANNEX_B_sharia_compliance_review.md`, 52 KB) is reproduced verbatim. I re-verified its load-bearing claims before accepting them. Verdicts below are **mine**; where Annex B and the package disagree, I say who is right.

### 11.1 Findings I accept and promote to blocking

| Annex B item | My verification | Decision |
|---|---|---|
| **Confidentiality leak via our own docs** (clause 15/17): `HANDOFF_MASTER`, `ANNEX_ALIGNMENT`, and annex-quoting passages of `SAFETY_AND_SHARIA` reproduce non-public organizer content. | Confirmed by reading: ANNEX_ALIGNMENT §2–§5 quotes the annex tables nearly in full. | **P0.** Already enforced: entire `.intake/` is git-ignored. Rule added to `CLAUDE.md`: **no organizer-derived text enters the public repo; SAFETY.md is a rewrite, not a copy.** |
| **A1/A2 — fabricated verse → `needs_review` + «أقرب ما وجدناه»** offers a substitute ayah for text not in the Mushaf; and the qirāʾa caveat lives only in the *second* string of state 4. | Confirmed: SAFETY §7.3 forces `needs_review` for **any** Quran score <1.0 (incl. 0.2), while §2.2 case 1 forces `not_found` for «Quran 9:11». Genuine contradiction. | **P0.** Fix in spec: Quran state machine = `found` (1.0) / `quran_needs_review` (≥T_review, **with** diff + السورة:الآية + qirāʾa caveat as ONE render unit) / `not_found_quran` (<T_review, **no candidates shown**, wording: «لم يوجد هذا النص في المصحف المعتمد في مصادرنا، وهذا ليس حكمًا عليه»). §7.3 test text updated accordingly. |
| **A5 — hadith `partial_match` has no transmission-variant caveat** (asymmetry with Quran). | Confirmed by reading §1.1-2. | **P0.** Add to `hadith_partial`: «قد يكون الاختلاف روايةً أخرى أو اختلاف نُسخ لا تغطيها مصادرنا». |
| **A8 — Quran verse framed as hadith → `not_found`** (false statement on screen). | Confirmed: §3.2 says match both corpora, but §3.5 has no arbitration rule. | **P0.** Rule: any span matching Tanzil at 1.0 is `found` in Quran regardless of `kind`/attribution; add `claimed_source_mismatch` note «النص آية في {surah}:{ayah} لا حديثًا». |
| **Report form stores user text** (clause 9: consent does not cure). | Confirmed; matches my C2. | **P0.** GitHub-Issue route only. |
| **Forbidden lexicon incomplete** (`مضلل`, `تحريف`, `صحيحة`, `ثابت`…); `صحيح` load-bearing in book names. | Confirmed; matches my C1. | **P1.** Whole-word scan + feminine/plural forms + whitelist of manifest book names and literal fields; **layout test** that `grade` never renders without its attribution prefix. |
| **Annex-mandated edits not yet applied** in SAFETY (levels ب/ج/د naming, transparency merged into `privacy_notice`, quranpedia/shamela/dorar links, `sahihain` tier string, السورة:الآية in verse string). | Confirmed line-by-line. | **P1.** All are text edits → done in our `messages/*.json` + `SAFETY.md` before Oct 4. |
| **Refusal detector too narrow** for level (د) phrasing. | Confirmed (§2 lists no lexicon). | **P1.** Deterministic lexicon: `هل يجوز|ما حكم|أفتوني|حكم الشرع|أنا في|زوجتي|راتبي|بلدي` + level tag in response. |
| **`known_claims.json` includes snopes/factcheck.org** beside Islamic references. | Confirmed in SAFETY §3.3. | **P1.** Restrict to annex-approved Islamic references (dorar, islamqa, islamweb, binbaz). |
| **ODbL §4.3 produced-work notice + licence URI missing** from results page/PDF/SOURCES. | Confirmed. | **P1.** Add ODbL/DbCL notice line to footer & PDF; `THIRD_PARTY_NOTICES.md` with full licence texts (MIT, CC BY 3.0, ODbL 1.0, DbCL 1.0). |
| **Tanzil rasm choice**: annex approves King Fahd Complex (Uthmani); default display must be Uthmani. | Confirmed (ANNEX §3). BUILD_SPEC already indexes both rasms; display rasm not fixed. | **P1.** Display **Uthmani** verbatim; Simple used for index only. 100-ayah sample check vs Complex edition documented in SOURCES.md. |
| **PDPL**: “no storage” is a retention control, not a lawful basis; cross-border LLM call is an Art. 29 transfer. | Legal reasoning is sound; I cannot verify adequacy law here. | **P1 (owner-visible).** Add `/privacy` page (Art. 12/13 content: provider **named**, jurisdiction, purpose, rights), client-side PII blocker (email/phone/@handle/10-digit ID) **before** send, IP logging disabled at edge/host and stated. **Owner decision:** prefer a KSA-resident or zero-retention provider. |

### 11.2 Findings I accept with correction

| Annex B claim | Correction |
|---|---|
| “Upstream `hadith-islamware` has **no licence** on the page; plan’s ‘Unlicense’ is unverified.” | **Both partly right.** GitHub API returns `license: Unlicense` (file exists) — so the package was accurate. **But** the README asserts «Copyright (C) 2006-2014 Islam Ware» and the Unlicense was added by a *preserver*, not the rights-holder. → Chain of title is **unresolved**, not negated. Classical hadith matn is public domain; what may be protected is Islam Ware’s digitisation/compilation. **Decision (owner to confirm):** keep OHD (essential for coverage), record the full chain in `SOURCES.md` with `verified: chain-of-title unresolved`, add ODbL notice, and design so OHD text display can be switched to reference-only (`OHD_MODE=display|reference`) in minutes — mirroring `HADEETHENC_MODE`. |
| “A10 — 4-word sahih hadith `من غشنا فليس منا` → `no_quotes`.” | Partly. Peer item 24 says <5 words *without markers or attribution* is not extracted. Judges will paste bare text. **Decision:** threshold **3** tokens for exact-match-only; <3 not extracted. Add companion line when nothing is extracted from a short input: «إن كان النص اقتباسًا فضعه بين علامتي تنصيص أو أضف نسبته». |
| “A15 — HadeethEnc grade is an unattributed ruling.” | It **is** attributed — to the encyclopedia (an institutional source), which is what the annex requires («حكم معتمد في البيانات»). The defect is presentational: the grade must never be visually separable from `الحكم كما ورد في موسوعة الأحاديث النبوية`. → covered by the layout test above. |
| “Ship Uthmani *or the King Fahd text*.” | We cannot ship the Complex’s own digital file (licence unknown). Tanzil Uthmani + documented sample comparison is the defensible path. |

### 11.3 Findings I reject or downgrade

| Annex B claim | Why |
|---|---|
| “Index is a Derivative Database → share-alike may be triggered by public use (§4.4c).” | Index is **never conveyed**; built at deploy. ODbL §4.4 obligations attach on *conveying* the Derivative DB or *Publicly Using* it — a server-side index exposing only per-row verbatim text with attribution is the standard reading of “Produced Work”, and we add the §4.3 notice. Residual ambiguity acknowledged in SOURCES.md; **not blocking**. |
| “Branding as `مدقق`/`للتحقق` contradicts ‘does not judge’.” | Track 4’s own title is «أدوات المعرفة **والتحقق**». Verifying *transmission* (نقل) is exactly the claimed scope; footer already says «للتحقق من **نقل** الآيات والأحاديث». Keep; no change. |
| “`لا تحكم` is ambiguous imperative/indicative.” | Cosmetic; resolve with «لا تُصدر بصيرة حكمًا على…» in `footer`. P2. |

### 11.4 Net effect on plan

- **New P0 count: +5** (confidentiality of derived docs; Quran state machine; hadith caveat; cross-corpus arbitration; report store) — all **text/spec fixes**, permitted before Oct 4.
- **New owner decisions: +2** — OHD chain-of-title posture; LLM provider jurisdiction/retention.
- No change to product scope, stack, or timeline.


---

---

## 12. Triage of Annex A (independent hostile technical review)

Annex A (`docs/internal/ANNEX_A_technical_review.md`, 54 KB) instrumented the real Tanzil corpus. I **re-ran its two critical experiments myself** before accepting anything.

### 12.1 Independent re-verification

| Annex A claim | My re-run (Tanzil simple-clean, BUILD_SPEC §3.1 pipeline) | Verdict |
|---|---|---|
| §2.1 «إن الله **علي** كل شيء قدير» (typo for على) → exact `found`, 11 verses, empty diff | **11 verses**: 2:20, 2:106, 2:109, 2:148, 2:259 … — score 1.0, diff empty | ✅ **Confirmed. Critical.** |
| 595 verses exposed to the على/علي collapse | **594** | ✅ (off by one) |
| Only 6,055 distinct normalized verse strings; 98 collision groups | **6,055 / 6,236; 98 groups** | ✅ exact |
| §2.2 «قل هو الله واحد» and «الحمد لله رب العالمون» score **exactly 0.750** (knife-edge on `≥0.75`) | **0.75 / 0.75** | ✅ Confirmed |
| §2.2 «إن الله يحب الصابرين» best ≤0.50 → case unsatisfiable | **0.75 vs 2:153** («إن الله **مع** الصابرين», 1 substitution / 4 tokens). Agent only checked the spec's named candidate 3:146. | ❌ **Corrected** — case is reachable, but on the same knife-edge. The real defect stands: all three category-C examples sit exactly on the threshold. |

### 12.2 Accepted → promoted to blocking (spec/text edits before Oct 4; code on Oct 4)

| # | Finding (Annex A §) | Decision |
|---|---|---|
| **T1 P0** | Loose normalization erases the exact evidence the product promises to highlight (§2.1). | **Dual-orthography gate**: loose tokens for retrieval; a **strict** form (keep ة/ه، ى/ي، أإآٱ، ؤ/ئ; drop only diacritics/RLM/tatweel) must also match before `found`. Strict mismatch → `needs_review` with diff on the *strict* tokens. Property test: `found ⇒ strict-equal segment`. This makes `annex_case_11_misquoted_ayah` pass on the exact adversarial input. |
| **T2 P0** | Threshold rows contradict for <5-token Quran quotes; all category-C examples land on 0.750 (§1.3, §2.2). | Single precedence rule; short-quote row applies **after** corpus row; Quran review band becomes `0.60 ≤ sim < 1.0` (≥3 tokens) so a one-word change in a 4-word ayah (0.75) is safely inside the band; add boundary cases at ±0.002 (R12). Re-calibrate on Oct 4 and publish the curve. |
| **T3 P0** | RRF top-100 truncation can drop the exact match before exact stage (§2.5). | Exact stage runs on the **full inverted index** (measured <1 s for 6 quotes over 2×6,236). RRF only for fuzzy fallback. |
| **T4 P0** | Documented misquote-as-`found` via alternative narration (§2.6, BUILD_SPEC L259, cat. F). | Never a clean `found` with empty diff when strict form differs; emit `matched_other_wording` notice + diff vs. the record the user most plausibly meant. Category F expectations rewritten. |
| **T5 P0** | Eval plan impossible under own rate limits (§1.11); IP limiter behind proxy counts everyone as one client (§2.15). | Eval traffic uses an `X-Eval-Key` header (server-side secret) bypass; limiter trusts exactly one proxy hop; 30/min per IP; CORS `*.pages.dev` + prod. Smoke-test from 2 networks before M2. |
| **T6 P0** | `/health` returns 200 with empty corpus (§2.11). | `/health` reports `corpus.loaded`, per-corpus doc counts, `rss_mb`, `build_sha`; returns 503 until loaded. |
| **T7 P1** | Memory estimate omits char-3gram postings (~2.2 GB) (§2.8). | Postings as `numpy.int32` + offsets; char-3gram for **Quran only**; hadith uses BM25 words + (optional) matn-window index. Measure RSS at M3; hard budget 1.5 GB. |
| **T8 P1** | Vector channel = pure cost in P0 (§2.9). | **Cut from P0** (`RETRIEVAL_VECTORS=off`), documented as P2. Matches my R4. |
| **T9 P1** | `needs_review` is a 4-in-1 bucket → degenerate F1 (§1.13, §4.5). | Add machine-readable `reason ∈ {near_miss, short_quote, stage_failure, validator_reject, non_arabic, image_unconfirmed}`; headline metric = `found`-precision on A/B/E + FPR; F1 reported second with the degenerate baseline stated. |
| **T10 P1** | NFC vs NFKC inconsistency (§1.7); presentation forms (ﷲ U+FDF2) unhandled (§2.3). | Display path: **no** normalization (bytes as in corpus). Index path: explicit map for U+FDF0–FDFD → spelled forms *before* NFKC; validator byte-equality on raw corpus bytes. |
| **T11 P1** | OCR→check binding is client-asserted (§1.14, §2.12); images sent with EXIF (§5.4). | `/v1/ocr` returns HMAC token over (raw_ocr_text, ts); `/v1/check` with `source_modality=image` requires it; server re-encodes image via Pillow (strip metadata, downscale), validates magic bytes. |
| **T12 P1** | Missing schema fields & response-level notices (§2.11, §1.5); `score` invites reading as confidence. | Folded into §5 schema: `notice_keys[]`, `window_refs[]`, `basmala_token_offset`, `Retry-After`, status↔code map, rename `score`→`similarity`, `grade.source_key`. `503 degraded` removed — degraded is a 200 with `extraction_degraded=true`. |
| **T13 P1** | Unbounded `rules.py` output → compute DoS (§2.16, §5.1); one-word quotes flood (§2.4). | Min quote length: 2 tokens Quran / 3 hadith unless quote-marked; cap 30 spans total; cap positions returned (5) with count; per-request compute budget → degraded. |
| **T14 P1** | Calibration provenance is an unpublishable script (§2.17). | Calibration **method** written as text in `eval/PLAN.md` before Oct 4; every «قيمة مبدئية» cites it. Re-run as code on Oct 4. |
| **T15 P1** | Fixed seed vs «بذرة جديدة» in M9 (§1.12). | Keep seed 20261004; publish before/after on the **same** set; optionally add a second fresh-seed set as extra evidence, never as replacement. |
| **T16 P1** | `title` field (HadeethEnc) contains grade words and is not exempt from lexicon scan (§2.10-4). | `title` not displayed in v1 (only `hadith_text`, `grade`, `takhrij`, `link`). Consistent with my R8. |
| **T17 P1** | `claimed_source_mismatch` asserts an unprovable negative (§2.13). | Template → «وُجد في {X}؛ لم نجده في {Y} ضمن المرشحين المسترجَعين» and flag only when the claimed book was searched exhaustively (exact stage on full index makes this provable for exact hits). |
| **T18 P1** | CI eval cache keyed by reversible hash of user text; no baseline file (§4.7). | Cache only for the **synthetic** fixed case set (allowed); key = HMAC(secret, case_id); `eval/results/baseline.json` committed; CI asserts provider model IDs. |
| **T19 P2** | Three-run range mislabeled; per-category CIs with n<30 (§4.2, §4.4). | Label «extraction variance only»; CIs only for n≥100; small n marked indicative. |
| **T20 P2** | No degraded-path test; no boundary tests; sealed-set composition unstated (§4.10, §4.1, §4.9). | Add 3 both-providers-down cases, 12 boundary cases, publish sealed composition. |

### 12.3 Accepted with correction

| Claim | Correction |
|---|---|
| Category-C case «إن الله يحب الصابرين» unsatisfiable | Reachable at 0.75 via 2:153. Defect reclassified from *unsatisfiable* to *knife-edge* — remedied by T2. |
| Total effort R1–R12 ≈ 41 h «more than half the window» | With T8 cut and v0.9 (LLM-free) shipped first (Annex A §3.2 — which I adopt as the **build order**), the irreducible set is ≈24 h — feasible for D1–D2 with AI-assisted coding. |

### 12.4 Rejected / downgraded

| Claim | Why |
|---|---|
| `link`-mode HadeethEnc contradicts mandatory grade display (§1.8) | Not a contradiction: in `link` mode the *grade line* still shows `grade`+`takhrij` (short factual fields, quoted with attribution — the annex's «حكم معتمد في البيانات») while the full `hadith_text` is **linked** not embedded. Spec wording will make this explicit. |
| «No storage» has four exceptions (§1.10) | Demo cache is for **synthetic** fixed inputs; CI cache same; `known_claims` keys a curated list, not user text; report store is **deleted** (C2). After these, the only hash of user-derived text is none. Consistent. |
| Window docs unjustified (§2.11) | Cross-ayah quotes are common in posts («…الصابرين ۝ الذين إذا أصابتهم…»). Keep 2-verse windows **only**, add `window_refs[]`, and add 5 cross-verse cases to category A. |

### 12.5 Consolidated blocking list (after Annexes A + B)

**P0 — must be in the spec text before Oct 4, implemented Oct 4:**
C1 lexicon whitelist · C2 report→GitHub Issue · B-Quran state machine (found / needs_review-with-caveat / not_found_quran, no candidates) · B-hadith variant caveat · B-cross-corpus arbitration · B-confidentiality of derived docs · T1 strict gate · T2 thresholds/precedence · T3 exact-on-full-index · T4 no silent alternative-narration `found` · T5 limiter/eval bypass/CORS · T6 health gate · R1 static demo fallback · R2 sanad-aware indexing.

**Owner decisions (8):** licence; HadeethEnc mode; acceptance confirmation; accounts (Render/CF/GitHub/2×LLM/vision with zero-retention); AI_USAGE wording; Guard API stays P2; **OHD chain-of-title posture**; **LLM provider jurisdiction**.

**Build order (adopted from Annex A §3.2):** corpus+manifest → strict/loose Quran index + exact + diff + state machine + validator (gate: adversarial typo case passes) → hadith exact + grade → `rules.py` + `/v1/check` + cards = **v0.9 LLM-free demo** → LLM extraction → OCR → eval → docs/video.


---

*End of BASIRA-AUD-001 (rev 3 — Annexes A and B triaged; consolidated blocking list in §12.5).*
