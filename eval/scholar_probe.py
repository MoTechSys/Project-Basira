"""Run eval/scholar_lens_cases.yaml against a live server (default http://localhost:8000). Exit 1 on any failure.

ملاحظة: يُشغَّل عبر Makefile (target: eval) أو مباشرة من سطر الأوامر.
جميع المسارات نسبية لجذر المستودع.
"""
"""Run eval/scholar_lens_cases.yaml against a live server (default http://localhost:8000). Exit 1 on any failure."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import yaml

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000") + "/v1/check"
cases = yaml.safe_load((Path(__file__).parent / "scholar_lens_cases.yaml").read_text(encoding="utf-8"))
fails = 0
for c in cases:
    req = urllib.request.Request(
        URL, data=json.dumps({"text": c["text"]}).encode(), headers={"Content-Type": "application/json"}
    )
    r = json.load(urllib.request.urlopen(req, timeout=30))
    qs = r["quotes"]
    errs: list[str] = []
    if c["status"] == "none":
        if qs:
            errs.append(f"expected no quotes, got {[q['status'] for q in qs]}")
    elif not qs:
        errs.append("no quotes")
    else:
        q = qs[0]
        if q["status"] != c["status"]:
            errs.append(f"status {q['status']} != {c['status']}")
        for n in c.get("notices", []):
            if n not in q["notice_keys"]:
                errs.append(f"missing notice {n}")
        for n in c.get("absent", []):
            if n in q["notice_keys"]:
                errs.append(f"unexpected notice {n}")
        if "mismatch" in c and q["claimed_source_mismatch"] != c["mismatch"]:
            errs.append("claimed_source_mismatch flag wrong")
        if "ref" in c and (not q["matches"] or q["matches"][0]["ref"] != c["ref"]):
            errs.append(f"ref {q['matches'][0]['ref'] if q['matches'] else None} != {c['ref']}")
        if "message_key" in c and q["message_key"] != c["message_key"]:
            errs.append(f"message_key {q['message_key']}")
        if "total_positions" in c and q["total_positions"] != c["total_positions"]:
            errs.append(f"total_positions {q['total_positions']}")
        if "quotes" in c and len(qs) != c["quotes"]:
            errs.append(f"{len(qs)} quotes != {c['quotes']}")
    mark = "PASS" if not errs else "FAIL"
    fails += bool(errs)
    print(f"[{mark}] {c['id']} {c['text'][:48]!r} {'; '.join(errs)}")
print(f"\n{len(cases) - fails}/{len(cases)} passed")
sys.exit(1 if fails else 0)
