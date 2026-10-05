#!/usr/bin/env python3
"""corpus/fetch.py — download every pinned source in manifest.json and verify it.

Usage:
    python corpus/fetch.py            # fetch what is missing, verify everything
    python corpus/fetch.py --verify   # verify only (no network)
    python corpus/fetch.py --only tanzil_uthmani ohd

Rules (see docs/adr/ADR-001, SOURCES policy):
  * Every file is verified against the sha256 pinned in manifest.json.
    Mismatch => non-zero exit, file renamed `*.MISMATCH`, build must fail.
  * TLS: downloads are verified normally. If (and only if) the server's
    certificate fails validation AND the file has a pinned sha256, the
    download is retried once without certificate verification and a loud
    warning is printed. Integrity is still guaranteed by the sha256 pin
    (the channel is untrusted, the content is not). `--strict-tls` disables
    this fallback. Unpinned sources (sha256: null) never fall back.
    Rationale: E-013 — tanzil.net served an expired certificate on 2026-10-01.
  * HadeethEnc has `sha256: null` (server re-exports). First fetch prints the
    hash so it can be pinned; until pinned a mismatch is a WARNING only.
  * Nothing is modified. Files are stored byte-exact under corpus/data/
    (git-ignored). Tanzil footer (licence) is kept inside the file.
  * Record counts are checked (expected_records / expected_rows) so a
    truncated download cannot pass silently.

Standard library only, so it runs before the backend venv exists.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
DATA = ROOT / "data"
USER_AGENT = "Basira-corpus-fetch/1.0 (+https://github.com/MoTechSys/Basira.ai)"
TIMEOUT_S = 120


class FetchError(RuntimeError):
    pass


class _Policy:
    """Process-wide download policy (set once from CLI args)."""

    strict_tls: bool = False


def _is_cert_error(exc: BaseException) -> bool:
    """True when the failure is a TLS *certificate* problem (expired, untrusted, hostname)."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, ssl.SSLCertVerificationError):
            return True
        if isinstance(cur, ssl.SSLError) and "CERTIFICATE_VERIFY_FAILED" in str(cur):
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stream_to(url: str, tmp: Path, *, context: ssl.SSLContext | None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=context) as resp, tmp.open("wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)


def download(url: str, dest: Path, *, pinned_sha256: str | None = None) -> None:
    """Download `url` to `dest` atomically.

    If TLS certificate validation fails and `pinned_sha256` is set (and
    `--strict-tls` is not), retry once with verification disabled and warn.
    The caller MUST verify `pinned_sha256` afterwards (handle_* do).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        try:
            _stream_to(url, tmp, context=None)
        except urllib.error.URLError as exc:
            if not (_is_cert_error(exc) and pinned_sha256 and not _Policy.strict_tls):
                raise
            print(
                f"  ! TLS certificate rejected for {url}\n"
                f"    ({exc.reason})\n"
                f"    retrying WITHOUT certificate verification; integrity relies on pinned sha256 "
                f"{pinned_sha256[:12]}… (use --strict-tls to forbid)",
                file=sys.stderr,
            )
            insecure = ssl.create_default_context()
            insecure.check_hostname = False
            insecure.verify_mode = ssl.CERT_NONE
            _stream_to(url, tmp, context=insecure)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        raise FetchError(f"download failed: {url}: {exc}") from exc
    tmp.replace(dest)


# --------------------------------------------------------------------------- counters


def count_tanzil(path: Path) -> int:
    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("|", 2)
            if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
                raise FetchError(f"{path.name}: malformed line: {line[:60]!r}")
            n += 1
    return n


def count_csv_rows(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as fh:
        return sum(1 for _ in csv.reader(fh))


def count_xlsx_rows(path: Path) -> int:
    """Count data rows of the first sheet without openpyxl (stdlib zip + xml scan).

    HadeethEnc layout: row 1 = comment block, row 2 = headers, rows 3.. = data.
    """
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet")]
        if not names:
            raise FetchError(f"{path.name}: no worksheet found")
        xml = zf.read(sorted(names)[0]).decode("utf-8", errors="replace")
    rows = len(re.findall(r"<row[ >]", xml))
    return max(rows - 2, 0)


# --------------------------------------------------------------------------- per-source


def handle_file_source(src: dict[str, Any], *, verify_only: bool) -> list[str]:
    """Single-file sources (Tanzil x2, HadeethEnc)."""
    problems: list[str] = []
    dest = DATA / src["filename"]
    if not dest.exists():
        if verify_only:
            return [f"{src['id']}: missing {dest.relative_to(ROOT)} (run without --verify)"]
        print(f"  ↓ {src['id']}: {src['url']}")
        download(src["url"], dest, pinned_sha256=src.get("sha256"))

    digest = sha256_of(dest)
    pinned = src.get("sha256")
    if pinned is None:
        print(f"  ! {src['id']}: sha256 not pinned — computed {digest}  (pin it in manifest.json)")
    elif digest != pinned:
        bad = dest.with_suffix(dest.suffix + ".MISMATCH")
        dest.replace(bad)
        problems.append(f"{src['id']}: sha256 MISMATCH expected {pinned} got {digest} → {bad.name}")
        return problems

    expected = src.get("expected_records")
    if expected is not None:
        if src["type"] == "quran_text":
            got = count_tanzil(dest)
        elif dest.suffix == ".xlsx":
            got = count_xlsx_rows(dest)
        else:
            got = count_csv_rows(dest)
        if got != expected:
            problems.append(f"{src['id']}: expected {expected} records, got {got}")
        else:
            print(f"  ✓ {src['id']}: {got} records, sha256 ok")
    return problems


def handle_ohd(src: dict[str, Any], *, verify_only: bool) -> list[str]:
    problems: list[str] = []
    base = src["raw_base"].rstrip("/")
    total = 0
    for book in src["books"]:
        bdir = DATA / "ohd" / book["dir"]
        for role in ("plain", "display"):
            fname = book[role]
            dest = bdir / fname
            if not dest.exists():
                if verify_only:
                    problems.append(f"ohd/{book['key']}: missing {fname}")
                    continue
                url = f"{base}/{book['dir']}/{fname}"
                print(f"  ↓ ohd/{book['key']}/{role}")
                download(url, dest, pinned_sha256=book.get(f"sha256_{role}"))
            pinned = book.get(f"sha256_{role}")
            digest = sha256_of(dest)
            if pinned and pinned != digest:
                problems.append(f"ohd/{book['key']}/{role}: sha256 MISMATCH")
                continue
            rows = count_csv_rows(dest)
            if rows != book["expected_rows"]:
                problems.append(
                    f"ohd/{book['key']}/{role}: expected {book['expected_rows']} rows, got {rows}"
                )
            if role == "plain":
                total += rows
    if not problems:
        if total != src["expected_records"]:
            problems.append(f"ohd: total rows {total} != {src['expected_records']}")
        else:
            print(f"  ✓ ohd: 9 books, {total} rows")
    return problems


# --------------------------------------------------------------------------- main


def load_manifest() -> dict[str, Any]:
    with MANIFEST.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true", help="verify existing files only; no network")
    ap.add_argument("--only", nargs="*", default=None, help="source ids to process")
    ap.add_argument(
        "--strict-tls",
        action="store_true",
        help="never fall back to an unverified TLS connection, even for sha256-pinned files",
    )
    args = ap.parse_args(argv)
    _Policy.strict_tls = bool(args.strict_tls)

    manifest = load_manifest()
    DATA.mkdir(exist_ok=True)
    problems: list[str] = []
    for src in manifest["sources"]:
        if args.only and src["id"] not in args.only:
            continue
        print(f"[{src['id']}]")
        try:
            if src["id"] == "ohd":
                problems += handle_ohd(src, verify_only=args.verify)
            else:
                problems += handle_file_source(src, verify_only=args.verify)
        except FetchError as exc:
            problems.append(str(exc))

    if problems:
        print("\nFAILED:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1
    print("\nall sources present and verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
