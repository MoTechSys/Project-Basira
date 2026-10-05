# English gate — data + retrieval layer (feat/english-gate)

**Status:** data layer and retriever shipped and measured (2026-10-03). **Not** wired into the pipeline, the
API or the UI — by design of the work order. No LLM is involved anywhere in this layer.

## 1. What it does

Input: an English quotation, e.g. *«There is no compulsion in religion»* or *«None of you truly believes
until he loves for his brother what he loves for himself»*.
Output: `candidates(text, k=5) -> list[Candidate]`, each `Candidate = (kind: "quran"|"hadith",
ref: "2:256" | HadeethEnc id, source_key, score, translation_text)` — a short, deterministic list of
*possible* sources drawn from approved English translations. A later stage (a language model under the
existing provider layer, or a human) picks one or rejects them all. This layer **never decides**.

What it is not: not a verdict, not a grade, not generated text. `translation_text` is the upstream string
byte-for-byte (tested), and a `not in top-k` is «our translations do not contain a close sentence», not a
statement about the quotation.

## 2. Sources (organizer's scientific package only)

| item | API | version (upstream) | records | sha256 (pinned in `corpus/manifest.json["translations"]`) |
|---|---|---|---|---|
| `quranenc_english_saheeh` (priority 1) | `https://quranenc.com/api/v1/translation/sura/english_saheeh/{sura}` | 1.1.2 (2025-06-24) — Noor International | 6 236 ayat | `6792bcbe…0776` |
| `quranenc_english_rwwad` (priority 2) | `…/translation/sura/english_rwwad/{sura}` | 1.0.19 (2026-03-12) — Rowwad | 6 236 ayat | `1212a876…e80b` |
| `hadeethenc_en` | `https://hadeethenc.com/api/v1/hadeeths/one/?language=en&id={id}` | v1.25.0 (2026-05-10, from the bulk EN workbook header; the API has no version field) | **2 328 of 3 582** ids | `3b51594a…d0ce` |

* Ids for HadeethEnc are exactly the ids already in our Arabic corpus (`corpus/manifest.json` →
  `hadeethenc_ar`). **1 254 ids (35 %) have no English translation** — the API returns 404 for them; the
  bulk EN workbook confirms the same 2 328-id set (0 ids in the workbook that the API lacks, 0 the other
  way). The list is written to `corpus/data/translations/hadeethenc_en.missing.json` so the gap is explicit.
* Licence terms are stored verbatim in the manifest: HadeethEnc API docs — «No modification … Clearly
  referring to the publisher and the source»; QuranEnc — «free and trustworthy translations … accessible
  and shareable» (About page; there is no separate licence page — `/en/home/terms|copyright|license` all
  404 on 2026-10-03). Translation copyright stays with the issuing bodies named in `title`.
* Nothing is modified. Footnote markers like `[104]` stay in the stored text and are removed only at
  tokenisation. Translation files are git-ignored (`corpus/data/`); only hashes and counts are committed.
* Byte-determinism of the fetch: two independent downloads produced identical sha256 for all three files.

Commands:
```bash
python3 corpus/fetch_translations.py            # ~40 s: 228 QuranEnc calls (4 workers) + 3582 HadeethEnc calls (8 workers)
python3 corpus/fetch_translations.py --verify   # offline check against the pins
python3 corpus/fetch_translations.py --repin    # accept an upstream change consciously
backend/.venv/bin/python corpus/build_index.py  # existing build + new step → corpus/index/translations.pkl (2.4 s, 15 MB)
```
`build_index.py` refuses to index a translation file whose sha256 differs from the manifest pin.
`meta.json["translations"]` records the pkl sha256 (`706ce482…` — reproduced identically on two builds)
and the source hashes it was built from. If `corpus/data/translations/` is absent the step prints a
message and is skipped; the Arabic product does not depend on it.

## 3. How retrieval works (`backend/app/retrieve/translations.py`)

1. **Documents** — one per (translation key, ayah) → 12 472 Quran docs; one per hadith with English
   text → 2 328 docs (index text = HadeethEnc `title` + `hadeeth`; **returned** text = `hadeeth` only).
   Footnote bodies are commentary and are not indexed.
2. **Normalisation** `normalize_en` (identical for documents and queries): strip `[n]` footnote markers →
   NFKD and drop combining marks (`Allāh`→`allah`, `ṭāghūt`→`taghut`) → casefold → drop apostrophes
   inside words (`Qur’an`→`quran`) → split on non-alphanumerics → Harman S-stemmer (conservative plural
   stripping, no dictionary). No stop-word list: BM25's idf already pushes `the/and/of` to ≈0.
3. **Scoring** — two BM25 channels (k1 = 1.2, b = 0.75): unigrams and word bigrams. Each channel is divided
   by the query's own idf mass, so a score ≈1.0 reads as «every query term present once in an
   average-length document». Fused score = 0.8·unigram + 0.2·bigram. The weight was **measured**, not
   guessed (`eval/run_english.py --sweep`, all 30 cases, k = 5):

   | w (bigram) | recall@5 | MRR | highest negative top-1 | lowest positive top-1 |
   |---|---|---|---|---|
   | 0.0 | 0.957 | 0.902 | 0.540 | 0.488 |
   | 0.1 | 0.957 | 0.924 | 0.502 | 0.493 |
   | **0.2** | **0.957** | **0.924** | **0.465** | **0.497** |
   | 0.3 | 0.957 | 0.924 | 0.543 | 0.501 |
   | 0.5 | 0.957 | 0.889 | 0.754 | 0.510 |
   | ≥0.6 | 0.913 | 0.880 | 0.859–1.281 | 0.515–0.532 |

   0.2 is the only setting where every positive top-1 beats every negative top-1 with recall and MRR at
   their maximum. (Eval-set tuned, n = 30 — labelled «قيمة مبدئية»; re-measure when the set grows.)
4. **Candidates** — one slot per (kind, ref): the best-scoring translation of an ayah represents it, ties
   broken by translation priority (saheeh before rwwad). Total order = (score rounded to 6 dp, kind, natural
   ref order, priority, doc id) → **the same input always yields the same list in the same order** (tested:
   25 repeats + a fresh load from disk; `run_english.py` asserts 3 repeats byte-identical).
   Top-k is taken from an `argpartition` pool that includes every tie; proven equal to a full sort on all
   queries tried. Cost: **0.9 ms median / 1.6 ms max per query**, index load 0.10 s, 15 MB on disk.
5. Nothing random, no time, no network, no model. `translation_text` is tested byte-equal to the pickle.

## 4. Measured numbers (`backend/.venv/bin/python eval/run_english.py`, full index, 3 repeats, k = 5)

```
recall@5 = 0.9565  (22/23 positives; Wilson 95 % 0.790–0.992 — n < 30, indicative)
MRR      = 0.9239
negatives: 7/7 below the ceiling; highest negative top-1 = 0.4654, lowest positive top-1 = 0.4972
by category: EQ 8/8 (indexed wording) · EP 5/5 (popular wordings NOT in our index) · EH 9/10 · EN 7/7
latency: p50 0.89 ms, max 1.64 ms · repeats identical: true
```
Per-case ranks/scores: `eval/results/english_latest.json` (git-ignored, regenerated by the command).
`backend/tests/test_translations.py` pins the 12 required cases (6 ayat, 3 hadith, 3 negatives) to these
measured scores with a margin (±0.15 / ±0.10) so a regression fails but a minor upstream revision does not.

**The one miss — EH-015 «Actions are judged by intentions».** HadeethEnc's English has «the reward of deeds
depends on the intentions» (ids 4560/66511): the popular wording shares only *intention* with the
translation after stemming (`action≠deed`, `judged≠depends`). Rank at k = 10 is still absent; «Deeds are
judged by intentions» ranks 4, «The reward of deeds depends on intentions» ranks 1 (score 1.016). This is
a vocabulary gap, not a ranking bug — see §6.

**Why the 2:286 case ranks 4, not 1.** The popular «does not burden a soul beyond that it can bear» is
closer to Rowwad's 23:62 «We do not burden a soul more than what it can bear» than to either 2:286
rendering («does not charge a soul except with that within its capacity» / «does not burden any soul
greater than it can bear»). All four top candidates are genuine «لا يكلف الله نفسًا» ayat; the picker
stage has what it needs.

## 5. Limits (stated, not hidden)

* **Coverage.** Two Quran translations only; 65 % of HadeethEnc ids have English. A quotation from
  Yusuf Ali, Pickthall, Hilali-Khan, Sahih International or from a hadith outside HadeethEnc's English set
  may rank low or be absent. The EP category shows popular non-indexed wordings still retrieve well when
  the content words survive (5/5), and fail when they do not (EH-015).
* **Retrieval, not verification.** A score is lexical overlap, not faithfulness; a high score for a
  *mis*quoted ayah is expected and desirable (it gives the next stage the right text to compare against).
  The four states (`found` …) are **not** produced here and must not be inferred from a score.
* **No cross-reference to the Arabic record yet.** `ref` is sufficient to look the record up
  (`tanzil s:a` / `hadeethenc id`), but this layer does not do it.
* **Scores are relative to this index.** Changing sources, weights or the stemmer changes the scale;
  the tests and docs must be re-measured together (the index pickle carries `bigram_weight` and the test
  asserts it equals the code constant, so a stale pickle fails loudly).
* **Eval set size.** 30 cases, 23 positives: numbers are indicative; the Wilson interval is wide.

## 6. Not solved / next

1. **Synonym gap for popular hadith wordings** (EH-015). Options in order of principle: (a) add more
   *approved* English hadith sources if the organizer's package allows; (b) index HadeethEnc `explanation`
   as a *separate, lower-weight* channel (it often paraphrases with common verbs) — must remain clearly
   non-text; (c) a tiny curated synonym map (`deed↔action`, `judged↔depends`) — deterministic but hand-made,
   needs a DECISIONS row. No embeddings (ADR-002 §7, non-deterministic).
2. **Wiring**: a `needs_review_non_arabic` quote (I7) could carry `english_candidates` for the UI/LLM picker.
   Touches `pipeline.py` / `schemas.py` — out of scope here, owned by another engineer.
3. **Picker stage** (LLM under the provider layer, or rule «top-1 ≥ 0.9 and gap ≥ 0.3»): to be designed;
   the low-score ceiling 0.60 and the 0.4654/0.4972 separation are the measured starting point.
4. **Grow `eval/english_cases.yaml`** to ≥ 100 (more EP wordings, more hadith, 30+ negatives) so the
   intervals mean something; add a false-alarm run over verbatim translation sentences wrapped in prose.
5. HadeethEnc EN **attribution/grade** fields are fetched (`attribution`, `grade`) and stored but not
   exposed by `Candidate` — exposing them is a product decision (Q2 `link` mode applies).

## 7. Re-test in one command

```bash
python3 corpus/fetch_translations.py --verify && backend/.venv/bin/python corpus/build_index.py >/dev/null && \
cd backend && .venv/bin/pytest -q tests/test_translations.py && cd .. && backend/.venv/bin/python eval/run_english.py --fail-under 0.9
```

## 7. Wired into the pipeline — picker results (E-048, 2026-10-03)

`backend/app/english_gate.py` runs for every quote with `language == "en"` (I7 keeps the verdict
`needs_review/non_arabic`): candidates → cross-reference to the byte-exact Arabic record (a candidate
without a record is dropped) → **picker** marks at most one `selected`:

* **rule** (deterministic, offline): top-1 ≥ 0.9 and gap to top-2 ≥ 0.3;
* **model** (optional, `LLM_PROVIDER=openai-compatible`): when the rule abstains, the model answers
  `{"pick": k}` constrained to the candidate list or `0` to refuse — it can never introduce text
  (`parse_pick`; `backend/tests/test_english_gate.py`, 17 tests).

Measured with `eval/run_english_picker.py` on the 30 cases, 2 repeats each, temperature 0,
`response_format=json_object`, endpoint host `www.genspark.ai` (model ids exactly as the API lists them):

| arm | selected correct | abstained | selected WRONG | false select on negatives | unstable across repeats | wall |
|---|---|---|---|---|---|---|
| `rule-only` | 11/23 | 12 | **0** | **0**/7 | 0 | 0.1 s |
| `gpt-5.4` | 21/23 | 2 | **0** | **0**/7 | 0 | 76.9 s |
| `claude-sonnet-5-5` | 22/23 | 1 | **0** | **0**/7 | 1 | 65.8 s |
| `claude-opus-5-5` | 22/23 | 1 | **0** | **0**/7 | 0 | 106.7 s |

Reading: the deterministic rule alone resolves about half of the positives and **never** selects a
wrong passage; adding a model roughly doubles the resolved cases while the constraint keeps *wrong =
0* and *negatives = 0* for all three models. The one instability (`claude-sonnet-5-5`, EQ-012) flipped
between two accepted twins of the same sentence (29:57 / 21:35) — both correct. Raw rows:
`eval/results/english_picker.json` (git-ignored; regenerate with `make eval-english-picker
PICKER_MODELS="gpt-5.4 claude-sonnet-5-5"`).

What the UI gets per English quote: `english_candidates[]` (ref, labels, verbatim Arabic for Quran —
HadeethEnc stays link-only per Q2 — verbatim translation, source key, score, `selected`) and
`picker ∈ {rule, model, none}` so the screen can say *how* the choice was made.
