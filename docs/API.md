# Basira API — developer guide (REST)

Base URL in development: `http://localhost:8000`. OpenAPI: `GET /openapi.json`, Swagger UI: `GET /docs`.
Every number and every output below was produced by the command shown, on 2026-10-03, against the full
corpus with the mock extraction provider (`LLM_PROVIDER=mock`), server started with
`BASIRA_MCP=1 BASIRA_EVAL_KEY=dev-key uvicorn app.main:app --port 8000`
(`/health`: boot `snapshot` 1.78 s, RSS 315 MB, index `54892a95fbb0…`).

## 1. Endpoints

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/health` | readiness, corpus versions, index sha, boot mode | **503** until the index is loaded |
| POST | `/v1/check` | locate + verify every quotation in `text` (≤ 5 000 chars) | header `X-Basira-Determinism-Hash` |
| POST | `/v1/check/image` | OCR then the same check; `ocr_text` echoed; never `found` (SAFETY §1.5) | multipart `image` ≤ 6 MB |
| POST | `/v1/guard` | chatbot answer → `clear` / `flagged` / `no_quotes` + fixed summaries | docs/GUARD.md; same header |
| GET | `/v1/sources` | corpora: id, version/commit, licence, pinned sha256, live record counts | straight from `corpus/manifest.json` |
| GET | `/v1/rules?ui_lang=ar\|en` | grounding rules (the four states, red lines) for models | same text as the MCP `grounding_rules` tool |
| GET | `/v1/messages/{ar\|en}` | every user-facing string (single source of truth) | |
| POST | `/v1/receipt` | stateless **verification receipt**: verdicts + `token` (= the input, compressed) | §3.8; same header; nothing stored |
| GET | `/v/{token}?h=<hash>` | re-run a receipt in full → `verified_now` / `stale` | §3.8; JSON only; `Cache-Control: no-store` |
| — | `/mcp` | MCP server (6 tools) when `BASIRA_MCP=1`; plain 404 otherwise | docs/INTEGRATIONS.md §3.1 |

Guards on every `/v1/*` route: CORS allow-list (`BASIRA_CORS_ORIGINS`), security headers + CSP, `Cache-Control: no-store`,
rate limit **30 requests / minute per client IP** (`BASIRA_RATE_LIMIT_PER_MIN`) with an `X-Eval-Key` bypass for
benchmarks (`BASIRA_EVAL_KEY`), error envelope `{"error":{"code","message_ar","message_en"}}`.
**Nothing is stored**: no request body, no user text, no result is written anywhere (ADR-004); access logs carry
method/path/status only.

## 2. The four states (and the only meanings they carry)

| `status` | meaning | Quran | Hadith |
|---|---|---|---|
| `found` | strict byte-level match with a source record; `source_text` is that record verbatim | ✓ | ✓ |
| `partial_match` | overlaps a record with differences (possible transmission variant) | **never** | ✓ |
| `needs_review` | differs from the closest record, or could not be verified (`review_reason`: `orthographic_difference`, `diacritic_difference`, `foreign_material`, `non_arabic`, `image_unconfirmed`, `short_quote`, …) | ✓ (any difference lands here) | ✓ |
| `not_found` | nothing close enough **in our sources** — not a verdict on the text | ✓ (no candidates shown) | ✓ (search links only) |

`claimed_source_mismatch: true` means the reference the author wrote («رواه مسلم», «[البقرة: 255]») does not match where the
text was found. The status is unaffected (invariant I8). Basira never grades; a `grade` object, when present, is HadeethEnc's
own line, verbatim and attributed.

## 3. Examples — real requests, real outputs

### 3.1 `found` + the determinism header
```
$ curl -s -D - localhost:8000/v1/check -H "Content-Type: application/json" -d '{"text":"قال تعالى: ﴿إن الله مع الصابرين﴾","ui_lang":"ar"}' | sed -n "1p;/determinism/Ip"
HTTP/1.1 200 OK
x-basira-determinism-hash: 5785aa4af67b8d21cdafa04ca833bdf2cfd8d07f4a254f24e15d4bd8b842e78b

$ ... | jq "{status: .quotes[0].status, ref: .quotes[0].matches[0].ref, label: .quotes[0].matches[0].ref_label_en, notice_keys: .quotes[0].notice_keys, determinism_hash}"
{
  "status": "found",
  "ref": {
    "surah": 2,
    "ayah": 153
  },
  "label": "Surah Al-Baqarah (2:153)",
  "notice_keys": [
    "quran_fragment"
  ],
  "determinism_hash": "5785aa4af67b8d21cdafa04ca833bdf2cfd8d07f4a254f24e15d4bd8b842e78b"
}
```
(`quran_fragment`: the quote is part of the ayah, not the whole ayah — a fact, not a fault; status stays `found`, E-026.)

### 3.2 `partial_match` (hadith, one word added)
```
$ curl -s localhost:8000/v1/check -H "Content-Type: application/json" -d '{"text":"قال ﷺ: «طلب العلم فريضة على كل مسلم ومسلمة»"}' | jq "{status: .quotes[0].status, ref: .quotes[0].matches[0].ref, diff_kinds: .quotes[0].matches[0].diff_kinds, score: .quotes[0].matches[0].score}"
{
  "status": "partial_match",
  "ref": {
    "book": "sunan_ibn-maja",
    "num": 220,
    "numbering": "ohd"
  },
  "diff_kinds": [
    "word_added_in_quote"
  ],
  "score": 0.8571
}
```

### 3.3 `needs_review` (Quran, one letter: «علي» for «على»)
```
$ curl -s localhost:8000/v1/check -H "Content-Type: application/json" -d '{"text":"قال تعالى: ﴿إن الله علي كل شيء قدير﴾"}' | jq "{status: .quotes[0].status, review_reason: .quotes[0].review_reason, message_key: .quotes[0].message_key, diff_kinds: .quotes[0].matches[0].diff_kinds}"
{
  "status": "needs_review",
  "review_reason": "orthographic_difference",
  "message_key": "needs_review_quran",
  "diff_kinds": [
    "word_replaced"
  ]
}
```

### 3.4 `not_found`
```
$ curl -s localhost:8000/v1/check -H "Content-Type: application/json" -d '{"text":"قال ﷺ: «الدين المعاملة»"}' | jq "{status: .quotes[0].status, matches: (.quotes[0].matches|length), links: [.quotes[0].external_search_links[].name]}"
{
  "status": "not_found",
  "matches": 0,
  "links": [
    "ابحث في الدرر السنية",
    "ابحث في المكتبة الشاملة"
  ]
}
```

The same four pairs (full bodies, `source_text` verbatim) are embedded in the OpenAPI schema as `examples` of
`CheckRequest` / `CheckResponse` (`backend/app/openapi_examples.json`, captured from the full corpus).

### 3.5 `/v1/guard`
```
$ curl -s localhost:8000/v1/guard -H "Content-Type: application/json" -d '{"answer":"قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «طلب العلم فريضة على كل مسلم ومسلمة»","ui_lang":"ar"}' | jq "del(.quotes)"
{
  "verdict": "flagged",
  "counts": {
    "quotes": 2,
    "found": 1,
    "flagged": 1,
    "by_status": {
      "found": 1,
      "partial_match": 1
    }
  },
  "flagged_quote_ids": [
    "q2"
  ],
  "flags": {
    "chain_message": false,
    "refusal": false,
    "pii_suspected": false
  },
  "extraction_degraded": false,
  "summary_ar": "في الإجابة اقتباسان؛ واحد منها يحتاج مراجعة قبل النشر (لم يُوجد مطابقًا في مصادر بصيرة أو يختلف عن النص المصدر). بصيرة أداة مساعدة حتمية؛ «لم يوجد في مصادرنا» ليس حكمًا على النص. راجع أهل العلم عند الشك.",
  "summary_en": "The answer contains 2 quotation(s); 1 of them need review before publishing (not found verbatim in Basira's sources, or differing from the source text). Basira is a deterministic aid; \"not found in our sources\" is not a verdict on the text. Consult qualified scholars when in doubt.",
  "determinism_hash": "e8bb60f86941daa614b42f601ad52388943dd4104ea6f84ef8ca714b2321ae0a",
  "corpus": {
    "tanzil": "1.1",
    "ohd_commit": "1515f6cb",
    "hadeethenc": "1.7.0"
  }
}

$ curl -s localhost:8000/v1/guard -H "Content-Type: application/json" -d '{"answer":"اليوم طقس جميل","ui_lang":"en"}' | jq "{verdict, counts, summary_en}"
{
  "verdict": "no_quotes",
  "counts": {
    "quotes": 0,
    "found": 0,
    "flagged": 0,
    "by_status": {}
  },
  "summary_en": "No Quran or Hadith quotation that can be checked was found in the answer. Basira is a deterministic aid; \"not found in our sources\" is not a verdict on the text. Consult qualified scholars when in doubt."
}
```

### 3.6 `/v1/rules` and `/v1/sources`
```
$ curl -s "localhost:8000/v1/rules?ui_lang=en" | jq "{states, source, safety_sha256, text_head: .text[0:140]}"
{
  "states": [
    "found",
    "partial_match",
    "needs_review",
    "not_found"
  ],
  "source": "SAFETY.md",
  "safety_sha256": "6a443a070dea45d9b5c9e4e06fb3921e74b066f1aa46bb4e06ccdcc5ae024227",
  "text_head": "Basira grounding rules (read once per session; source of truth: SAFETY.md in the repository)\n\nWhat Basira is: a deterministic checker. Given"
}

$ curl -s localhost:8000/v1/sources | jq "[.[] | {id, version, records, sha256: .sha256[0:12]}]"
[
  { "id": "tanzil_uthmani",     "version": "1.1",      "records": 6236,  "sha256": "bf4f57b968d0" },
  { "id": "tanzil_simple_clean","version": "1.1",      "records": 6236,  "sha256": "228df2a71767" },
  { "id": "tanzil_simple",      "version": "1.1",      "records": 6236,  "sha256": "f3268cfe7a40" },
  { "id": "ohd",                "version": "1515f6cb", "records": 62169, "sha256": "" },
  { "id": "hadeethenc_ar",      "version": "1.7.0",    "records": 3582,  "sha256": "d5d397cb9fc8" }
]
```
(OHD is 18 files; their per-file hashes are in the manifest `books[]` and in the MCP `list_sources` output.)

### 3.7 Limits — measured
```
$ curl -s -w " %{http_code}\n" localhost:8000/v1/check -H "Content-Type: application/json" -d "{\"text\":\"<5001 × ا>\"}"
{"error":{"code":"text_too_long","message_ar":"النص أطول من الحد المسموح (5000 حرفًا).","message_en":"The text exceeds the allowed length (5000 characters)."}} 413

$ for i in $(seq 1 31); do curl -s -o /dev/null -w "%{http_code} " localhost:8000/v1/check -H "Content-Type: application/json" -d '{"text":"اختبار"}'; done   # no X-Eval-Key
200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 429
```

### 3.8 Verification receipt — `POST /v1/receipt` → `GET /v/{token}` (E-052)

The receipt **is the input**: `token = base64url(zlib(json{v:1, t:text, l:ui_lang}))` — a compressed payload, no
secret, no database (ADR-004). `receipt_id` = first 16 hex of `determinism_hash`. Issue and re-verify share one core
(`devgate.issue_receipt` / `devgate.verify_receipt`); the MCP tool `issue_receipt(text, ui_lang)` returns the same object.
Real run on the full index (build `dev`, index `54892a95…`):

```
$ curl -s -D - -X POST localhost:8000/v1/receipt -H 'Content-Type: application/json' \
  -d '{"text":"قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «إنما الأعمال بالنيات» رواه البخاري","ui_lang":"ar"}'
HTTP/1.1 200 OK
x-basira-determinism-hash: 11ac6c77e96409ef4f689b28f677a18cf3cd96cefe1627338bc428f487bb95dc
cache-control: no-store
{"receipt_id":"11ac6c77e96409ef","determinism_hash":"11ac6c77e96409ef4f689b28f677a18cf3cd96cefe1627338bc428f487bb95dc",
 "corpus":{"tanzil":"1.1","ohd_commit":"1515f6cb","hadeethenc":"1.7.0"},
 "index_sha256":"54892a95fbb02d95d454fa8047e8178dd492073794603ed336a3504b12b9944d","build_sha":"dev",
 "issued_at":"2026-10-03T07:45:58Z","ui_lang":"ar","summary":{"quotes":2,"by_status":{"found":2}},
 "quotes":[… compact, same shape as MCP verify_text …],"validator_rejections":0,"disclaimer":"…",
 "token":"eNotjjEKwkAQRa8yTJ3Gdm9jbyViIzYSk5hriOwSQRAisgoKOcX_p9grOLuxm_95_zE73apbVLpRpzzAsxYMiPngyUkav7iwkZJrtsIjYkl4wCPgzp5NGj_C7j9Pz5eT6ZpnBvsZPiPmkO2huBr2th-mt5iis6qdwYCb9WbVSlf203Kt-x_D9WP1",
 "presented_hash":null,"verified_now":null,"stale":null}

$ curl -s "localhost:8000/v/<token>?h=11ac6c77…95dc"      → "verified_now": true,  "stale": false
$ curl -s "localhost:8000/v/<token>?h=000…000"             → "verified_now": false, "stale": true   (HTTP 200: said, not hidden)
$ curl -s "localhost:8000/v/<token>"                       → both false (plain re-run, no claim made)
$ curl -s localhost:8000/v/not-a-token                     → HTTP 400 {"error":{"code":"receipt_invalid",…}}
```

`stale: true` means the fresh `determinism_hash` differs from the one presented: the corpus build (`index_sha256`),
the matcher, or a verdict changed since issue. Limits: the token is refused **before** inflating when longer than any
legitimate token (`413 text_too_long`), and inflation is bounded to `max_text_chars × 4 + 256` bytes (no zip bombs).
Both routes sit behind `_guard` (readiness + the same rate limiter / `X-Eval-Key`).

### 3.9 Post-validator V6 — every `found` has an independent proof (B04, I17)

`verify.validate_response` re-derives each `found` from the Store alone: the quote's **strict** tokens
(`normalize.strict_tokens`) must occur as a **contiguous window** in the strict token stream of the first matched record
(crossing adjacent ayat for a range), checked in **both** rasm streams — the Uthmani display stream (`GS` at `g_start`) and
the simple stream (`GS2` at `g2_start`) with their twin-rasm alternates (E-024). Failure → `needs_review` /
`review_reason: "validator_unproven"`, `message_key: needs_review_unproven`, `validator_rejections += 1`; the closest
record stays visible. Measured: first version (display stream only) wrongly rejected **3/150** eval cases
(A-010, A-011, A-013 — simple-rasm quotes of ayat whose two rasms differ in word count); proving in both streams → **150/150**.

### 3.10 `needs_review` / `attribution_only` (B05)

A quote that is only an **isnad** («عن أبي هريرة رضي الله عنه قال: قال رسول الله ﷺ:», «حدثنا … عن … عن ابن عمر») or only an
**attribution** («رواه البخاري», «متفق عليه», «أخرجه مسلم في صحيحه», also inside «قال ﷺ: «رواه البخاري ومسلم»») is never
`not_found`: `not_found` would read as a verdict on a text that was not supplied. It returns `needs_review` /
`review_reason: "attribution_only"`, `message_key: needs_review_attribution_only` («هذا عزو أو إسناد بلا متن … أدخل نص
المتن ليُفحص»), `matches: []`, no external links, and does **not** count as a validator rejection (wording, not a
rejection). A chain that is verbatim in an OHD record (records carry their isnad) stays `found` — V6 proves it.

### 3.11 Audit fixes B06 · B07 · B10 · B12 (E-053)

| Field / notice | Where | Meaning |
|---|---|---|
| `matches[].source_segments[]` | `Match` | **B07.** For a quote spanning several ayat: one entry per ayah, in Mushaf order — `{ref, ref_label_ar, ref_label_en, source_text, source_url}`; `source_text` is the record's display field **byte-exact**, V1/V2 re-checked per element. Empty for single-ayah quotes. Never a generated joined line. |
| `quotes_detected`, `extraction_truncated` | `CheckResponse` | **B10.** Spans found before the cap (`max_quotes`=30) and whether only the first ones were checked. When true, every returned quote also carries `notice_keys: ["extraction_truncated"]`. |
| `ocr_truncated` + notice `ocr_truncated` | `/v1/check/image` | **B10.** The image text exceeded `max_text_chars`; only the first part was checked — said, not hidden. |
| notice `claimed_ref_invalid` | quote | **B06.** The claimed reference cannot exist in the Mushaf («الإخلاص 1-999», «البقرة 300», a backwards range) — `app/quran_meta.AYAH_COUNTS` (114 surahs, Σ 6 236, test-pinned equal to Tanzil). Status untouched (I8). |
| `claimed_ayah_mismatch` semantics | quote | **B06.** A verbatim passage that recurs (the 31 refrains of سورة الرحمن) is compared against **every** matched position, so «[الرحمن: 77]» is correct, not a mismatch; «[البقرة: 5]» still is. |
| rate-limit identity | `_guard` | **B12.** `X-Forwarded-For` is honoured **only** when the TCP peer is in `BASIRA_TRUSTED_PROXIES` (IPs/CIDRs); then the right-most untrusted hop is the client. Default: the header is ignored — a rotating header no longer buys a fresh quota. The Dockerfile no longer passes `--forwarded-allow-ips='*'`; set `FORWARDED_ALLOW_IPS` = the same proxies. |
| image sniffing | `/v1/check/image` | **B12.** The bytes must carry the signature of the declared type (PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`, WebP `RIFF….WEBP`) or the request is `422 invalid_input` — before any provider sees it. |

## 4. Determinism contract

`determinism_hash = sha256(index records sha256 ‖ loose-normalised input ‖ ordered verdicts (span, status, message_key, matched refs))`.
Same text + same corpus build ⇒ same hash, across restarts and across snapshot/build boots (E-032). It is returned in the
body and, since this release, in the `X-Basira-Determinism-Hash` response header of `/v1/check` and `/v1/guard`, so a proxy or a
judge can record it without parsing the body. `/health.index_sha256` identifies the corpus build. The header is absent on
error responses. The MCP `verify_text` tool returns the same hash for the same text (tested byte-equal against REST).

## 5. Mock mode

With no provider keys (`LLM_PROVIDER=mock`, `VISION_PROVIDER=mock` — the defaults) extraction is rule-based only
(introducers, brackets, corpus-anchored detection) and `extraction_provider` is `"mock"`. Verdicts are identical for
every quote the rules find; a real provider can only *add* candidate spans (every proposal is re-located verbatim in
the input, ADR-005), it never changes matching. `/v1/check/image` in mock mode returns the fixture OCR text with the
`ocr_mock` notice so it is never mistaken for a reading of the image. All outputs in this document are mock mode.

## 6. Error codes

| HTTP | `code` | when |
|---|---|---|
| 413 | `text_too_long` | `text`/`answer` > `BASIRA_MAX_TEXT_CHARS` (5000) |
| 413 | `image_too_large` | image > 6 MB |
| 400 | `receipt_invalid` | `GET /v/{token}`: token is not base64url(zlib(json{v:1,…})) or was not issued by Basira |
| 422 | `invalid_input` | blank text, bad JSON, unsupported MIME, unknown `lang` |
| 429 | `rate_limited` | > 30 requests/min from one client without `X-Eval-Key` |
| 503 | `degraded` | index still loading (see `/health`) |
| 500 | `internal` | unexpected; only the exception class is logged |

## 7. Try it in one minute

```bash
cd backend && BASIRA_MCP=1 .venv/bin/uvicorn app.main:app --port 8000      # ~2 s from snapshot, ~25 s first build
curl -s localhost:8000/health | jq .status
curl -s localhost:8000/v1/check -H 'Content-Type: application/json' -d '{"text":"قال تعالى: ﴿إن الله مع الصابرين﴾"}' | jq '.quotes[0].status'
curl -s localhost:8000/v1/guard -H 'Content-Type: application/json' -d '{"answer":"قال ﷺ: «الدين المعاملة»"}' | jq '{verdict, summary_en}'
backend/.venv/bin/python scripts/mcp_demo.py                                  # MCP client demo (docs/INTEGRATIONS.md §3.1)
```
