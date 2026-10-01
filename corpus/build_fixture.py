#!/usr/bin/env python3
"""corpus/build_fixture.py — a tiny, deterministic subset of the real index for fast tests/CI.

Reads ``corpus/index/records.jsonl`` (full build) and writes ``corpus/fixture/records.jsonl`` +
``meta.json`` + ``surah_names.json`` with:

  * Quran: surahs 1, 2 (first 160 ayat), 8 (ayah 40–50), 55, 112, 113, 114  → both rasms, basmala offsets intact
  * OHD:   the first N hadith of each of the nine books (N=12) + a few canonical records
           (Bukhari 1 «إنما الأعمال», Ibn Maja 220 «طلب العلم», Ibn Maja 2216 «من غشنا»)
  * HadeethEnc: the first 30 records + ids 4560 and 66511 («إنما الأعمال بالنيات», two wordings)

Fixture size ≈ 1.5 MB; store load ≈ 0.3 s. Record format is identical to the full index so
every code path (store, exact, retriever, pipeline, verify) is exercised unchanged.
The fixture is **git-ignored** (it contains corpus text) and rebuilt by tests when the full index
exists; if neither exists the API tests skip.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "index"
OUT = ROOT / "fixture"

QURAN_KEEP: dict[int, tuple[int, int] | None] = {
    1: None,
    2: (1, 160),
    8: (40, 50),
    55: None,
    112: None,
    113: None,
    114: None,
}
OHD_PER_BOOK = 12
OHD_PINNED = {
    ("sahih_al-bukhari", 1),
    ("sunan_ibn-maja", 220),
    ("sunan_ibn-maja", 2216),
    ("sunan_abu-dawud", 1882),
    ("sahih_muslim", 1),
}
HENC_FIRST = 30
HENC_PINNED = {4560, 66511}  # «إنما الأعمال بالنيات» in both wordings (tashkeel in source)


def main() -> int:
    if not (SRC / "records.jsonl").exists():
        print("full index missing — run bootstrap first", file=sys.stderr)
        return 2
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    per_book: dict[str, int] = {}
    henc_n = 0
    counts = {"tanzil": 0, "ohd": 0, "hadeethenc": 0}
    h = hashlib.sha256()
    with (
        (SRC / "records.jsonl").open(encoding="utf-8") as fh,
        (OUT / "records.jsonl").open("w", encoding="utf-8") as out,
    ):
        for line in fh:
            d = json.loads(line)
            c = d["c"]
            keep = False
            if c == "tanzil":
                s = int(d["s"])
                if s in QURAN_KEEP:
                    rng = QURAN_KEEP[s]
                    keep = rng is None or rng[0] <= int(d["a"]) <= rng[1]
            elif c == "ohd":
                key = (d["b"], int(d["n"]))
                n = per_book.get(d["b"], 0)
                if key in OHD_PINNED or n < OHD_PER_BOOK:
                    keep = True
                    per_book[d["b"]] = n + 1
            elif henc_n < HENC_FIRST or int(d["id"]) in HENC_PINNED:
                keep = True
                henc_n += 1
            if keep:
                counts[c] += 1
                out.write(line)
                h.update(line.encode("utf-8"))
    src_meta = json.loads((SRC / "meta.json").read_text(encoding="utf-8"))
    meta = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fixture_of": src_meta.get("records_sha256"),
        "counts": counts,
        "versions": src_meta.get("versions", {}),
        "records_sha256": h.hexdigest(),
        "build_seconds": round(time.time() - t0, 2),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    # store._load_surah_names reads ``index_dir.parent / surah_names.json`` → corpus/surah_names.json (committed)
    print(f"fixture: {counts} in {time.time() - t0:.1f}s → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
