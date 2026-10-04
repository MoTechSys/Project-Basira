"""IslamicEval 2026 Task 1 (span detection) on dev, via the product's own Pipeline.check()."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.config import Settings  # noqa: E402
from app.pipeline import CorpusMeta, Pipeline  # noqa: E402
from app.providers import MockLLM  # noqa: E402
from app.retrieve.index import Retriever  # noqa: E402
from app.schemas import CheckRequest  # noqa: E402
from app.store import load_store  # noqa: E402

CHUNK = 4900


def main() -> None:
    s = Settings(index_dir=REPO / "corpus/index")
    st = load_store(s.index_dir)
    p = Pipeline(
        st,
        Retriever(st),
        MockLLM(),
        s,
        CorpusMeta.from_manifest(json.loads(s.manifest_path.read_text()), st.meta),
    )
    data = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".scratch/islamiceval2026/dev_set/dev.jsonl")
    out_path = (
        Path(sys.argv[2]) if len(sys.argv) > 2 else Path("eval/islamiceval/predictions_2026_task1_dev.tsv")
    )
    with data.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh]
    t0 = time.time()
    nsp = 0
    with out_path.open("w", encoding="utf-8") as out:
        out.write("Response_ID\tAnnotation_ID\tSegment_Type\tSpan_Start\tSpan_End\n")
        for r in rows:
            ans = r["generated_answer"]
            aid = 0
            found = False
            chunks: list[tuple[int, str]] = []
            i = 0
            while i < len(ans):
                j = min(len(ans), i + CHUNK)
                if j < len(ans):
                    k = ans.rfind("\n", i, j)
                    j = k if k > i else j
                chunks.append((i, ans[i:j]))
                i = j
            for off, c in chunks:
                if not c.strip():
                    continue
                d = asyncio.run(p.check(CheckRequest(text=c, ui_lang="ar"))).model_dump()
                for q in d["quotes"]:
                    aid += 1
                    found = True
                    for sg in q["segments"]:
                        nsp += 1
                        out.write(f"{r['id']}\t{aid}\t{sg['type']}\t{sg['start'] + off}\t{sg['end'] + off}\n")
            if not found:
                out.write(f"{r['id']}\t1\tNoAnnotation\t0\t0\n")
    print("secs", round(time.time() - t0, 1), "segments", nsp)


if __name__ == "__main__":
    main()
