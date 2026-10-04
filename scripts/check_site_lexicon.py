#!/usr/bin/env python3
"""Run the backend's forbidden-lexicon scanner (app.messages.scan_forbidden) over every frontend chrome
string (src/i18n.ts UI + src/site/strings.ts). Exit 1 on any hit. Used by `make site-lexicon`."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.messages import scan_forbidden  # noqa: E402

FILES = [ROOT / "frontend/src/site/strings.ts", ROOT / "frontend/src/i18n.ts"]
STR = re.compile(r'^\s*(\w+):\s*\n?\s*"((?:[^"\\]|\\.)*)"', re.M)


def main() -> int:
    hits = 0
    n = 0
    for f in FILES:
        for m in STR.finditer(f.read_text(encoding="utf-8")):
            key, val = m.group(1), m.group(2)
            n += 1
            found = scan_forbidden(val)
            if found:
                hits += 1
                print(f"{f.name}:{key}: {found} :: {val}")
    print(f"scanned {n} strings, {hits} with forbidden vocabulary")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
