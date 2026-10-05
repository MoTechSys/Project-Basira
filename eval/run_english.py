#!/usr/bin/env python3
"""eval/run_english.py — measure the English gate on eval/english_cases.yaml (recall@k, negatives, latency).

    backend/.venv/bin/python eval/run_english.py                      # full index, k=5, 3 repeats
    backend/.venv/bin/python eval/run_english.py --k 10 --repeats 1
    backend/.venv/bin/python eval/run_english.py --sweep               # bigram weight 0.0 … 1.0 (tuning evidence)
    backend/.venv/bin/python eval/run_english.py --fail-under 0.9      # CI-style gate on recall@k

Definitions (published with every number, same discipline as eval/metrics.py):
  * recall@k      — among cases with an expected ref, fraction where the expected ref (or one of its
                    `accept` twins) is within the first k candidates. Wilson 95 % interval when n ≥ 30,
                    otherwise «indicative» counts.
  * MRR           — mean reciprocal rank of the expected ref over the same cases (0 if absent in top k).
  * neg_ceiling   — among `expect: none` cases, the highest top-1 score observed; the gate test asserts it
                    stays below LOW_SCORE_CEILING, and the gap to the lowest positive top-1 is reported.
  * variance      — results across repeats must be byte-identical (deterministic retrieval).
Writes eval/results/english_latest.json. No LLM, no network, no religious text in this file.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))

from app.retrieve import translations as tr  # noqa: E402
from eval.metrics import wilson  # noqa: E402

CASES = REPO / "eval" / "english_cases.yaml"
RESULTS = REPO / "eval" / "results"
LOW_SCORE_CEILING = 0.60  # measured: highest negative top-1 (see docs/ENGLISH_GATE.md); gate test re-checks


def load_cases(path: Path = CASES) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) >= 30, "english_cases.yaml must hold ≥ 30 cases"
    ids = [c["id"] for c in data]
    assert len(set(ids)) == len(ids), "duplicate case ids"
    return data


def accepted_refs(case: dict[str, Any]) -> set[str]:
    exp = case["expect"]
    return {str(exp["ref"]), *(str(r) for r in exp.get("accept", []))}


def run_once(idx: tr.TranslationIndex, cases: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in cases:
        t0 = time.perf_counter()
        cands = idx.candidates(c["text"], k)
        ms = (time.perf_counter() - t0) * 1000
        row: dict[str, Any] = {
            "id": c["id"],
            "category": c["category"],
            "ms": round(ms, 2),
            "top": [(x.kind, x.ref, x.source_key, x.score) for x in cands],
        }
        if c["expect"] == "none":
            row["expected"] = None
            row["top1"] = cands[0].score if cands else 0.0
            row["pass"] = row["top1"] < LOW_SCORE_CEILING
        else:
            want = accepted_refs(c)
            kind = c["expect"]["kind"]
            rank = next((i + 1 for i, x in enumerate(cands) if x.kind == kind and x.ref in want), None)
            row["expected"] = c["expect"]["ref"]
            row["rank"] = rank
            row["top1"] = cands[0].score if cands else 0.0
            row["pass"] = rank is not None
        rows.append(row)
    return rows


def aggregate(rows: list[dict[str, Any]], k: int) -> dict[str, Any]:
    pos = [r for r in rows if r["expected"] is not None]
    neg = [r for r in rows if r["expected"] is None]
    hit = sum(1 for r in pos if r["rank"] is not None)
    lo, hi = wilson(hit, len(pos))
    by_cat: dict[str, dict[str, int]] = {}
    for r in rows:
        b = by_cat.setdefault(r["category"], {"n": 0, "pass": 0})
        b["n"] += 1
        b["pass"] += int(r["pass"])
    return {
        "k": k,
        "n_positive": len(pos),
        f"recall@{k}": round(hit / len(pos), 4) if pos else None,
        "recall_wilson95": [round(lo, 4), round(hi, 4)],
        "recall_label": "indicative (n < 30)" if len(pos) < 30 else "wilson 95 %",
        "hits": hit,
        "mrr": round(statistics.fmean((1 / r["rank"]) if r["rank"] else 0.0 for r in pos), 4)
        if pos
        else None,
        "misses": [r["id"] for r in pos if r["rank"] is None],
        "n_negative": len(neg),
        "neg_pass": sum(1 for r in neg if r["pass"]),
        "neg_ceiling_top1": round(max((r["top1"] for r in neg), default=0.0), 4),
        "pos_floor_top1": round(min((r["top1"] for r in pos), default=0.0), 4),
        "low_score_ceiling": LOW_SCORE_CEILING,
        "by_category": by_cat,
        "latency_ms_p50": round(statistics.median(r["ms"] for r in rows), 2),
        "latency_ms_max": round(max(r["ms"] for r in rows), 2),
    }


def sweep(idx: tr.TranslationIndex, cases: list[dict[str, Any]], k: int) -> None:
    """Measure recall@k / MRR for each bigram weight. Mutates the module constant, restores it after."""
    original = tr.BIGRAM_WEIGHT
    print(f"{'w':>4} {'recall@' + str(k):>9} {'MRR':>6} {'neg_ceiling':>11} {'pos_floor':>9}  misses")
    try:
        for w10 in range(0, 11):
            tr.BIGRAM_WEIGHT = w10 / 10
            a = aggregate(run_once(idx, cases, k), k)
            print(
                f"{tr.BIGRAM_WEIGHT:4.1f} {a[f'recall@{k}']:9.3f} {a['mrr']:6.3f} {a['neg_ceiling_top1']:11.3f} "
                f"{a['pos_floor_top1']:9.3f}  {','.join(a['misses']) or '-'}"
            )
    finally:
        tr.BIGRAM_WEIGHT = original


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", default=str(REPO / "corpus" / "index" / "translations.pkl"))
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--sweep", action="store_true", help="print recall for bigram weights 0.0 … 1.0 and exit")
    ap.add_argument("--fail-under", type=float, default=None, help="exit 1 if recall@k is below this")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    idx = tr.TranslationIndex.load(Path(args.index))
    load_s = time.perf_counter() - t0
    cases = load_cases()
    if args.sweep:
        sweep(idx, cases, args.k)
        return 0

    runs = [run_once(idx, cases, args.k) for _ in range(max(1, args.repeats))]
    strip = lambda rows: [{kk: v for kk, v in r.items() if kk != "ms"} for r in rows]  # noqa: E731
    identical = all(strip(r) == strip(runs[0]) for r in runs[1:])
    agg = aggregate(runs[0], args.k)
    agg.update({"repeats": len(runs), "repeats_identical": identical, "index_load_s": round(load_s, 3)})
    agg["index_meta"] = {
        kk: idx.meta[kk] for kk in ("n_docs", "n_quran_docs", "n_hadith_docs", "bigram_weight")
    }

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "english_latest.json").write_text(
        json.dumps({"aggregate": agg, "rows": runs[0]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(agg, ensure_ascii=False, indent=2))
    for r in runs[0]:
        mark = "OK " if r["pass"] else "MISS"
        if r["expected"] is None:
            print(f"{mark} {r['id']}  top1={r['top1']:.3f}  {r['top'][0][:2] if r['top'] else '-'}")
        else:
            print(
                f"{mark} {r['id']}  rank={r['rank']}  top1={r['top1']:.3f}  want={r['expected']}  got={[t[1] for t in r['top'][:3]]}"
            )
    if not identical:
        print("FAIL: repeats differ — retrieval is not deterministic", file=sys.stderr)
        return 1
    if args.fail_under is not None and (agg[f"recall@{args.k}"] or 0.0) < args.fail_under:
        print(f"FAIL: recall@{args.k} {agg[f'recall@{args.k}']} < {args.fail_under}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
