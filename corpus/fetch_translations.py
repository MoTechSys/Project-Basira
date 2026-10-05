#!/usr/bin/env python3
"""corpus/fetch_translations.py — English translations for the «English gate» (data layer only).

Usage:
    python3 corpus/fetch_translations.py              # fetch what is missing, verify, pin sha256 in manifest
    python3 corpus/fetch_translations.py --verify     # verify existing files against manifest (no network)
    python3 corpus/fetch_translations.py --repin      # accept an upstream change: overwrite pinned sha256
    python3 corpus/fetch_translations.py --only quranenc_english_saheeh hadeethenc_en

Sources (organizer's scientific package — no others):
  * QuranEnc API   https://quranenc.com/api/v1/translation/sura/{key}/{sura}
                   keys: english_saheeh (priority 1), english_rwwad (priority 2)
  * HadeethEnc API https://hadeethenc.com/api/v1/hadeeths/one/?language=en&id={id}
                   ids = the HadeethEnc ids already in our Arabic corpus (corpus/index/records.jsonl,
                   or the raw hadeethenc-ar.xlsx when the index is not built yet).

Output (git-ignored, under corpus/data/translations/):
  quranenc_english_saheeh.jsonl   one line per ayah: {"sura","aya","translation","footnotes"}  (6236 lines)
  quranenc_english_rwwad.jsonl    same                                                          (6236 lines)
  hadeethenc_en.jsonl             one line per hadith that HAS an English translation:
                                  {"id","title","hadeeth","hadeeth_intro","attribution","grade","link"}
  hadeethenc_en.missing.json      ids that returned 404 (no English translation) — kept so a re-run is
                                  reproducible and the gap is documented, not hidden.

Rules:
  * Texts are stored byte-exact as returned by the API (JSON-escaped, sort_keys, sorted by id/ayah) so the
    file bytes — and therefore the sha256 — are a pure function of upstream content.
  * manifest.json gets a top-level "translations" section (source, licence terms, version, date, sha256,
    record counts). The existing "sources" list is NOT modified; consumers that iterate it are unaffected.
  * On a later run, a sha256 that differs from the pin is an ERROR (upstream changed) unless --repin.
  * No modification of any text. No religious text enters git — only hashes and counts.
  * Standard library only (runs before the backend venv exists, like fetch.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
DATA = ROOT / "data"
OUT = DATA / "translations"
INDEX_RECORDS = ROOT / "index" / "records.jsonl"
AR_XLSX = DATA / "hadeethenc-ar.xlsx"
USER_AGENT = "Basira-corpus-fetch/1.0 (+https://github.com/MoTechSys/Basira.ai)"
TIMEOUT_S = 60
RETRIES = 4
QURAN_WORKERS = 4
HADITH_WORKERS = 8
N_SURAS = 114
EXPECTED_AYAT = 6236

QURANENC_LIST = "https://quranenc.com/api/v1/translations/list"
QURANENC_SURA = "https://quranenc.com/api/v1/translation/sura/{key}/{sura}"
HADEETHENC_ONE = "https://hadeethenc.com/api/v1/hadeeths/one/?language=en&id={id}"
HADEETHENC_BULK_EN = "https://hadeethenc.com/browse/download/en"
HADEETHENC_LINK = "https://hadeethenc.com/en/browse/hadith/{id}"

# Terms as published by each provider on 2026-10-03 (verbatim where quoted). Not our interpretation.
QURANENC_TERMS = (
    "QuranEnc.com publishes «free and trustworthy translations … accessible and shareable» (About page, "
    "read 2026-10-03; no separate licence page exists). Translation copyright remains with the issuing body "
    "named in `title`. Our use: retrieval + attributed, unmodified display of the matched ayah translation."
)
HADEETHENC_TERMS = (
    "HadeethEnc API docs (read 2026-10-03): «Contents of the project can be used, with the following terms and "
    "conditions: 1. No modification, addition, or deletion of the content. 2. Clearly referring to the publisher "
    "and the source (HadeethEnc.com).»"
)

QURAN_KEYS: tuple[tuple[str, int], ...] = (("english_saheeh", 1), ("english_rwwad", 2))


class FetchError(RuntimeError):
    pass


# --------------------------------------------------------------------------- http


def _get(url: str, *, timeout: int = TIMEOUT_S) -> bytes:
    """GET with a small, deterministic retry policy (network errors and 5xx only; 404 propagates)."""
    last: BaseException | None = None
    for attempt in range(RETRIES):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return bytes(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                raise
            last = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
        time.sleep(0.5 * (2**attempt))
    raise FetchError(f"GET failed after {RETRIES} attempts: {url}: {last}")


def _get_json(url: str) -> Any:
    return json.loads(_get(url).decode("utf-8"))


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    tmp.replace(path)


def _count_lines(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for _ in fh)


# --------------------------------------------------------------------------- QuranEnc


def quranenc_versions() -> dict[str, dict[str, Any]]:
    data = _get_json(QURANENC_LIST)
    items = data["translations"] if isinstance(data, dict) else data
    return {str(t["key"]): t for t in items}


def fetch_quran_key(key: str) -> list[dict[str, Any]]:
    def one(sura: int) -> list[dict[str, Any]]:
        payload = _get_json(QURANENC_SURA.format(key=key, sura=sura))
        rows = payload["result"] if isinstance(payload, dict) else payload
        out: list[dict[str, Any]] = []
        for r in rows:
            if int(r["sura"]) != sura:
                raise FetchError(f"quranenc {key}/{sura}: row claims sura {r['sura']}")
            out.append(
                {
                    "sura": int(r["sura"]),
                    "aya": int(r["aya"]),
                    "translation": str(r.get("translation") or ""),
                    "footnotes": str(r.get("footnotes") or ""),
                }
            )
        return out

    with ThreadPoolExecutor(QURAN_WORKERS) as ex:
        per_sura = list(ex.map(one, range(1, N_SURAS + 1)))
    rows = [r for chunk in per_sura for r in chunk]
    rows.sort(key=lambda r: (r["sura"], r["aya"]))
    if len(rows) != EXPECTED_AYAT:
        raise FetchError(f"quranenc {key}: {len(rows)} ayat != {EXPECTED_AYAT}")
    keys = {(r["sura"], r["aya"]) for r in rows}
    if len(keys) != EXPECTED_AYAT:
        raise FetchError(f"quranenc {key}: duplicate (sura, aya) pairs")
    empty = sum(1 for r in rows if not r["translation"].strip())
    if empty:
        raise FetchError(f"quranenc {key}: {empty} empty translations")
    return rows


# --------------------------------------------------------------------------- HadeethEnc


def _ids_from_index() -> list[int]:
    ids: list[int] = []
    with INDEX_RECORDS.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith('{"c":"hadeethenc"'):
                ids.append(int(json.loads(line)["id"]))
    return ids


def _ids_from_xlsx() -> list[int]:
    """Column A of the Arabic HadeethEnc workbook holds inline numeric ids (verified: 3582 numeric cells)."""
    with zipfile.ZipFile(AR_XLSX) as zf:
        names = sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet"))
        xml = zf.read(names[0]).decode("utf-8", errors="replace")
    ids: list[int] = []
    for attrs, value in re.findall(r'<c r="A\d+"([^>]*)><v>([^<]*)</v></c>', xml):
        if 't="s"' in attrs:  # shared string (header / comment rows)
            continue
        ids.append(int(float(value)))
    return ids


def hadeethenc_ids() -> list[int]:
    if INDEX_RECORDS.exists():
        ids = _ids_from_index()
        src = INDEX_RECORDS
    elif AR_XLSX.exists():
        ids = _ids_from_xlsx()
        src = AR_XLSX
    else:
        raise FetchError("no HadeethEnc ids: run corpus/fetch.py (and ideally build_index.py) first")
    ids = sorted(set(ids))
    print(f"  · {len(ids)} HadeethEnc ids from {src.relative_to(ROOT)}")
    return ids


def fetch_hadeethenc_en(ids: list[int]) -> tuple[list[dict[str, Any]], list[int]]:
    def one(i: int) -> dict[str, Any] | None:
        try:
            d = _get_json(HADEETHENC_ONE.format(id=i))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        if int(d["id"]) != i:
            raise FetchError(f"hadeethenc {i}: response id {d['id']}")
        return {
            "id": i,
            "title": str(d.get("title") or ""),
            "hadeeth": str(d.get("hadeeth") or ""),
            "hadeeth_intro": str(d.get("hadeeth_intro") or ""),
            "attribution": str(d.get("attribution") or ""),
            "grade": str(d.get("grade") or ""),
            "link": HADEETHENC_LINK.format(id=i),
        }

    with ThreadPoolExecutor(HADITH_WORKERS) as ex:
        results = list(ex.map(one, ids))
    rows = [r for r in results if r is not None]
    missing = [i for i, r in zip(ids, results, strict=True) if r is None]
    empty = sum(1 for r in rows if not r["hadeeth"].strip())
    if empty:
        raise FetchError(f"hadeethenc_en: {empty} rows with empty hadeeth text")
    return rows, missing


def hadeethenc_bulk_version() -> str | None:
    """Read «v1.25.0 (2026-05-10)»-style version from the bulk EN workbook's comment cell. Best effort."""
    try:
        blob = _get(HADEETHENC_BULK_EN, timeout=120)
        with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
            tmp.write(blob)
            tmp.flush()
            with zipfile.ZipFile(tmp.name) as zf:
                shared = zf.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
        m = re.search(r"Last update:\s*([0-9:\- ]+)\s*\((v[0-9.]+)\)", shared)
        return f"{m.group(2)} ({m.group(1).strip()})" if m else None
    except (FetchError, KeyError, zipfile.BadZipFile, OSError):
        return None


# --------------------------------------------------------------------------- manifest


def load_manifest() -> dict[str, Any]:
    with MANIFEST.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def save_manifest(m: dict[str, Any]) -> None:
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _section(m: dict[str, Any]) -> dict[str, Any]:
    sec = m.setdefault(
        "translations",
        {
            "note": (
                "English translations for the English gate (docs/ENGLISH_GATE.md). Fetched by "
                "corpus/fetch_translations.py; files live in corpus/data/translations/ (git-ignored). "
                "sha256 is pinned here; a changed upstream fails the fetch unless --repin."
            ),
            "items": [],
        },
    )
    assert isinstance(sec, dict)
    return sec


def _item(sec: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    for it in sec["items"]:
        if it["id"] == item_id:
            assert isinstance(it, dict)
            return it
    return None


def _upsert(sec: dict[str, Any], item: dict[str, Any]) -> None:
    for i, it in enumerate(sec["items"]):
        if it["id"] == item["id"]:
            sec["items"][i] = item
            return
    sec["items"].append(item)


def _pin(sec: dict[str, Any], item: dict[str, Any], path: Path, *, repin: bool) -> list[str]:
    digest = sha256_of(path)
    prev = _item(sec, item["id"])
    pinned = prev.get("sha256") if prev else None
    if pinned and pinned != digest and not repin:
        return [
            f"{item['id']}: sha256 changed upstream — pinned {pinned[:12]}… got {digest[:12]}… "
            f"(inspect, then re-run with --repin to accept)"
        ]
    item["sha256"] = digest
    item["downloaded_at"] = time.strftime("%Y-%m-%d", time.gmtime())
    _upsert(sec, item)
    return []


# --------------------------------------------------------------------------- per-source


def handle_quran(
    sec: dict[str, Any], key: str, priority: int, *, verify_only: bool, repin: bool
) -> list[str]:
    item_id = f"quranenc_{key}"
    dest = OUT / f"{item_id}.jsonl"
    prev = _item(sec, item_id)
    if verify_only:
        return _verify(prev, dest, item_id, EXPECTED_AYAT)
    if dest.exists() and prev and prev.get("sha256") == sha256_of(dest) and not repin:
        print(f"  ✓ {item_id}: present, sha256 ok ({_count_lines(dest)} ayat)")
        return []
    print(f"  ↓ {item_id}: 114 suras from {QURANENC_SURA.format(key=key, sura='{sura}')}")
    meta = quranenc_versions().get(key, {})
    rows = fetch_quran_key(key)
    _write_jsonl_atomic(dest, rows)
    item: dict[str, Any] = {
        "id": item_id,
        "kind": "quran",
        "source": "QuranEnc.com (Encyclopedia of the Noble Quran) — API",
        "api": QURANENC_SURA.format(key=key, sura="{sura}"),
        "key": key,
        "priority": priority,
        "title": str(meta.get("title") or ""),
        "version": str(meta.get("version") or ""),
        "upstream_last_update": time.strftime("%Y-%m-%d", time.gmtime(int(meta["last_update"])))
        if meta.get("last_update")
        else "",
        "license": QURANENC_TERMS,
        "license_url": "https://quranenc.com/en/home/about",
        "filename": str(dest.relative_to(DATA)),
        "expected_records": EXPECTED_AYAT,
        "records": len(rows),
        "modifications": "none (footnote markers like [2] are kept in the stored text; stripped only at tokenisation)",
    }
    problems = _pin(sec, item, dest, repin=repin)
    if not problems:
        print(f"  ✓ {item_id}: {len(rows)} ayat, v{item['version']}, sha256 {item['sha256'][:12]}…")
    return problems


def handle_hadeethenc(sec: dict[str, Any], *, verify_only: bool, repin: bool) -> list[str]:
    item_id = "hadeethenc_en"
    dest = OUT / f"{item_id}.jsonl"
    missing_path = OUT / f"{item_id}.missing.json"
    prev = _item(sec, item_id)
    if verify_only:
        return _verify(prev, dest, item_id, None)
    if dest.exists() and prev and prev.get("sha256") == sha256_of(dest) and not repin:
        print(f"  ✓ {item_id}: present, sha256 ok ({_count_lines(dest)} hadith)")
        return []
    ids = hadeethenc_ids()
    print(f"  ↓ {item_id}: {len(ids)} ids via {HADEETHENC_ONE.format(id='{id}')} ({HADITH_WORKERS} workers)")
    t0 = time.time()
    rows, missing = fetch_hadeethenc_en(ids)
    _write_jsonl_atomic(dest, rows)
    missing_path.write_text(json.dumps(missing) + "\n", encoding="utf-8")
    version = hadeethenc_bulk_version()
    item: dict[str, Any] = {
        "id": item_id,
        "kind": "hadith",
        "source": "HadeethEnc.com (Encyclopedia of Translated Prophetic Hadiths) — API, English",
        "api": HADEETHENC_ONE.format(id="{id}"),
        "key": "hadeethenc_en",
        "priority": 1,
        "version": version or "",
        "version_note": (
            "The API exposes no version; this string is read from the bulk EN workbook header at fetch time."
        ),
        "license": HADEETHENC_TERMS,
        "license_url": "https://hadeethenc.com/api-docs",
        "filename": str(dest.relative_to(DATA)),
        "ids_source": "HadeethEnc ids present in the Arabic corpus (manifest source hadeethenc_ar)",
        "ids_total": len(ids),
        "records": len(rows),
        "missing_english": len(missing),
        "missing_file": str(missing_path.relative_to(DATA)),
        "modifications": "none; `link` is constructed from the id (https://hadeethenc.com/en/browse/hadith/{id})",
    }
    problems = _pin(sec, item, dest, repin=repin)
    if not problems:
        print(
            f"  ✓ {item_id}: {len(rows)} with English, {len(missing)} without (404), "
            f"{time.time() - t0:.1f}s, sha256 {item['sha256'][:12]}…"
        )
    return problems


def _verify(prev: dict[str, Any] | None, dest: Path, item_id: str, expected: int | None) -> list[str]:
    if prev is None or not prev.get("sha256"):
        return [f"{item_id}: not pinned in manifest (run without --verify)"]
    if not dest.exists():
        return [f"{item_id}: missing {dest.relative_to(ROOT)} (run without --verify)"]
    digest = sha256_of(dest)
    if digest != prev["sha256"]:
        return [f"{item_id}: sha256 MISMATCH expected {prev['sha256']} got {digest}"]
    n = _count_lines(dest)
    want = expected if expected is not None else int(prev.get("records", n))
    if n != want:
        return [f"{item_id}: expected {want} records, got {n}"]
    print(f"  ✓ {item_id}: {n} records, sha256 ok")
    return []


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--verify", action="store_true", help="verify existing files against the manifest; no network"
    )
    ap.add_argument("--repin", action="store_true", help="re-download and accept a changed upstream sha256")
    ap.add_argument("--only", nargs="*", default=None, help="item ids to process")
    args = ap.parse_args(argv)

    manifest = load_manifest()
    sec = _section(manifest)
    OUT.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    jobs: list[tuple[str, Any]] = [
        (
            f"quranenc_{key}",
            lambda key=key, pr=pr: handle_quran(sec, key, pr, verify_only=args.verify, repin=args.repin),
        )
        for key, pr in QURAN_KEYS
    ]
    jobs.append(("hadeethenc_en", lambda: handle_hadeethenc(sec, verify_only=args.verify, repin=args.repin)))
    for item_id, fn in jobs:
        if args.only and item_id not in args.only:
            continue
        print(f"[{item_id}]")
        try:
            problems += fn()
        except (FetchError, urllib.error.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
            problems.append(f"{item_id}: {exc}")

    if not args.verify:
        sec["items"].sort(key=lambda it: (it["kind"], it["priority"], it["id"]))
        save_manifest(manifest)
    if problems:
        print("\nFAILED:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1
    print("\nall translations present and verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
