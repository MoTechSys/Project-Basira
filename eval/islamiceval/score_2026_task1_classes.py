"""Per-class char-level F1 for IslamicEval 2026 Task 1 predictions (needs scikit-learn)."""

from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

C = {"Ayah": 1, "matn": 2, "isnad": 3, "claimed_source": 4}
D = Path(".scratch/islamiceval2026/dev_set/")


def main() -> None:
    with (D / "dev.jsonl").open(encoding="utf-8") as fh:
        resp = {row["id"]: row["generated_answer"] for row in map(json.loads, fh)}

    def lab(path: Path) -> dict[str, np.ndarray]:
        labels = {k: np.zeros(len(v), int) for k, v in resp.items()}
        with path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                t = r["Segment_Type"].strip()
                if t in C:
                    labels[r["Response_ID"]][int(r["Span_Start"]) : int(r["Span_End"])] = C[t]
        return labels

    gold = lab(D / "dev_task_1.tsv")
    pred = lab(
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("eval/islamiceval/predictions_2026_task1_dev.tsv")
    )
    g = np.concatenate([gold[k] for k in resp])
    p = np.concatenate([pred[k] for k in resp])
    f = f1_score(g, p, labels=[1, 2, 3, 4], average=None)
    print({k: round(v, 3) for k, v in zip(C, f, strict=True)}, "macro", round(f.mean(), 4))
    cm = collections.Counter(zip(g.tolist(), p.tolist(), strict=True))
    print("rows gold (neither,Ayah,matn,isnad,cs) x pred")
    for a in range(5):
        print(a, [cm[(a, b)] for b in range(5)])


if __name__ == "__main__":
    main()
