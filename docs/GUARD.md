# The Guard — putting Basira between a chatbot and its user

`POST /v1/guard` (REST) · `guard_answer` (MCP tool). Code: `backend/app/guard.py`, templates
`backend/app/guard_messages.py`, tests `backend/tests/test_guard.py`. Every output below is pasted from a real run
(2026-10-03, full corpus, mock provider).

## 1. What it answers

> «This chatbot answer contains N Quran/Hadith quotations; K of them are not byte-exact in Basira's licensed sources —
> review them before publishing.»

That is the whole claim. The Guard says nothing about the *answer* (its reasoning, its fiqh, its tone) and nothing
about the *authenticity* of a hadith. It only tells you whether each quoted text is the text.

| `verdict` | condition | what the integrator should do |
|---|---|---|
| `clear` | every detected quotation is `found` | publish |
| `flagged` | at least one quotation is `partial_match` / `needs_review` / `not_found` | hold, annotate, or send to review — **never rewrite the quotation automatically** |
| `no_quotes` | no Quran/Hadith quotation detected | publish (Basira had nothing to check) |

Response fields: `verdict`, `counts {quotes, found, flagged, by_status}`, `flagged_quote_ids`, `quotes[]` (the compact
per-quotation detail: status, kind, quoted_text, review_reason, matches with the **verbatim** `source_text` and
`source_url`, notices as sentences), `flags` (chain message / refusal / PII suspected), `summary_ar`, `summary_en`,
`determinism_hash`, `corpus`. The same hash is in the `X-Basira-Determinism-Hash` header.

## 2. Where it sits

```
 user ──prompt──▶ your LLM ──draft answer──▶ ┌──────────── Guard ────────────┐
                                             │ POST /v1/guard {answer}       │
                                             │  extract quotations           │
                                             │  exact / fuzzy match (Basira) │
                                             │  verdict + fixed summaries    │
                                             └───────┬───────────────────────┘
                     clear / no_quotes ◀─────────────┤
                       → show answer                 │ flagged
                                                     ▼
                                 show answer + summary banner, or hold for human review,
                                 or ask the LLM to *cite the source_text verbatim* (never to "fix" it)
```

Latency budget: the Guard is the same pipeline as `/v1/check` — match ≈ 3 ms per quote; with the mock provider a
two-quotation answer returns in well under 100 ms; with a real extraction provider the provider call dominates (E-035).

## 3. Minimal client (Python, stdlib) — `docs/examples/guard_client.py`

```python
import json
import urllib.request

BASIRA = "http://localhost:8000"


def guarded_reply(model_answer: str, lang: str = "ar") -> str:
    body = json.dumps({"answer": model_answer, "ui_lang": lang}).encode("utf-8")
    req = urllib.request.Request(f"{BASIRA}/v1/guard", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        g = json.load(resp)
    if g["verdict"] == "flagged":  # hold or annotate — never rewrite the quotation
        return f"{model_answer}\n\n⚠ {g['summary_' + lang]}"
    return model_answer
```

Real run:
```
$ backend/.venv/bin/python docs/examples/guard_client.py
قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «الدين المعاملة»

⚠ في الإجابة اقتباسان؛ واحد منها يحتاج مراجعة قبل النشر (لم يُوجد مطابقًا في مصادر بصيرة أو يختلف عن النص المصدر). بصيرة أداة مساعدة حتمية؛ «لم يوجد في مصادرنا» ليس حكمًا على النص. راجع أهل العلم عند الشك.
```

Same thing from an MCP-capable assistant: call `guard_answer(answer, ui_lang)` — identical output (tested).

## 4. The summaries are templates, nothing else

`summary_ar` / `summary_en` are rendered from fixed strings in `guard_messages.py` with **only counts** substituted
(Arabic number agreement: «اقتباس واحد / اقتباسان / 3 اقتباسات / 11 اقتباسًا»). Guaranteed by tests:

* every template and every rendered summary passes `app.messages.scan_forbidden` (the forbidden-lexicon scanner that
  guards all of Basira's prose) — no «محرّف / ضعيف / صحيح / fabricated / weak …»;
* no quoted text and no `source_text` (not even a 4-word window of it) appears in a summary; the Arabic summary's
  vocabulary is a closed set equal to the templates' vocabulary;
* every summary ends with the fixed footer: «لم يوجد في مصادرنا» ليس حكمًا على النص / "not found in our sources" is not a verdict.

The templates live outside `messages/*.json` on purpose (that file is owned by another work stream); they follow the
same rules and the same scanner.

## 5. Full response shape (real)

```
$ curl -s localhost:8000/v1/guard -H "Content-Type: application/json" -d '{"answer":"قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «طلب العلم فريضة على كل مسلم ومسلمة»","ui_lang":"ar"}' | jq "del(.quotes)"
{
  "verdict": "flagged",
  "counts": { "quotes": 2, "found": 1, "flagged": 1, "by_status": { "found": 1, "partial_match": 1 } },
  "flagged_quote_ids": [ "q2" ],
  "flags": { "chain_message": false, "refusal": false, "pii_suspected": false },
  "extraction_degraded": false,
  "summary_ar": "في الإجابة اقتباسان؛ واحد منها يحتاج مراجعة قبل النشر (لم يُوجد مطابقًا في مصادر بصيرة أو يختلف عن النص المصدر). بصيرة أداة مساعدة حتمية؛ «لم يوجد في مصادرنا» ليس حكمًا على النص. راجع أهل العلم عند الشك.",
  "summary_en": "The answer contains 2 quotation(s); 1 of them need review before publishing (not found verbatim in Basira's sources, or differing from the source text). Basira is a deterministic aid; \"not found in our sources\" is not a verdict on the text. Consult qualified scholars when in doubt.",
  "determinism_hash": "e8bb60f86941daa614b42f601ad52388943dd4104ea6f84ef8ca714b2321ae0a",
  "corpus": { "tanzil": "1.1", "ohd_commit": "1515f6cb", "hadeethenc": "1.7.0" }
}
```
`quotes[1]` (id `q2`) carries `status: partial_match`, `diff_kinds: ["word_added_in_quote"]` and the Ibn Majah 220
record verbatim as `source_text` — that is what a reviewer (or the LLM, instructed to *quote*, not to *fix*) works from.

## 6. Limits

* Detection is rule-based in mock mode (introducers, brackets, corpus anchors); an unmarked, unintroduced paraphrase may not
  be detected → `no_quotes` is «nothing detected», not «nothing quoted». A real extraction provider adds spans (ADR-005).
* English/transliterated quotations are `needs_review/non_arabic` today (→ `flagged`). The English gate (PR #1) is the data
  layer for a future English path.
* `flagged` is a review signal, not a score of the answer. `partial_match` on a hadith may be a legitimate transmission variant.
* Max 5 000 characters per call (`text_too_long` otherwise); rate limit 30/min per IP without `X-Eval-Key`.
* Nothing is stored. If you need an audit trail, store the `determinism_hash` and the corpus build (`/health.index_sha256`);
  re-running the same answer on the same build reproduces the verdict.
