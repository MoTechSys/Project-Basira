# Annex A — Hostile Technical Review of BUILD_SPEC + SAFETY (independent agent)

> Produced 2026-09-30 by an independent review agent (task `d8052dd6-e81d-5d50-bedc-d46214997041`) briefed as a hostile senior architect / NLP reviewer. Reproduced verbatim; the lead engineer's independent re-verification and triage is in `AUDIT_HANDOFF_PACKAGE.md` §12.

---

# Basira — Hostile Technical Audit

**Reviewer stance:** adversarial hackathon judge + NLP/systems reviewer. No praise, no document summary.
**Sources audited (read in full, line-numbered):**
- `BUILD_SPEC.md` — v1.1, 2026-09-30, 585 lines (cited as **BS Lnn**)
- `SAFETY_AND_SHARIA.md` — v1.1, 2026-09-30, 316 lines (cited as **SA Lnn**)
- Supporting: `ANNEX_ALIGNMENT.md`, `HANDOFF_MASTER.md` (context only)

**Independent verification performed for this audit** (Tanzil `simple-clean` v1.1 sha256 `228df2a7…d67610`, `uthmani` v1.1 sha256 `bf4f57b9…3312c8` — both match BS L75–76; 6,236 verses each; keys identical). A reference implementation of BS §3.1 normalization was written and run against the real corpus. Statistics were recomputed with SciPy. Every number below is either quoted from the documents or produced by that instrumented run; the method is stated so it can be reproduced.

---

## 0. Executive verdict

The safety architecture is unusually disciplined and the statistics in §6.2/§6.3 are arithmetically correct (verified). The **matching core is not**. §3.1 normalization is aggressive enough to erase the exact evidence §3.4/§3.6 claim to detect, and the retrieval/truncation design can discard the correct candidate before exact matching ever runs. One of the spec's own §6.1 test cases is arithmetically unreachable under its own §3.4 threshold table. The four-state machine cannot be exercised as drawn, the response schema has no slot for templates the spec itself mandates, and §7.4's rate limiter makes §6.4's own eval plan impossible.

**Top 5 items that fail a live demo in front of judges:**

| # | Failure | Trigger | Evidence |
|---|---|---|---|
| 1 | Misquoted ayah returned as `found` with **no** highlighted difference | Any quote containing `ى`/`ة`/`أ` variants — i.e. the most common Arabic typing pattern | §2.1 (L1) below: `إن الله علي كل شيء قدير` → 11 verses, score 1.0, empty diff, validator passes |
| 2 | A §6.1 case cannot pass its own threshold table | `إن الله يحب الصابرين` (category C) | §2.2: best similarity ≤0.50 vs 0.75 floor → `not_found`, case expects `needs_review` |
| 3 | Two §6.1 cases pass only because the score lands **exactly** on the threshold | `قل هو الله واحد`, `الحمد لله رب العالمون` → sim = 0.750 | §2.2: `>=` → `>` (or any rounding change) flips them to `not_found` |
| 4 | Eval cannot run inside the product's own rate limits | M8 = 150 + 500 + dev set, 3 runs, 200/day/IP | §4.7: 450 `/v1/check` calls = 2.25 days of quota |
| 5 | `/health` returns 200 while the corpus is unloaded | Index build/load failure on Render | §2.11: L304–309 reports providers only |

**Scientific-integrity items** (the category the brief asked to prioritise):
- §2.6: the spec **documents as a feature** that a misquote scores 1.0 when the substituted wording exists in another narration (L259), and §6.1 category F (L405) **expects `FOUND`** for it. A misquote is reported as verified with nothing highlighted.
- §2.1: a misquoted ayah is reported as `found`, which contradicts SA L71 (“لا تُكتب «آية مزيفة»… الصيغة الوحيدة: «لم يوجد في مصادرنا» أو «يحتاج مراجعة»”) in the opposite direction — the system over-affirms rather than over-condemns. Both are integrity failures; the second is the one judges will hit.
- No path in the design can imply a hadith is fabricated — the prohibitions (BS §10.2 L558, SA §2.1 L83, SA §1.3 L70, automated test SA L281) are genuinely well covered. **The residual integrity risk is over-affirmation, not over-condemnation.**

---

## 1. Internal contradictions

### 1.1 Where do user-facing strings live? Three answers, one document
- BS L56: `messages/{ar,en}.json` is “**المصدر الوحيد**؛ الواجهة تستوردها عند البناء **ولا تحمل نسخة مستقلة في frontend/src/i18n**”.
- BS L509 (repo tree): `frontend/ (Vite+React+TS) src/{…, **i18n/{ar,en}.json**}`
- SA L25: “القوالب مفاتيح في ملف i18n واحد (`**frontend/src/i18n/{ar,en}.json**` مثلًا)”
- BS L500: `backend/app/ … **messages/{ar.json,en.json}**`

Three locations for the one artifact that SA §7.3 L281 makes the subject of a mandatory automated test (“كل نص تُنتجه الواجهة أو الـAPI”). If the frontend ships its own copy, the forbidden-word test can pass on the backend copy while the UI renders the stale one. The layout at L509 directly contradicts the rule at L56.

### 1.2 Two spellings of the same enum, with no case-normalisation rule
BS L251: “**التعداد المعتمد في الـAPI والاختبارات والواجهة هو صيغة SAFETY الصغيرة**: `found / partial_match / needs_review / not_found`. ما ورد في هذه الوثيقة بالحروف الكبيرة (FOUND…) يُقرأ بها.” Yet §6.1's own case file writes `status: NEEDS_REVIEW` (L390) and the examples in the category table use `FOUND` (L400–411), while the API enum is lowercase (L333). Nothing in §6.3 or §6.4 says the comparison is case-insensitive, so the eval harness is specified to compare `NEEDS_REVIEW` against `needs_review`.

### 1.3 The threshold table contradicts itself for short Quranic quotes
- Quran row (L253): `needs_review` iff `0.70 ≤ sim < 1.0`; `not_found` iff `sim < 0.70`.
- Short-quote row (L255, “اقتباس أقل من 5 tokens”): `needs_review` iff `sim ≥ 0.75`; “غير ذلك” → `not_found`.

For a 4-token Quranic quote at `sim = 0.72` the two rows return different states. The rows are unlabelled as to precedence, and **every example in §6.1 category C is a 4-token quote** (L402: `قل هو الله واحد`, `الحمد لله رب العالمون`, `إن الله يحب الصابرين`). The entire “one word changed in an ayah” category sits exactly in the contradictory band.

### 1.4 The state diagram contradicts the threshold table
L266–274 draws `best sim ─► ≥T_partial ─► PARTIAL` with no corpus gate. The gate that prevents `partial_match` on Quran exists only in §3.5 rule 1 (L277), SA L41 and SA L283 — not in the machine, not in the table's structure. As drawn, a Quranic quote at `sim ≥ 0.75` produces `PARTIAL`.

### 1.5 SAFETY mandates two templates it never defines
SA L15 (quoting the official annex) adds two mandatory templates: `transparency_notice` and `found_other_book`. Neither appears in SA §1.1 (L31–54, four states only) nor in the §1.2 table (L58–67: `grade_line`, `no_grade`, `footer`, `refusal`, `no_quotes`, `privacy_notice`, `synthetic_badge`, `translation_note`). BS L351 then declares that **all** user-facing text “يؤخذ **بمفتاحه** من `SAFETY_AND_SHARIA.md` §1 **حصرًا**”. The two documents therefore jointly guarantee that two mandated strings have no authoritative source. BS L582 and ANNEX_ALIGNMENT §6 require `collection_tier: "sahihain" | "other_nine"` in the record and the response — that field appears nowhere in the §2.2 record schema (L124–134) or the §4 response (L319–348).

### 1.6 SAFETY is stale on the annex, in the same version it cites
SA L314 still lists “الملحق العلمي للتحدي ومستويات المحتوى فيه (**غير منشور علنًا**…)” as unresolved, and SA §10 says it “قد يضيف مصادر أو قيودًا تُحدِّث §3 و§4”. BS L582 records it as **delivered 30 September** with a concrete change list. Both files are stamped “الإصدار 1.1 · 30 سبتمبر”. SA §0 quotes the annex as binding while §10 says it hasn't arrived.

### 1.7 Two Unicode forms for the same byte-equality gate
SA L81: any Quranic/hadith text must be “مطابق حرفيًا (**byte-equal بعد توحيد Unicode NFC**) لسجلّ في المدوّنة”. BS L160: the pipeline applies “**NFKC**”. NFC and NFKC are different functions; the post-validator's byte-equality rule (BS L289) is written against neither. For Arabic the difference is not academic — NFKC applies compatibility decompositions (e.g. U+FDF2 ‎`ﷲ` → the 4-letter `الله`, U+FDFA/U+FDFB handled ad hoc at L160), so a source string can be transformed before the gate that is supposed to guarantee it wasn't.

### 1.8 HadeethEnc: `link`-mode default vs. mandatory verbatim grade display
- BS L457 / L108 / SA L147 / SA L311: licensing of the Arabic file is **unverified**; default `HADEETHENC_MODE = "link"`, “ولا يُرفع إلى المستودع”.
- BS L280 and SA L109: `grade_line` **must** display `grade` and `takhrij` verbatim, attributed, with the record link, whenever the quote matches a HadeethEnc record.

`link` mode cannot satisfy L280: you cannot display a verbatim field you are not licensed to reproduce. BS §2.2 L132–134 also stores `title`, `hadith_text`, `grade`, `takhrij` in the shipped corpus regardless of mode. The safe default and the mandatory output are mutually exclusive as written.

### 1.9 Open-Hadith-Data: “don't publish the index” vs. “the index is baked into the deployment image”
- SA L142: “**الأسلم ألا تنشر الفهرس**، بل سكربتًا يبنيه وقت البناء” and test sets should cite hadiths “**بالمعرّف لا بالنص**”.
- BS L147: “الحفظ: `index/*.npz` و`records.jsonl` **داخل صورة النشر**”.
- BS L508: `.gitignore`s `data/` and `index/` — but a Render service image is not a gitignore concern.
- BS §6.1 L396 stores corpus text in `cases.yaml` inside a **public** repo (`quote:` fields), which is the opposite of “بالمعرّف لا بالنص”.

ODbL's share-alike obligation attaches to a publicly distributed derivative database. Which artifact is the derivative — the image, the npz, or the YAML quotes — is left unresolved, and the two documents give opposite instructions.

### 1.10 “No storage” vs. four storage requirements
SA §5.2 L190 forbids storing text, images, and “**hash قابل للعكس لنص قصير**”. Against that:
- BS L445: CI caches extraction outputs “**بمفتاح hash**” (of the input text).
- BS L464: demo cache keyed by hash.
- BS L561 vs SA L118: `known_claims.json` is specified as `{id, claim_text, …}` in one file and `{claim_hash, source_name, source_url}` in the other; the response field is a third shape, `known_claim: {source_name, source_url}`. The matching key (`id` vs `claim_hash`) and its input (raw vs normalized text) are undefined — and a hash over short text is precisely what L190 forbids.
- SA §7.1 L267–268: the report flow is called “الاستثناء الوحيد من «لا تخزين»” but §7.2 L272–278 requires persisting reports, `REVIEW_LOG.md` entries and GitHub issues.

“No storage” is in fact “no storage except four things”, and one of them (hash keys) is explicitly prohibited elsewhere in the same document.

### 1.11 §7.4 rate limits vs §6.4/§9 eval plan
BS L473: `/v1/check` = **10/min and 200/day per IP**. BS L445: CI runs the 150-case suite on every push. BS L442: `--runs 3`. M8 (L544): 150 + 500 + IslamicEval dev in one evening. M9/M10 (L546–547): another 3 runs plus a regenerated FA set. Nothing exempts eval traffic from the limiter. 150 × 3 = 450 calls = **2.25 days** of the documented per-IP quota; adding the FA set and dev set puts day 5 near 2,100 LLM-backed calls, i.e. **~210 minutes of pure rate-limit waiting** at 10/min.

### 1.12 Fixed seed vs. “regenerate with a new seed”
BS L420: `eval/false_alarm.py` “من المدوّنة **ببذرة ثابتة** (`seed=20261004`)”. BS L546 (M9): “يُعاد توليد مجموعة الـ500 **ببذرة جديدة** بعد الإصلاح ويُنشر الرقمان معًا”. A new seed is a different population; the two numbers are then not comparable, which defeats the stated purpose of publishing both. Keeping the seed is the correct procedure and contradicts M9's wording.

### 1.13 `needs_review` is a four-in-one bucket
SA L54: “أي حالة غير (1)(2)(3)، ومنها: فرق في آية، أو درجة بين العتبتين، أو اختلاف في الاستخراج، أو فشل أي مرحلة (نموذج، OCR، مهلة)، أو نص قصير جدًا”. BS L266–274 routes every error/timeout/validator rejection to the same state. One state covers “near miss”, “LLM timed out”, “validator rejected”, “quote too short”, “non-Arabic quote” (L282). §6.3's 4×4 confusion matrix (L431) will have one dominant cell with no diagnostic content, and the headline metric (L432) treats `needs_review` and `not_found` as the same positive.

### 1.14 The OCR→check contract has no server-side binding
BS L355–362: `/v1/ocr` returns `ocr_text` + `needs_user_confirmation`; “المستخدم يراجع … ثم تُرسل الواجهة `/v1/check` مع `source_modality="image"`”. BS L278: an image quote “**لا يأخذ FOUND إلا بعد أن يؤكد المستخدم النص**”. There is no token, no signature, no server-side record linking the two calls, so both the modality and the confirmation are **client-asserted**. Any caller can set `source_modality: "image"` with no OCR having occurred, and the validator (§3.6) has no rule about it.

### 1.15 P1/P2 labels collide with the cut rule
BS L551: “إن تأخر M5 عن 23:00 يوم 4، **يُلغى كل P2**”. But BS §3.5 rule 7 (`chain_message`, L283) is **P1**, and L364's `/v1/guard` is P2. No milestone in §9 covers any P1 deliverable, and no cut rule exists for P1. Separately, BS L482 marks `pip-audit`/`npm audit` as “P1”, reusing the §1 L14 label for an unrelated axis.

### 1.16 `timings_ms` and `flags` don't match their own content
L347 fixes `timings_ms` to `{extract, retrieve, match, total}` — no OCR stage even though `/v1/ocr` is a documented endpoint with its own 15 s timeout (L371). L324 exposes `flags: {chain_message: false}` only, i.e. a P0 response always carries a P1 field and never carries a flag for `extraction_degraded`, which is a top-level boolean (L323) with no `message_key` to render.

### 1.17 SAFETY's mandatory source row names a model the build cannot use
SA L224 makes a `SOURCES.md` row mandatory for “نماذج التضمين (**مثل multilingual-e5-small** وترخيصها — «غير متحقق» حتى يُفتح)”. BS L150 states that model **does not exist in fastembed 0.8.1** and substitutes `paraphrase-multilingual-MiniLM-L12-v2`. The compliance document will therefore certify a dependency that is not in the product, while the model actually shipped has an unmeasured licensing row.

### 1.18 The sealed-set procedure doesn't seal against the calibration that set the thresholds
BS L416: the 30 sealed cases are “تُكتب **قبل 4 أكتوبر**”. BS L16/L261: the thresholds were produced by a **30 September** research-environment script and are only re-tuned on 4 October. The seal therefore protects against Oct 4–6 overfitting but not against the Sept 30 calibration that produced the numbers the cases will be scored against. The document presents the seal as if it covered both.

---

## 2. Technical design flaws and ambiguities

### 2.1 (Critical) §3.1 normalization destroys the exact evidence §3.4/§3.6 claim to detect
§3.1 step 5 (L164) maps `ى → ي` and `ة → ه`; step 4 (L163) maps `إ أ آ ٱ → ا`. These are applied **identically** to the query and to the corpus (L158). Consequence: the Quran's own `على` normalizes to `علي`, so a user who writes `علي` (the single most common Arabic orthographic slip, and precisely the class of error the annex's mandatory test case targets) produces an **exact** match.

**Instrumented result** — input `إن الله علي كل شيء قدير` (mushaf has `على`):
- normalized query: `ان الله علي كل شيء قدير`
- **22 exact hits across 11 distinct verses**: 2:20, 2:106, 2:109, 2:148, 2:259, 3:165, 16:77, 24:45, 29:20, 35:1, 65:12
- `score = 1.0`; diff on normalized tokens = **all `equal`**; §3.6 rule 1 passes because `source_text` is copied byte-exact from the corpus.
- **Emitted state: `found`, with nothing highlighted.** The annex's `annex_case_11_misquoted_ayah` (BS L582; the README's three red lines) requires the opposite.

Scale of the exposure: **595 of 6,236 verses** contain a normalized token `علي` derived from an original `على`. Any quote drawn from those verses is unprotected against this error class.

Second effect — **index collisions**. After §3.1 the Quran has only **6,055 distinct normalized strings (simple script)** and **6,057 (Uthmani)**: **181** and **179** verse records respectively collapse into shared normalized strings, in **98 collision groups** measured on the simple script (the Uthmani group count was not separately computed). Examples I reproduced: `2:1 ≡ 3:1 ≡ 29:1 ≡ 30:1 ≡ 31:1 ≡ 32:1` (all → `بسم الله الرحمن الرحيم الم`, an artifact of the L72 basmala strip); `2:5 ≡ 31:5`; `2:47 ≡ 2:122`; `2:134 ≡ 2:141`; `2:162 ≡ 3:88`. §6.3's “دقة المرجع” metric (L434) is **unachievable by construction** for those records, and §3.4's “عند التعادل تُفضَّل الوثيقة الأقصر” (L242) silently picks one.

**Fix (R1):** split the pipeline into *match-time* normalization (loose, as specified) and *confirm-time* verification (strict: preserve `ة/ه`, `ى/ي`, `أإآٱ/ا`, and the diacritic-bearing source). A candidate may only reach `found` if the **strict** forms also agree; otherwise `needs_review`. Keep a second strict index (small — only the 6,236 verses and a token-hash postings list). This also makes `annex_case_11` pass on the exact input above.

### 2.2 (Critical) §3.4's threshold table does not produce §6.1's own expected states
Applying §3.4 step b exactly (window lengths `{round(0.8n), n, round(1.2n)}`, `sim = 1 − Lev(tokens)/max(len(q), len(w))`, best over windows) to the three category-C examples (L402):

| quote | n | best sim (measured) | §3.4 row 3 (<5 tokens) | §6.1 expects | verdict |
|---|---|---|---|---|---|
| `قل هو الله واحد` | 4 | **0.750** | `needs_review` (`≥0.75`) | `NEEDS_REVIEW` | passes **exactly on the boundary** |
| `الحمد لله رب العالمون` | 4 | **0.750** | `needs_review` (`≥0.75`) | `NEEDS_REVIEW` | passes **exactly on the boundary** |
| `إن الله يحب الصابرين` | 4 | **≤0.50** (0.25 in my run; 0.50 is the arithmetic maximum for any window) | `not_found` | `NEEDS_REVIEW` | **FAILS** |

For the third case the only candidate named by the spec is 3:146 (`وكأين من نبي قاتل … والله يحب الصابرين`). The query `[ان, الله, يحب, الصابرين]` and the best window `[والله, يحب, الصابرين]` share a 2-token core; Levenshtein = 2 over `max(4,3) = 4` → **sim = 0.50**, below row 3's 0.75 floor and below the Quran row's 0.70 floor. Both rows give `not_found`. The case is unsatisfiable as written.

For the two that pass: they pass **at exactly 0.750** against a `≥ 0.75` test. A change from `>=` to `>`, a rounding change in `round(0.8n)`, or a different window set flips both to `not_found`. Two of the three examples of the spec's most safety-critical category are on a knife edge.

### 2.3 §3.1 order and coverage gaps
- Step 1 (L160) deletes `ﷺ`/`ﷻ` **before** NFKC. NFKC then expands the *other* Arabic presentation forms the spec forgot: U+FDF2 (`ﷲ`) → the 4-letter `الله`, U+FDF3, U+FDF4… These add spurious tokens to the query and to the corpus asymmetrically.
- Step 7 (L166) maps “كل ما ليس حرفًا عربيًا (`U+0621–U+064A`)” to a space. That range excludes U+0640 (handled at step 3) but also excludes U+06C0–U+06D5 and U+08F0–U+08FF (Arabic Extended-A marks), which are silently **deleted into spaces** rather than flagged — an Urdu/Persian-influenced input loses characters and the failure surfaces as `not_found` rather than `needs_review`.
- The spec has no rule for **tatweel inside a token** after step 3 removal causing token merging, and no rule for the Arabic-Indic digits U+0660–U+0669 (step 7 turns them into spaces, so `٢:٢٥٥` becomes two empty gaps — which is fine, but `سورة ٢` loses the surah number entirely while `claimed_source` parsing (L205) expects to read it).

### 2.4 No minimum quote length anywhere — a UI denial-of-service
§3.2's schema sets `span_start: minimum 0` and `span_end: minimum 1` (L191–192) with **no minimum span length**; §3.2's post-checks (L208–211) only require `span_end > span_start`. §3.4 step a (L230) then collects **all** matching positions. Measured over the real corpus:

| single token | verses containing it |
|---|---|
| `من` | 2,023 |
| `الله` | 1,664 |
| `ان` | 1,352 |
| `قال` | 371 |

L233 caps the *display* (“يُعرض العدد وأول 5 مواضع”) but the state is still `found`, the response still carries a match object per position unless capped, and the judge sees `found` for a one-word quote. `rules.py` (L213) is unbounded by the LLM schema's `maxItems: 30` (L186) — the union can exceed 30 quotes and nothing caps it.

### 2.5 (High) RRF truncation can discard the exact match before exact matching runs
§3.3 (L221–224): three channels at `top-50` each → up to **150** candidates → RRF `k=60` → “ثم تمرير **أعلى 100** إلى المطابقة”. With RRF, score = Σ 1/(60+rank):

| rank in one channel | score | rank 50 in **all three** | score |
|---|---|---|---|
| 1 | 0.016393 | 50 | 0.027273 |
| 5 | 0.015385 | 20 | 0.037500 |

A document that is rank **1** in the char-3gram channel (because it contains the exact substring) scores 0.0164 and **loses** to a document that is rank 50 in all three channels (0.0273). Since §3.4 step a only searches *candidates*, an exact substring match can be dropped before the exact stage. The spec's own calibration (L226) used a **different configuration** — “القناتان النصيتان وحدهما (top-30 لكل منهما)” — so the production path was never measured.

Note also that exact matching does not need retrieval at all: exhaustive token-subsequence scan over **all 6,236 verses × 2 scripts** for 6 representative quotes (including the 31-occurrence `فبأي آلاء ربكما تكذبان`) completed in **<1 s total** in pure Python in this sandbox. **Fix (R3):** run the exact stage against the full inverted index; use RRF only for the fuzzy fallback.

### 2.6 (High) A documented misquote-as-`found` path — integrity, not just accuracy
BS L259: “**حالتان من 150 بلغتا 1.0 لأن اللفظ المستبدَل موجود في رواية أخرى.**” BS §3.5 rule 5 (L281) and §6.1 category F (L405: `لا يؤمن أحدكم حتى أكون أحب إليه من ولده ووالده` ← `FOUND، لأن اللفظ نفسه موجود في Ibn-Maja/66`) turn this into an **expected** outcome. The result is a quote that differs from the text the user probably meant, reported as `found` with an empty diff and no signal that a different narration was matched. For a product whose one-sentence pitch is “كل آية وحديث في منشورك، إلى مصدره في ثانية — يكشف ويُسند ويُحيل” (L101), silently resolving a divergence by hopping to another narration is a correctness claim the tool cannot support. **Fix (R20):** when the matched record is not the record the user's wording most plausibly came from, emit an explicit `matched_alternative_narration` notice; never a clean `found` with an empty diff for a query whose strict form differs from the source.

### 2.7 Windowed Levenshtein has no complexity budget
For each candidate, §3.4 step b evaluates 3 window lengths × `(|doc| − n + 1)` windows × a full Levenshtein over ≤`1.2n` tokens. For a 3-verse window doc (~150 tokens) and `n = 20`: ~130 windows × 3 lengths × ~400 cells ≈ **150k cell ops per candidate**, × up to **100 candidates** ≈ 15M cell ops per quote in pure Python. L226's “**نحو 150ms للاقتباس الواحد بـPython خالص**” was measured on a 30-candidate set from two channels for 5–20-word samples — i.e. roughly a tenth of the production candidate count, with no truncation stage. §6.3 (L436) requires p95 latency on a 1–5 quote post, so the worst case (5 quotes × 100 candidates) has no stated budget. **Fix (R4):** banded Levenshtein (max-distance automaton), char-3gram Jaccard pruning before Levenshtein, and a per-request compute budget with a `needs_review`/degraded fallback.

### 2.8 Memory estimate is off by ~2× and omits the largest structure
L148: “متجهات 384 بعدًا × نحو 99 ألف وثيقة بـfloat32 ≈ 150MB. مع النصوص والفهارس، **أقل من 1GB**.” The vectors are the *smallest* structure. The char-3gram index over 62,169 hadith at ~600 chars ≈ **37M postings**; as `dict[str, list[int]]` at ~60 B/posting that is **~2.2 GB** before the word index, the 36,700 Quranic window docs, and the raw texts — against the Render **Standard 2 GB** plan (L33). Only the vectors were costed. **Fix (R13):** store postings as `numpy.int32` arrays + an offset table (~150 MB for 37M postings), or drop char-3grams for the hadith corpus (Quran is small enough to keep).

### 2.9 The vector channel is pure cost in P0
L150 states the model's quality on classical Arabic is **unmeasured**, and L226 states the two textual channels already put the correct document in the candidate set **for every** calibration case. SA L97 restricts semantic matching to proposing. But a vector-derived candidate still enters §3.4's fuzzy stage, where the token-similarity gate (0.75/0.70) is what actually decides — so the channel contributes recall only, at the cost of 150 MB, a model dependency, a `SOURCES.md` licensing row (SA L224), and extra latency. **Recommendation (R14):** delete it from P0; keep it as a documented P2.

### 2.10 Post-validator (§3.6) doesn't validate the things that matter
The five rules (L289–293) are: byte-exact `source_text`, `ref` exists, no model-authored text, a forbidden-word lexicon, `disclaimer` present. Missing:
1. **No rule that the user's quote actually differs from the matched source in the way the diff says.** The §2.1 false-positive produces an *empty* diff for a wrong quote and passes every rule.
2. No rule enforcing the machine's own invariants (`no partial_match with corpus=quran` — that exists only as a *test* at SA L283, not at runtime).
3. No rule that `matches[0]` is actually the best-scoring candidate, nor that `score` is consistent with the emitted state.
4. The lexicon rule (L292) scans “كل نص خارج الحقول الحرفية”, but SA L281 exempts only `source_text` and `grade_text`. `title` (BS L132, L107) is a corpus field that will contain `صحيح`/`حسن` in many records and is **not** exempted — displaying it trips the validator.
5. No rule against emitting `found` for a quote that the **strict** comparison rejects (the R1 gate).
**Fix (R1/R2):** add rules 6–8: strict-orthography gate; state/score consistency; `title` added to the exempt-field list.

### 2.11 API schema gaps (enumerated)
- **No response-level notice channel.** `disclaimer_key` (L321) and per-quote `message_key` (L335) exist; `no_quotes`, `refusal`, `extraction_degraded`, `transparency_notice`, `privacy_notice` are response-level behaviours with **no field**. `refusal` (mandated by SA §2.1 L63 and tested by SA L285) has no representation at all.
- **No `window_refs[]`.** §2.3 (L143) builds 2- and 3-verse window documents for cross-verse quotes, and §3.4 step b (L243) says the window is mapped back to “الآية **أو الآيات**” — but `matches[]` (L336–342) carries exactly one `ref`, one `source_text`, one `diff`. §2.2 (L124–134) has **no window record type**, so the window docs have no identity to map back from. §6.1 category A's own example (`فإن تابوا وأقاموا الصلاة وآتوا الزكاة فإخوانكم في الدين`, L400) is a single-verse substring of 9:11 (verified), so the window machinery is currently justified by nothing in the test file.
- **No basmala offset.** §2.1 L72 strips the basmala from the index only; §2.2 has no token→char map; §3.4 step c (L246) projects the diff onto the original. For the **112** basmala-bearing ayah-1 records the displayed text has **4 extra leading tokens** (verified: 112:1 index = `[قل, هو, الله, احد]`, displayed = `[بسم, الله, الرحمن, الرحيم, قل, هو, الله, احد]`). `diff[].source_range` (L341) is in token indices, so every highlight on those 112 verses is off by 4 unless the client knows. No field tells it.
- **Error codes are listed but not mapped.** L353 lists `400/413/422/429/503`; the error object (L301) has `{code, message_ar, message_en}` with no status field and no enum. `429` “مع `Retry-After`” has no field for it.
- **`503 degraded` is self-contradictory.** L353 says on 503 “تبقى المطابقة الحتمية تعمل على ما التقطه `rules.py`” — that is a **200** with `extraction_degraded=true`, not a 503. The same condition is specified as both.
- **Input bounds disagree across endpoints.** `/v1/ocr` accepts up to 4096 px (L357); a page image at that size easily exceeds `/v1/check`'s `1..5000` char bound (L316), so the user confirms a long OCR text and then gets `413 text_too_long` on the check that follows.
- **`score` (L334) is exposed raw.** A float next to a state invites a judge to read it as confidence; SA's language forbids implying judgment. Rename to `similarity` or drop from the public schema.
- **`grade.source` is a literal string** `"HadeethEnc"` (L342) while everything else is keyed for i18n.
- **`external_search_links` is per-quote** (L344) but a `no_quotes`/all-`not_found` response has no quote to hang it on.
- **`GET /health` (L304–309) reports only provider status** — not whether the corpus loaded, not the index document count, not RSS. M2's acceptance test is `curl /health` → 200 (L538), and M3's is “6,236 آية و62,169 حديثًا و3,582 سجل” loaded (L539). As specified, `/health` returns 200 **while the corpus is empty**, and the first judge to hit `/v1/check` gets a 500.

### 2.12 OCR flow: the named risk has no control
L373 correctly names the danger — the vision model completing a corrupted verse from memory. But the flow's only signal is `unreadable_marks` (L360), a count of `[؟]` markers the model itself chooses to emit. A model that **completes** rather than marks produces `unreadable_marks = 0` and a confident, correct-looking `ocr_text`; the corrupted input has been laundered into a `found`. §6.1 category L (L411) *measures* the rate; nothing *prevents* it, and the confirm step is client-asserted (§1.14). **Fix (R8):** return a signed token from `/v1/ocr` carrying a hash of the raw OCR text; `/v1/check` with `source_modality="image"` must present it, and the server rejects any image-modality check whose text differs from the token's text unless the client explicitly re-confirms. Also: re-encode images server-side (see §5.5).

### 2.13 `claimed_source_mismatch` asserts an unprovable negative
L279's template is “وُجد في [X]، **لا في [Y] المذكور**”. Proving absence from the claimed book requires a negative over 62,169 records, but §3.4 only sees the top-100 candidates from a truncated RRF list whose BM25 channel **drops terms appearing in >20% of documents** (L221). Absence from the top-100 is not absence from the corpus. §6.1 category I (L408) expects that exact string on three inputs. **Fix (R15):** restrict the flag to “not found in the claimed book among retrieved candidates” and reword the template to stop asserting absence.

### 2.14 Tie-break and position-collection interact badly
L230 collects **all** matching positions; L242 breaks ties by preferring the **shorter** document. For a quote matching both a single verse and a 2-verse window, the single verse wins silently — reasonable, but the document never says whether the window doc is then also reported. Combined with the absent `window_refs[]` (§2.11), the behaviour is undefined.

### 2.15 Rate limiting and CORS are configured against the wrong client identity
L472 uses `slowapi` “بعنوان IP”. On Render, TLS terminates upstream and the client address arrives via `X-Forwarded-For`; unless the limiter is configured to trust exactly one proxy hop, every request resolves to the proxy IP and the **global** 200/day is consumed collectively — the demo dies mid-judging. Compounding it: BS L302 restricts CORS to “نطاق Pages”, but Cloudflare Pages gives every preview deployment a distinct `<hash>.pages.dev` subdomain, so a preview or a renamed project breaks the live demo with an opaque CORS error. **Fix (R6/R16):** correct proxy-trust config, allow `https://*.pages.dev` + the production domain, send `Vary: Origin`, no credentials.

### 2.16 §7.3 prompt-injection handling is structurally right; the residual risk is compute, not correctness
L468–470 (positions only, no tools, schema-checked, deterministic state) plus the `rules.py` union (L213) genuinely bounds the correctness impact, and category J (L409) tests it. Two gaps: (a) `rules.py` is unbounded while the LLM is capped at 30 quotes, so a crafted input full of `قال تعالى …` produces an unbounded quote set (a compute DoS through the fuzzy stage); (b) the union means an injected instruction that gets the model to *mark* a benign sentence as a quote will cause that sentence to be matched against **both** corpora (L215) and can yield `found` for a sentence the user never meant as a quotation — harmless as a fact, but it looks wrong to a judge. **Fix (R5):** cap `rules.py` output, cap total span characters per request, and add a per-request candidate×length budget.

### 2.17 The calibration artifact is not reproducible
L16: the thresholds in §3.4 were produced by a temporary script run in the research environment on 30 September, “**السكربت ليس جزءًا من المستودع**”, and the developer must write everything from scratch. Every “قيمة مبدئية” in §3.4 (0.75 / 0.70, `k1=1.2`, `b=0.75`, the 20%/30% document-frequency cut-offs, `k=60`) is therefore inherited from an **unversioned, unpublishable artifact**. A judge who asks “how did you choose 0.75?” gets “a script we can't show you” — at exactly the point where §12 L568 forbids “أي رقم غير مقاس”. **Fix (R6b):** reimplement the calibration logic as text in `eval/PLAN.md` **before** Oct 4 (this is permitted — it is text, not code) and cite it as the provenance of each initial value.

---

## 3. Feasibility for a 72-hour solo build

### 3.1 What the schedule actually demands
| Milestone | Deadline | Requirement | Realistic risk |
|---|---|---|---|
| M3 (L539) | D1 14:00 | fetch + sha256 verify + build **3 indexes × 2 corpora** over ~99k docs (incl. 36,700 Quranic windows) | Embedding ~99k docs on 4 vCPU (est. 8–33 min) plus char-3gram construction at ~37M postings; serialization to npz; load-time measurement. **Tight but feasible** — and it is the only milestone that can be partly pre-staged before Oct 4 (text only). |
| M4 (L540) | D1 18:00 | exact + windowed fuzzy + diff + 4-state machine + post-validator + `rules.py`, passing categories A/B/E/H | The windowed fuzzy stage (§2.7) and the strict/loose problem (§2.1) land here. **Highest-risk milestone.** |
| M5 (L541) | D1 21:00 | two LLM providers with structured outputs + fallback + union with `rules.py` + full `/v1/check` + a 50-case run + the P1/P2 decision written to CHANGELOG | Two providers configured, prompted, schema-validated, timed out and failed over — in 3 hours after M4. |
| M8 (L544) | D2 20:00 | 150 cases + 500 FA + dev set + **threshold freeze** + `eval/REPORT.md` with CIs | Impossible inside §7.4's 200/day cap (§1.11), and it is the same evening as the PDF export (M6b). |
| M10–M12 (L547–549) | D3 16:00–22:30 | 3 runs, final docs, code freeze, 3 external demo runs, 2-min video, submission | 6.5 h for 3 full runs + video + freeze + 3 external runs. Thin. |

### 3.2 Build order I would actually use (highest value first)
1. **Corpus fetch + `manifest.json` + sha256** (M3). Non-negotiable; partly pre-staged as text.
2. **Normalization + dual (loose/strict) Quran index + exact match + diff + state machine + validator.** This *is* the product claim. Do not proceed until `annex_case_11_misquoted_ayah` passes on `إن الله علي كل شيء قدير`.
3. **Hadith exact match on OHD + HadeethEnc grade attach** (respecting the `link`-mode conflict, §1.8).
4. **`rules.py` + full `/v1/check` + frontend cards.** Ship this as **v0.9: a working, LLM-free product.** It is demo-able, judge-proof against provider outages, and satisfies M2/M3/M4 with room to spare.
5. LLM extraction behind the union (M5).
6. OCR (M7) — last, because it is the only stage whose failure mode is *silent corruption* (§2.12).
7. Eval harness (M8), then docs, video, submission.

### 3.3 Cut list, in order
1. **Vector channel** — zero measured recall contribution (L226), 150 MB, one licensing row, one model dependency. Cut first.
2. **Hadith char-3gram index** — the memory hog (§2.8). Keep it for Quran only.
3. **2-/3-verse window documents** — until `window_refs[]` exists (§2.11), they cannot be reported correctly. §6.1 contains no cross-verse case that requires them.
4. **500-FA set → 300 with published bounds** if M8 is at risk (300/0 errors → 1.22 % upper bound, still under the 2 % target; verified).
5. **M6b PDF export** — the only milestone that can be dropped without breaking a stated promise *if* the README is amended; dropping it silently breaks the Slide-10 promise.
6. **AR/EN → AR-first.** The strings are one file (SA L25/BS L56), so EN costs almost nothing; but EN *testing* costs a full pass. Ship EN untested and say so.
7. **`/v1/guard`** — already P2; keep it unannounced (L364).

**Do not cut:** the strict-orthography gate (R1). Without it the product's central promise — “الفرق مظلَّلًا” (L22) — is false for the most common Arabic error class, and the annex's mandatory case fails.

### 3.4 Two schedule holes
- **No milestone covers writing `known_claims.json`** (SA L118, text-only, permitted pre-Oct-4) or the 30 sealed cases (L416, text-only). Both are prerequisites of M8/M9 and neither appears in §9.
- **M11→M12 gives 2.5 h** for code freeze + 3 external demo runs + a 2-minute video + platform submission. The video alone (script, capture, edit, upload) is 1.5 h for a solo developer.

---

## 4. Testing and evaluation weaknesses

### 4.1 Category arithmetic is consistent; coverage is not
The 12 categories sum to exactly **150** (20+10+20+10+20+15+10+15+10+10+5+5) — verified. But the set contains **no boundary cases**: nothing at `sim = 0.749 / 0.751` (hadith partial/review) or `0.699 / 0.701` (review/not_found), even though §3.4's values are explicitly “قيم مبدئية” to be re-tuned on Oct 4 (L261). The most likely thing to change is the least covered. **Fix (R12):** add ~12 boundary cases at ±0.002 around each threshold.

### 4.2 The three-run protocol measures less than it appears to
L444: the deterministic part must produce **byte-identical** output “**لنفس مخرج الاستخراج**”. Therefore the only variance three runs can exhibit is LLM extraction variance. L443 publishes “المتوسط والمدى لكل مقياس” next to state-accuracy figures, implying a total-variance estimate it cannot be. Three runs yield a range, not an interval — inconsistent with §6.3's correct use of Wilson (L437). **Fix:** label the range “extraction variance only”, and report the deterministic stage's variance as exactly zero (by the test at L444).

### 4.3 The false-alarm set is not an independent estimate
L420–423 draws 250 Quranic segments (125 simple / 125 Uthmani) and 250 hadith segments of 5–20 words, half crossing verse boundaries — the **same generator family** as the calibration sample (L226: “125 قرآنية و150 حديثية، عيّنة عشوائية بين 5 و20 كلمة”). It is a re-draw from the same distribution, not an independent hold-out. It also omits: quotes shorter than 5 tokens (which have their own threshold row, L255), windows beyond 2 verses, diacritised hadith, and the `U+200F` RLM case that BS L97 warns about. L427 declares the first two limits honestly; it does not declare the distributional dependence.

### 4.4 The statistics are correct — attach them to the right things
Recomputed with SciPy (Clopper-Pearson, two-sided 95 %, upper bound; n = 500):

| errors | upper bound | spec (L425) | match |
|---|---|---|---|
| 0 | 0.735 % | 0.74 % | ✔ |
| 3 | 1.743 % | 1.74 % | ✔ |
| 5 | 2.318 % | 2.32 % | ✔ |
| 10 | 3.647 % | 3.65 % | ✔ |

“≤ 2 % requires ≤ 3 errors”: 3/500 → 1.743 % **pass**, 4/500 → 2.036 % **fail** — correct (L425). Wilson for 0.90 on 150 → **[84.2 %, 93.8 %]** — matches L437 exactly. **The statistics are sound; the defect is scope.** §6.3 L431 requires “دقة كل فئة”, but per-category n is 5–20: a 19/20 category has a Wilson interval of roughly ±17 points, and a 4/5 category spans ~30–100 %. §6.3 does not restrict interval reporting to the pooled numbers. **Fix:** report intervals only for n ≥ 100; mark everything else “n < 30 — indicative only”.

### 4.5 The headline metric is degenerate
L432 defines the positive class as “كل اقتباس حالته المتوقعة **غير** FOUND”. Since `needs_review` is the catch-all for every technical failure (§1.13), a system that returns `needs_review` for **everything** scores 100 % recall on this metric. §6.3's 4×4 matrix (L431) does contain the counter-evidence, but the F1 will be quoted first. **Fix:** state the degenerate baseline explicitly and lead with `found`-precision on categories A/B/E.

### 4.6 The IslamicEval anchor is handled honestly, but has no mapping
L447–453 correctly refuses the dev-vs-test comparison and even supplies the permitted phrasing (L451). Two holes: (a) there is **no mapping** between IslamicEval's 1A/1B tasks (span detection, judgement) and Basira's 4-state decision, so even the dev number is not comparable without a stated correspondence; (b) L112 reports **798 annotations over 150 questions** with `NoAnnotation 16`, so “150” and “798” are different denominators and §6.3 never says which one an accuracy figure uses. **Fix:** publish the mapping table and the denominator before M8.

### 4.7 CI makes the eval self-defeating
L445 runs the 150 cases on every push with a **cached** extraction. (a) The cache key is unspecified — and per SA L190 a reversible hash of short text is prohibited. (b) Caching means CI never re-tests extraction, so a silent provider model change passes CI green. (c) “يفشل البناء إذا سقطت حالة كانت تنجح” requires a stored per-case baseline; the repo tree (L510) lists `eval/results/` but no baseline artifact. **Fix (R18):** HMAC the cache key with a repo secret; store `eval/results/baseline.json`; add a provider/model-version assertion to CI.

### 4.8 The one property test that would have caught the worst bug is missing
A single property test — *“every `found` has a non-empty diff OR the quote is byte-equal to the matched source segment under **strict** comparison”* — fails immediately on `إن الله علي كل شيء قدير` (§2.1). §6.3 (L429–438) specifies no such invariant. **Fix (R1b, 2 h, highest ROI in the whole plan).**

### 4.9 The sealed set seals against the wrong window
See §1.18. Also: L416 does not state the **category composition** of the 30 sealed cases. If they are drawn proportionally, the published accuracy mixes tuned and untuned items with no way to separate them. **Fix:** publish the composition and report open/sealed separately.

### 4.10 No negative control for the LLM's absence
The spec's own insurance is `rules.py` + `extraction_degraded` (L175, L213), and category J (L409) tests injection — but nothing in §6.1 tests the **degraded** path (both providers down) end-to-end. Given that M5's whole point is provider failover, that is the most likely real-world failure and it is untested. **Fix:** add 3 cases with both providers stubbed to timeout, asserting `extraction_degraded=true` and non-empty `quotes[]` from `rules.py`.

---

## 5. Security and privacy gaps

### 5.1 Prompt injection — bounded, with a compute hole
Structurally correct (L468–470; L213). Residual: `rules.py` is unbounded (the LLM is capped at `maxItems: 30`, L186), so a crafted input can generate an unbounded quote set that each traverses the fuzzy stage over 100 candidates — a compute DoS that shows up as a timeout in front of a judge. **Fix (R5):** cap `rules.py` output, total span characters, and per-request candidate×length budget; return a degraded state past the budget.

### 5.2 `claimed_source_span` parsing
L205 parses `claimed_source_span` deterministically against a book/surah dictionary — correct — but the span can sit **inside** a quoted matn (e.g. a hadith whose text mentions “رواه البخاري”), producing a spurious claim and a spurious `claimed_source_mismatch`. **Fix:** exclude spans that fall inside another quote's span.

### 5.3 PII: warned, not controlled
SA L183 (quoting the terms) prohibits uploading real beneficiary data to external AI services; SA L199 discloses the transfer; SA L184–186 mandates synthetic demo data. There is **no detection or blocking**. A user pasting a phone number has it sent to the provider. A cheap regex/normalisation pre-scan (Saudi mobile/IBAN/national-ID patterns + email) with a hard block and a template would be both defensible and demonstrable. **Fix (R9, 4 h).**

### 5.4 Image path is the strongest concrete leak
`/v1/ocr` accepts up to 5 MB of `png|jpg|webp` (L357) with no magic-byte validation and no re-encode. Photos carry **EXIF GPS and device identifiers**, which would be transmitted to the vision provider while the UI promises “لا تُدخل بيانات شخصية” (SA L65) and BS L375 promises the image is never persisted. **Fix (R7, 2 h):** validate magic bytes, re-encode through Pillow to strip all metadata, downscale to the model's max input, and discard the original buffer. This is the highest-value privacy fix in the document.

### 5.5 Secrets and licensing as release blockers
`gitleaks` in pre-commit and CI (L479), env-only keys (L478), no key in the frontend (L480) — good. Gaps: no key-rotation note; nothing prevents the eval scripts (run locally with real keys) from being committed with a key in a `.env`; and **BS L518 leaves `LICENSE` as an open decision by `manus.date11`** while the submission requires a **public** GitHub repo. With ODbL-derived content in the pipeline (§1.9), an unresolved licence is a release blocker, not a footnote.

### 5.6 Rate limiting is the most likely operational failure
See §2.15. Two additional consequences: the daily spend cap (L476) silently degrades to `rules.py`-only, which to a judge looks like the product is broken — and the degraded state has no `message_key` (§2.11). And there is no per-IP token budget, so one abuser exhausts the global cap for everyone.

### 5.7 Logging is compliant in the app, undocumented at the platform
L463 lists exactly the right fields and L461 blocks body logging. But Render's platform access logs (path, status, duration, and the query string if any) are outside the application's control and outside the “لا نحفظ” promise the UI makes (SA L65). **Fix (R19, 1 h):** state in `SAFETY.md` that platform-level access logs contain no request body, and never place user text in a URL.

### 5.8 No CSRF/auth concern, but also no abuse ceiling
There are no cookies and no accounts, so CSRF is not applicable. The flip side is that the only cost control is the global daily cap (L476) — a single scripted client can end the demo. **Fix:** per-IP token budget rather than a global one.

---

## 6. Recommendations, ranked by impact (effort in engineer-hours)

| # | Recommendation | Effort | Why it's ranked here |
|---|---|---|---|
| **R1** | **Dual-orthography matching**: loose normalization for retrieval, **strict** re-verification before any `found`; keep a strict index. Add the property test “`found` ⇒ strict byte-equal segment”. | **8 h** | Fixes the highest-frequency false `found` (§2.1) and the annex's mandatory misquote case. Without it the product's core promise is false. |
| **R2** | **Split `needs_review`** into a machine-readable `reason` (`near_miss` / `stage_failure` / `short_quote` / `validator_reject` / `non_arabic`) and split the metric accordingly. | **4 h** | Un-degenerates the headline F1 (§4.5) and makes the 4×4 matrix diagnostic (§1.13). |
| **R3** | **Exact matching off the full inverted index**, not the truncated RRF top-100; RRF for the fuzzy fallback only. | **4 h** | Removes a documented path where the correct candidate is dropped (§2.5). Measured cost of full exact scan: <1 s for 6 quotes. |
| **R4** | **Bound the fuzzy stage**: banded Levenshtein (max-distance automaton) + char-3gram Jaccard pruning + per-request compute budget. | **3 h** | The only unbounded O(n²×candidates) stage; §6.3 requires p95 latency (§2.7). |
| **R5** | **Schema completion**: response-level `notice_keys[]`, `source_modality`, `window_refs[]`, basmala `token_offset`, `Retry-After`, HTTP-status↔`error.code` map, `similarity` instead of `score`, `collection_tier`, `found_other_book`/`transparency_notice` keys. | **3 h** | Five mandated behaviours currently have no wire representation (§2.11, §1.5). |
| **R6** | **Rate-limiter client-IP correctness** (exact proxy trust) + demo allowlist + per-IP token budget; smoke-test from two networks before M2. | **2 h** | Single most likely cause of a mid-demo failure (§2.15). |
| **R7** | **Image hygiene**: magic-byte validation, Pillow re-encode, EXIF strip, downscale, discard original. | **2 h** | Closes the only concrete PII leak to a third party (§5.4). |
| **R6b** | **Publish the calibration logic as text** in `eval/PLAN.md` before Oct 4, and cite it as the provenance of every “قيمة مبدئية”. | **1 h** | Removes an unversioned artifact from the scientific record (§2.17) at the exact point the spec claims rigor. |
| **R8** | **Bind `/v1/ocr` → `/v1/check`** with a signed token carrying the raw OCR-text hash; reject unconfirmed image-modality checks. | **4 h** | Makes the “user confirmed” invariant (L278) and `source_modality` non-forgeable (§1.14). |
| **R9** | **PII pre-scan with hard block** + a template for the block. | **4 h** | Converts a warning into a control (§5.3). |
| **R10** | **Resolve the i18n single-source contradiction**: canonical `backend/app/messages/`, generate the frontend copy at build, repoint SA L25. | **2 h** | Otherwise the forbidden-word test can pass while the UI ships stale strings (§1.1). |
| **R11** | **Amend SAFETY**: add `found_other_book` + `transparency_notice` to §1.1/§1.2; correct §10's annex status; add `title` to the exempt-field list. | **3 h** | Two mandated templates currently have no authoritative text (§1.5, §1.6, §2.10). |
| **R12** | **Boundary cases** at 0.699/0.701 and 0.749/0.751; per-category n-awareness in §6.3. | **2 h** | The values are explicitly provisional (L261) and untested at the boundary (§4.1). |
| **R13** | **Memory**: numpy postings + offsets, or drop hadith char-3grams; re-measure RSS against the Render plan at M3. | **6 h** | L148's <1 GB estimate omits the largest structure (~2.2 GB) (§2.8). |
| **R14** | **Drop the vector channel from P0.** | **0 h** (cut) | No measured recall contribution; 150 MB + a licensing row (§2.9). |
| **R15** | **Restrict `claimed_source_mismatch`** to the retrieved candidate set; reword the template to stop asserting absence. | **2 h** | Currently an unprovable negative in user-facing text (§2.13). |
| **R16** | **CORS**: allow `*.pages.dev` + production, `Vary: Origin`, no credentials. | **1 h** | Preview subdomains break the live demo (§2.15). |
| **R17** | **Reconcile SA L224** with BS L150 (embedding-model row). | **1 h** | The compliance file currently certifies a dependency that isn't used (§1.17). |
| **R18** | **CI**: per-case baseline file, HMAC cache key, provider/model-version assertion. | **2 h** | Otherwise CI is green while extraction silently changes (§4.7). |
| **R19** | **Document platform-log behaviour** in `SAFETY.md`. | **1 h** | The UI's “لا نحفظ” must be defensible at the platform layer too (§5.7). |
| **R20** | **`matched_alternative_narration` notice**: never a clean `found` with an empty diff when the strict form differs. | **2 h** | Closes the documented misquote-as-`found` path (§2.6). |
| **R21** | **Minimum quote length** (≥3 tokens hadith / ≥2 Quran) + hard cap on positions returned. | **2 h** | Removes the one-word-quote flood (2,023 verses for `من`) (§2.4). |
| **R22** | **`/health` must report corpus state**: `corpus.loaded`, `index_docs`, `rss_mb`, `build_sha`. | **2 h** | M2's acceptance test currently passes with an empty corpus (§2.11). |
| **R23** | **Demo-script resequencing**: lead with uncontested sahih material (Bukhari 1, Muslim 82); use the contested cases (`طلب العلم فريضة…` → OHD Ibn-Maja 220) explicitly as the “we report location, we do not grade” teaching moment, with the `found_other_book` → Dorar link on screen. | **3 h** | Highest-value change for judging: the strongest demo cases currently rest on hadiths whose grading is contested, presented as `found` (§2.6, §1.8). |

**Total for R1–R12 (the blocking set): ~41 h.** That is more than the deterministic half of the 72 h window. **R1, R2, R3, R6, R6b, R7, R21, R22 (~24 h) are the irreducible minimum**; everything else should be sequenced after v0.9 (LLM-free) is demo-able.

---

## 7. What is genuinely right (recorded for the record, not as praise)

So the audit is usable as a change list rather than a takedown:
- **Statistics**: every Clopper-Pearson and Wilson figure in §6.2/§6.3 recomputes exactly (table in §4.4). The dev-vs-test refusal (L450–451) is methodologically correct and rare.
- **Corpus provenance**: the Tanzil sha256 values in L75–76 **match the live files byte-for-byte**, the 6,236-verse count and the 112-surah basmala claim are exactly right, and the 3,985/6,236 two-script divergence figure reproduces to the digit (63.9 %). This is verified data, not assertion.
- **Anti-hallucination architecture**: “the LLM returns spans only” (L177, L210), “the quote is `input[span_start:span_end]`” (L210), deterministic state (L24), the `rules.py` union as injection insurance (L213) — this is the correct shape, and it is why the injection category is testable at all.
- **Grade policy**: the verbatim-and-attributed-only rule (L280, SA L109) plus the explicit “no weak/fabricated from us” prohibition (L558, SA L83) plus the automated forbidden-word test (SA L281) is the right way to avoid the integrity failure the brief worried about. The residual risk is over-affirmation (§0), not over-condemnation.
