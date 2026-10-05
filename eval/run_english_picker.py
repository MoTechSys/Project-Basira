"""eval/run_english_picker.py — the English gate END-TO-END: candidates → picker (rule / model) → selection.

ملاحظة: يُشغَّل عبر Makefile (target: eval) أو مباشرة من سطر الأوامر.
جميع المسارات نسبية لجذر المستودع.
"""

This is the «with model / without model» evidence for the English door (E-048). For every case in
eval/english_cases.yaml it records what gets *selected*:

  rule-only   deterministic: top-1 ≥ RULE_MIN_TOP1 and gap ≥ RULE_MIN_GAP, else nothing
  model       the rule first; when it abstains, the named model picks an index or refuses (0)

Metrics (positives = cases with an expected ref; negatives = expect: none):
  selected_correct   a candidate was selected and it is the expected ref (or an accepted twin)
  selected_wrong     a candidate was selected and it is NOT the expected passage  ← the number that must be 0
  abstained          nothing selected
  neg_false_select   a negative where something was selected                       ← must be 0

Model answers are constrained to an index into the candidate list (``parse_pick``); the model never
produces text. Model id, endpoint host, temperature, date and repeats are written into the report.
Needs OPENAI_BASE_URL / OPENAI_API_KEY for the model arm; the rule arm runs offline.

    backend/.venv/bin/python eval/run_english_picker.py                      # rule only
    backend/.venv/bin/python eval/run_english_picker.py --models gpt-5.4 claude-sonnet-5-5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.english_gate import RULE_MIN_GAP, RULE_MIN_TOP1, EnglishGate, EnglishPicker  # noqa: E402
from app.store import load_store  # noqa: E402

CASES = REPO / "eval" / "english_cases.yaml"
OUT_DIR = REPO / "eval" / "results"


def accepted(c: dict[str, Any]) -> set[tuple[str, str]]:
    e = c.get("expect")
    if not isinstance(e, dict):
        return set()
    refs = {str(e["ref"]), *(str(x) for x in e.get("accept", []))}
    return {(str(e["kind"]), r) for r in refs}


def ref_key(kind: str, ref: dict[str, Any]) -> str:
    return f"{ref['surah']}:{ref['ayah']}" if kind == "quran" else str(ref["id"])


async def run_arm(gate: EnglishGate, cases: list[dict[str, Any]], repeats: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    t_all = time.perf_counter()
    for c in cases:
        want = accepted(c)
        picks: list[tuple[str, str] | None] = []
        pickers: list[str] = []
        ms: list[int] = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            res = await gate.run(str(c["text"]))
            ms.append(int((time.perf_counter() - t0) * 1000))
            sel = next(((x.kind, ref_key(x.kind, x.ref)) for x in res.candidates if x.selected), None)
            picks.append(sel)
            pickers.append(res.picker)
        sel0 = picks[0]
        stable = all(p == sel0 for p in picks)
        if not want:
            verdict = "neg_false_select" if sel0 is not None else "neg_ok"
        elif sel0 is None:
            verdict = "abstained"
        else:
            verdict = "selected_correct" if sel0 in want else "selected_wrong"
        rows.append(
            {
                "id": c["id"],
                "category": c.get("category"),
                "verdict": verdict,
                "selected": sel0,
                "picker": pickers[0],
                "stable": stable,
                "ms": ms,
                "expected": sorted(want) if want else None,
            }
        )
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return {
        "rows": rows,
        "counts": counts,
        "unstable": [r["id"] for r in rows if not r["stable"]],
        "wall_s": round(time.perf_counter() - t_all, 1),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", default=str(REPO / "corpus" / "index"))
    ap.add_argument("--models", nargs="*", default=[], help="model ids for the model arm (exact API ids)")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--fail-on-wrong", action="store_true", help="exit 1 if any arm selects a wrong passage")
    args = ap.parse_args(argv)

    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    store = load_store(Path(args.index))
    base = EnglishGate.from_path(store, Path(args.index) / "translations.pkl")
    if not base.enabled:
        print("translations.pkl missing — run corpus/fetch_translations.py + build_index.py", file=sys.stderr)
        return 2

    report: dict[str, Any] = {
        "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_cases": len(cases),
        "n_positive": sum(1 for c in cases if accepted(c)),
        "n_negative": sum(1 for c in cases if not accepted(c)),
        "rule": {"min_top1": RULE_MIN_TOP1, "min_gap": RULE_MIN_GAP},
        "repeats": args.repeats,
        "arms": {},
    }
    report["arms"]["rule-only"] = asyncio.run(run_arm(base, cases, args.repeats))

    for model in args.models:
        from app.providers.openai_compat import OpenAICompatPicker  # noqa: PLC0415

        url, key = os.environ.get("OPENAI_BASE_URL", ""), os.environ.get("OPENAI_API_KEY", "")
        if not (url and key):
            print(f"skip {model}: OPENAI_BASE_URL / OPENAI_API_KEY not set", file=sys.stderr)
            continue
        picker: EnglishPicker = OpenAICompatPicker(base_url=url, api_key=key, model=model, timeout_s=40)
        gate = EnglishGate(store, base.index, picker)
        arm = asyncio.run(run_arm(gate, cases, args.repeats))
        arm["model"] = {
            "id": model,
            "endpoint_host": urlparse(url).netloc,
            "temperature": 0,
            "response_format": "json_object",
        }
        report["arms"][model] = arm

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "english_picker.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    bad = False
    print(
        f"english picker — {report['n_cases']} cases ({report['n_positive']} pos / {report['n_negative']} neg), repeats={args.repeats}"
    )
    for name, arm in report["arms"].items():
        c = arm["counts"]
        wrong = c.get("selected_wrong", 0) + c.get("neg_false_select", 0)
        bad |= wrong > 0
        print(
            f"  {name:20} correct={c.get('selected_correct', 0):2}  abstained={c.get('abstained', 0):2}  "
            f"WRONG={c.get('selected_wrong', 0)}  neg_false={c.get('neg_false_select', 0)}  "
            f"unstable={len(arm['unstable'])}  wall={arm['wall_s']}s"
        )
        for r in arm["rows"]:
            if r["verdict"] in ("selected_wrong", "neg_false_select") or not r["stable"]:
                print(
                    f"     ! {r['id']} {r['verdict']} selected={r['selected']} expected={r['expected']} stable={r['stable']}"
                )
    return 1 if (args.fail_on_wrong and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
