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

*End of BASIRA-AUD-001. Annexes A/B to follow upon agent completion.*
