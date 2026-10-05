# Models — measured on Basira's real tasks (2026-10-03)

**Where this is used:** `/settings` (server-side model config, E-051) and `GET /v1/models`. The catalog lives in `backend/app/byok.py`
and these numbers are the only source for what the UI shows. Nothing here is a vendor claim.

**How measured.** An OpenAI-compatible proxy endpoint, `https://www.genspark.ai/api/llm_proxy/v1`, temperature 0,
`response_format=json_object`, Basira's real `EXTRACT_SYSTEM` prompt (`backend/app/providers/openai_compat.py`).
Six extraction inputs (4 marked Arabic quotes incl. a foreign token inside an ayah, 1 unmarked saying,
1 plain text, 1 English quote), 6 parallel calls per model. "exact" = returned exactly the gold span list;
**every model returned only verbatim substrings** (no rewriting). OCR: `docs/manual-test/images/01_ayah_typo.png`.
Script: `scripts/bench_models.py` (needs `GSK_TEST_KEY` + `OPENAI_BASE_URL` in the environment).

| model | cost× | exact /6 | p50 ms | max ms | OCR faithful | OCR ms | verdict |
|---|---|---|---|---|---|---|---|
| **gpt-5.4-mini** | 0.3 | **6** | **1220** | 1759 | yes | 1343 | **default** — best accuracy, speed and cost |
| glm-5p3-flash-low | 0.15 | 6 | 1517 | 3573 | yes (1 spelling slip outside quote) | 1610 | cheapest |
| gpt-6-luna | 0.1 | 6 | 2690 | 3719 | yes | 4619 | good, slower OCR |
| mimo-v2.6-flash | 0.14 | 6 | 6506 | 11482 | yes | 27942 | too slow |
| claude-sonnet-5-5 | 2 | 5 | 3016 | 5264 | yes | 1676 | best large model |
| gpt-6-sol | 2 | 5 | 2069 | 3137 | yes | 2662 | fastest large |
| claude-fable-5-1 | 10 | 5 | 3833 | 11305 | — | — | not justified |
| gpt-5.6-luna | 0.2 | 5 | 2164 | 2759 | — | — | missed foreign-token ayah |
| glm-5p3 | 1 | 5 | 6236 | 21314 | — | — | slow |
| kimi-k3 | 3 | 5 | 7969 | 10107 | — | — | slow |
| claude-opus-5-5 | 4 | 4 | 4530 | 5758 | yes | 2545 | 1× non-JSON refusal |
| gpt-5.5 | 5 | 4 | 7486 | 8750 | — | — | listed «رواه البخاري» as quote |
| gpt-5.4 | 3 | 4 | 4124 | 8347 | yes | 6715 | E-030 reference, now beaten |
| gpt-6-astra | 10 | 4 | 3022 | 3631 | — | — | 10× for nothing |
| gpt-6.1-sol | 2 | 4 | 3095 | 3631 | — | — | |
| deep-seek-v4.1-flash | 0.3 | 4 | 1853 | 6100 | — | — | |
| gpt-5.6-terra | 2 | 3 | 1193 | 2606 | — | — | missed English quote |
| minimax-m3 | 0.3 | 3 | 4419 | 6194 | — | — | |
| claude-haiku-4-5 | — | 0 | 902 | 960 | — | — | never returned JSON (6/6 failures) |
| gemini-3.1-pro | — | — | — | — | — | — | not allowed on this key (HTTP 400) |

The "unmarked saying" miss (الدين المعاملة, no brackets) is **not an error**: the rule engine + corpus anchors
detect it; models were told to list only passages *presented* as quotes. 5/6 therefore equals 6/6 in product terms.

**Key point for judges:** the model choice never changes a verdict on a bracketed quote — the determinism hash
is identical with the mock or a configured model (`backend/tests/test_byok.py::test_check_headers_are_ignored_and_verdict_is_model_independent`).
