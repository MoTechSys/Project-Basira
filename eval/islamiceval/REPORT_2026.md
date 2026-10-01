# Basira on IslamicEval 2026 — public DEV set (official scorers)

Data: https://github.com/Watheq9/IslamicEval2026 (research-only licence → downloaded to `.scratch/islamiceval2026/`, never committed).
Deterministic core, no LLM, same code path as `POST /v1/check`.

## Task 2 — hallucination identification (Ayah / matn)
| | before (main @5fb118f) | after (basira-pro) | published dev (SanadAI / Namaa) |
|---|---|---|---|
| Ayah acc (n=698) | 98.42 | **98.71** | 97.42 / 96.1 |
| matn acc (n=588) | 93.20 | 93.20 | 94.56 / 91.3 |
| dangerous (gold incorrect → said correct) | 8 | 6 | — |

## Task 1 — span detection (character macro-F1, official `task1_scoring.py`)
| | before | after |
|---|---|---|
| macro-F1 | 35.53 | **64.30** |
| Ayah | 79.3 | 83.5 |
| matn | 62.8 | 65.8 |
| isnad | 0.0 | 35.2 |
| claimed_source | 0.0 | 72.7 |

Causes of the gain: explicit `<aya_start>/<hadith_start>` tags, boundary tightening, corpus-anchored seed-and-extend detector, deterministic `claimed_source` + `isnad` segmenter (`backend/app/extract/{anchor,segments}.py`).
Remaining gap: unmarked hadith paraphrases and isnad boundaries → next step is a small BIO tagger + LLM proposals (see PROMPT).

Reproduce: `git clone https://github.com/Watheq9/IslamicEval2026 .scratch/islamiceval2026 && backend/.venv/bin/python eval/islamiceval/run_2026_task2.py && backend/.venv/bin/python eval/islamiceval/run_2026_task1.py`
