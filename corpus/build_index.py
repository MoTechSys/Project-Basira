#!/usr/bin/env python3
"""corpus/build_index.py — turn verified raw sources into `corpus/index/records.jsonl`.

Run after `python corpus/fetch.py`. Requires the backend venv (uses app.normalize):

    backend/.venv/bin/python corpus/build_index.py

Output (git-ignored):
    corpus/index/records.jsonl   one JSON object per record (see RECORD FORMAT)
    corpus/index/meta.json       counts, versions, sha256 of records.jsonl, build time

RECORD FORMAT (compact; tokens are pre-computed so the server starts fast):
    common:  {"c": corpus, "L": "loose tokens joined by space", "S": "strict tokens joined",
              "P": [start,end, start,end, ...]  # spans into the display text, one pair per token
              "o": index_offset}               # tokens before this offset are NOT indexed (basmala)
    tanzil:  {"c":"tanzil","s":surah,"a":ayah,"tu":uthmani_verbatim,"ts":simple_verbatim,
              "L2","S2": tokens of the simple rasm (second index variant, no spans)}
    ohd:     {"c":"ohd","b":book_key,"n":num,"td":display_text (mushakkala, U+200F removed),
              "tp":plain_text_verbatim,"m":matn_start_token_index}
    hadeethenc: {"c":"hadeethenc","id":int,"title":str,"ht":hadith_text,"g":grade,"tk":takhrij,"u":link}

Invariants enforced here (build fails otherwise):
  * record counts equal manifest expectations;
  * for OHD, loose tokens of the plain file == loose tokens of the display file for every row
    (so indexing the display text is equivalent to indexing the plain text) — rows that differ
    are indexed from the plain text and counted in meta.json["ohd_display_plain_mismatch"];
  * Quran basmala offset is exactly 4 tokens on ayah 1 of every surah except 1 and 9.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "backend"))

from app.normalize import BASMALA_LOOSE, Token, tokenize  # noqa: E402

DATA = ROOT / "data"
INDEX = ROOT / "index"
MANIFEST = ROOT / "manifest.json"
RLM = "\u200f"

# Loose-token patterns whose END marks the most plausible start of the matn (R2, indexing aid only).
_MATN_MARKERS: tuple[tuple[str, ...], ...] = (
    ("قال", "رسول", "الله", "صلي", "الله", "عليه", "وسلم"),
    ("قال", "النبي", "صلي", "الله", "عليه", "وسلم"),
    ("رسول", "الله", "صلي", "الله", "عليه", "وسلم", "قال"),
    ("رسول", "الله", "صلي", "الله", "عليه", "وسلم", "يقول"),
    ("النبي", "صلي", "الله", "عليه", "وسلم", "قال"),
    ("النبي", "صلي", "الله", "عليه", "وسلم", "يقول"),
)
_MIN_MATN_TOKENS = 3


def _pack(tokens: list[Token]) -> dict[str, Any]:
    spans: list[int] = []
    for t in tokens:
        spans.append(t.start)
        spans.append(t.end)
    return {
        "L": " ".join(t.loose for t in tokens),
        "S": " ".join(t.strict for t in tokens),
        "P": spans,
    }


def matn_start(loose: list[str]) -> int:
    """Index of the first matn token according to the last marker occurrence; 0 if none."""
    best = 0
    n = len(loose)
    for pat in _MATN_MARKERS:
        k = len(pat)
        for i in range(n - k, -1, -1):
            if tuple(loose[i : i + k]) == pat:
                end = i + k
                if n - end >= _MIN_MATN_TOKENS and end > best:
                    best = end
                break
    return best


# --------------------------------------------------------------------------- Tanzil


def read_tanzil(path: Path) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            s, a, t = line.rstrip("\n").split("|", 2)
            out[(int(s), int(a))] = t
    return out


def build_tanzil(src_uth: dict[str, Any], src_sim: dict[str, Any]) -> list[dict[str, Any]]:
    uth = read_tanzil(DATA / src_uth["filename"])
    sim = read_tanzil(DATA / src_sim["filename"])
    if uth.keys() != sim.keys():
        raise SystemExit("tanzil: uthmani/simple key sets differ")
    records: list[dict[str, Any]] = []
    for (s, a), text_u in sorted(uth.items()):
        text_s = sim[(s, a)]
        tok_u = tokenize(text_u)
        tok_s = tokenize(text_s)
        offset = 0
        if a == 1 and s not in (1, 9):
            head_u = tuple(t.loose for t in tok_u[:4])
            head_s = tuple(t.loose for t in tok_s[:4])
            if head_u != BASMALA_LOOSE or head_s != BASMALA_LOOSE:
                raise SystemExit(f"tanzil {s}:{a}: expected basmala prefix, got {head_u} / {head_s}")
            offset = 4
        rec: dict[str, Any] = {"c": "tanzil", "s": s, "a": a, "tu": text_u, "ts": text_s, "o": offset}
        rec.update(_pack(tok_u))
        rec["L2"] = " ".join(t.loose for t in tok_s)
        rec["S2"] = " ".join(t.strict for t in tok_s)
        records.append(rec)
    if len(records) != src_uth["expected_records"]:
        raise SystemExit(f"tanzil: {len(records)} records != {src_uth['expected_records']}")
    return records


# --------------------------------------------------------------------------- OHD


def read_ohd_csv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            out[row[0]] = row[1]
    return out


def build_ohd(src: dict[str, Any], meta: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    mismatch = 0
    for book in src["books"]:
        plain = read_ohd_csv(DATA / "ohd" / book["dir"] / book["plain"])
        display = read_ohd_csv(DATA / "ohd" / book["dir"] / book["display"])
        if plain.keys() != display.keys():
            raise SystemExit(f"ohd/{book['key']}: plain/display numbering differs")
        for num_s, text_plain in plain.items():
            text_display = display[num_s].replace(RLM, "")
            tok_d = tokenize(text_display)
            tok_p = tokenize(text_plain)
            if [t.loose for t in tok_d] != [t.loose for t in tok_p]:
                mismatch += 1
                tokens = tok_p
                shown = text_plain  # fall back: highlight spans must point into the indexed text
            else:
                tokens = tok_d
                shown = text_display
            rec: dict[str, Any] = {
                "c": "ohd",
                "b": book["key"],
                "n": int(num_s),
                "td": shown,
                "tp": text_plain,
                "o": 0,
                "m": matn_start([t.loose for t in tokens]),
            }
            rec.update(_pack(tokens))
            records.append(rec)
        if len(plain) != book["expected_rows"]:
            raise SystemExit(f"ohd/{book['key']}: {len(plain)} rows != {book['expected_rows']}")
    meta["ohd_display_plain_mismatch"] = mismatch
    if len(records) != src["expected_records"]:
        raise SystemExit(f"ohd: {len(records)} != {src['expected_records']}")
    return records


# --------------------------------------------------------------------------- HadeethEnc


def build_hadeethenc(src: dict[str, Any]) -> list[dict[str, Any]]:
    import openpyxl  # noqa: PLC0415  (lazy: keep fetch/stdlib paths importable without openpyxl)

    wb = openpyxl.load_workbook(DATA / src["filename"], read_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    next(rows)  # comment block
    header = [str(h) for h in next(rows)]
    expected_header = ["id", "title", "hadith_text", "explanation", "word_meanings", "benefits", "grade", "takhrij", "link"]
    if header != expected_header:
        raise SystemExit(f"hadeethenc: unexpected header {header}")
    records: list[dict[str, Any]] = []
    for row in rows:
        d = dict(zip(header, row, strict=True))
        if d["id"] is None:
            continue
        title = str(d["title"] or "")
        ht = str(d["hadith_text"] or "")
        indexed = f"{title}\n{ht}"
        tokens = tokenize(indexed)
        rec: dict[str, Any] = {
            "c": "hadeethenc",
            "id": int(str(d["id"])),
            "title": title,
            "ht": ht,
            "td": indexed,
            "g": str(d["grade"] or ""),
            "tk": str(d["takhrij"] or ""),
            "u": str(d["link"] or ""),
            "o": 0,
        }
        rec.update(_pack(tokens))
        records.append(rec)
    if len(records) != src["expected_records"]:
        raise SystemExit(f"hadeethenc: {len(records)} != {src['expected_records']}")
    return records


# --------------------------------------------------------------------------- main


def main() -> int:
    t0 = time.time()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in manifest["sources"]}
    INDEX.mkdir(exist_ok=True)
    meta: dict[str, Any] = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    print("tanzil …")
    tanzil = build_tanzil(by_id["tanzil_uthmani"], by_id["tanzil_simple_clean"])
    print("ohd …")
    ohd = build_ohd(by_id["ohd"], meta)
    print("hadeethenc …")
    henc = build_hadeethenc(by_id["hadeethenc_ar"])

    out = INDEX / "records.jsonl"
    h = hashlib.sha256()
    with out.open("w", encoding="utf-8") as fh:
        for rec in (*tanzil, *ohd, *henc):
            line = json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n"
            fh.write(line)
            h.update(line.encode("utf-8"))
    meta.update(
        {
            "counts": {"tanzil": len(tanzil), "ohd": len(ohd), "hadeethenc": len(henc)},
            "versions": {
                "tanzil": by_id["tanzil_uthmani"]["version"],
                "ohd_commit": by_id["ohd"]["commit"],
                "hadeethenc": by_id["hadeethenc_ar"]["version"],
            },
            "records_sha256": h.hexdigest(),
            "records_bytes": out.stat().st_size,
            "build_seconds": round(time.time() - t0, 1),
        }
    )
    (INDEX / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
