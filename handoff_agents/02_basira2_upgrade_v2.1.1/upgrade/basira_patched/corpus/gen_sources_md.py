#!/usr/bin/env python3
"""Regenerate SOURCES.md from corpus/manifest.json (the competition's «سجل المصادر»)."""
from __future__ import annotations

import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    m = json.loads((ROOT / "corpus" / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for s in m["sources"]:
        sha = s.get("sha256") or ("per-book" if s.get("books") else "—")
        rows.append(
            f"| **{s['name']}** | `{s['id']}` | {s.get('version') or s.get('commit', '')} | {s.get('license', '')} | "
            f"[license]({s.get('license_url', '')}) | {s.get('purpose', '')} | {s.get('modifications', 'none')} | "
            f"`{sha[:16]}…` | {s.get('downloaded_at', '')} |"
        )
    books = ""
    for s in m["sources"]:
        if s.get("books"):
            books += f"\n### {s['name']} — books (commit `{s['commit']}`)\n\n| key | الاسم | tier | rows | sha256 (plain) |\n|---|---|---|---|---|\n"
            for b in s["books"]:
                books += f"| `{b['key']}` | {b['name_ar']} | {b['tier']} | {b['expected_rows']} | `{b['sha256_plain'][:16]}…` |\n"
            if s.get("upstream"):
                books += f"\n**Chain of title:** {s['upstream']}\n"
            books += f"\n**Numbering:** {s.get('numbering', '')}\n"
    tmpl = (ROOT / "SOURCES.md").read_text(encoding="utf-8")
    head = tmpl.split("## المصادر")[0]
    tail = "## ما لا نفعله بالمصادر" + tmpl.split("## ما لا نفعله بالمصادر")[1].rsplit("---", 1)[0]
    out = (
        head
        + "## المصادر\n\n| المصدر | id | الإصدار | الرخصة | رابط | الاستخدام | التعديلات | sha256 | تاريخ التنزيل |\n|---|---|---|---|---|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n"
        + books
        + "\n"
        + tail
        + f"---\n*Generated {datetime.date.today().isoformat()} from manifest schema v{m.get('$schema_version')}.*\n"
    )
    (ROOT / "SOURCES.md").write_text(out, encoding="utf-8")
    print("SOURCES.md regenerated")


if __name__ == "__main__":
    main()
