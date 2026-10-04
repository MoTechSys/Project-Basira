#!/usr/bin/env python3
"""scripts/mcp_demo.py — live demo of Basira's MCP server, and of how it complements a retrieval MCP server.

    # terminal 1
    cd backend && BASIRA_MCP=1 .venv/bin/uvicorn app.main:app --port 8000
    # terminal 2
    backend/.venv/bin/python scripts/mcp_demo.py [--url http://localhost:8000/mcp] [--no-remote]

Part 1 — Basira (local):  tools/list, grounding_rules, verify_text on three canonical cases, guard_answer.
Part 2 — integration (optional, needs internet): call `get_quran_verses` on the Islamic Content
Association's retrieval server (https://mcp.islamiccontent.org/mcp), take the verse text it returns, and
pass it to Basira's verify_text — the retrieval server fetches the text, Basira confirms the text in hand
is that text. Any failure in Part 2 is reported and skipped; Part 1 never depends on it.

Prints exactly what the tools return (trimmed source_text for the terminal). Nothing is stored.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

LOCAL = "http://localhost:8000/mcp"
REMOTE = "https://mcp.islamiccontent.org/mcp"
CASES = [
    "قال تعالى: ﴿إن الله مع الصابرين﴾",
    "قال تعالى: ﴿قل هو HELLO الله أحد﴾.",
    "قال ﷺ: «الدين المعاملة»",
]


def _short(s: str, n: int = 70) -> str:
    return s if len(s) <= n else s[:n] + "…"


def _print_quotes(result: dict[str, Any]) -> None:
    for q in result.get("quotes", []):
        m = q["matches"][0] if q["matches"] else None
        ref = f"{m['ref_label']}" if m else "—"
        print(f"    • {q['status']:<13} {q['kind']:<12} reason={q['review_reason']}  {ref}")
        if m:
            print(f"      source_text: {_short(m['source_text'])}")
        for n in q.get("notices", [])[:2]:
            print(f"      notice: {_short(n, 110)}")


async def _call(session: ClientSession, name: str, args: dict[str, Any]) -> dict[str, Any]:
    res = await session.call_tool(name, args)
    if getattr(res, "is_error", False):
        text = res.content[0].text if res.content and hasattr(res.content[0], "text") else ""
        raise RuntimeError(f"{name}: tool error {text}")
    sc = getattr(res, "structured_content", None)
    if isinstance(sc, dict):
        return sc
    # fallback: first text block as JSON
    text = res.content[0].text if res.content and hasattr(res.content[0], "text") else "{}"
    out: dict[str, Any] = json.loads(text)
    return out


async def part1(url: str) -> dict[str, Any]:
    print(f"== Part 1: Basira MCP at {url}")
    async with streamable_http_client(url) as (read, write, *_), ClientSession(read, write) as s:
        init = await s.initialize()
        print(f"  server: {init.server_info.name} v{init.server_info.version}")
        tools = await s.list_tools()
        print(f"  tools/list: {[t.name for t in tools.tools]}")
        rules = await _call(s, "grounding_rules", {"ui_lang": "en"})
        print(f"  grounding_rules: states={rules['states']} safety_sha256={rules['safety_sha256'][:12]}…")
        hashes: dict[str, str] = {}
        for text in CASES:
            r = await _call(s, "verify_text", {"text": text, "ui_lang": "ar"})
            hashes[text] = r["determinism_hash"]
            print(f"  verify_text({_short(text, 40)!r}) → hash {r['determinism_hash'][:12]}…")
            _print_quotes(r)
        r2 = await _call(s, "verify_text", {"text": CASES[0], "ui_lang": "ar"})
        print(f"  determinism: second call hash equal = {r2['determinism_hash'] == hashes[CASES[0]]}")
        g = await _call(s, "guard_answer", {"answer": " ".join(CASES), "ui_lang": "en"})
        print(f"  guard_answer → {g['verdict']} {g['counts']}")
        print(f"    {g['summary_en']}")
        return {"hashes": hashes}


async def part2(local_url: str) -> None:
    print(f"== Part 2: integration with {REMOTE}")
    try:
        async with streamable_http_client(REMOTE) as (r, w, *_), ClientSession(r, w) as remote:
            await remote.initialize()
            tools = await remote.list_tools()
            names = [t.name for t in tools.tools]
            print(f"  remote tools ({len(names)}): {names}")
            if "get_quran_verses" not in names:
                print("  get_quran_verses not offered — skipping")
                return
            tool = next(t for t in tools.tools if t.name == "get_quran_verses")
            print(
                f"  get_quran_verses input schema keys: {list(tool.input_schema.get('properties', {}).keys())}"
            )
            args = _guess_args(tool.input_schema)
            print(f"  calling get_quran_verses({args})")
            res = await remote.call_tool("get_quran_verses", args)
            payload = getattr(res, "structured_content", None)
            raw = payload if payload is not None else [c.text for c in res.content if hasattr(c, "text")]
            text = json.dumps(raw, ensure_ascii=False)
            print(f"  remote returned {len(text)} chars: {_short(text, 160)}")
            arabic = _first_arabic(raw)
            if not arabic:
                print("  no Arabic verse text found in the remote payload — skipping verify")
                return
            print(f"  verse text → Basira: {_short(arabic, 60)!r}")
    except Exception as exc:  # network / protocol — reported, never fatal
        print(f"  remote unavailable: {exc.__class__.__name__}: {_short(str(exc), 160)}")
        return
    async with streamable_http_client(local_url) as (r, w, *_), ClientSession(r, w) as local:
        await local.initialize()
        out = await _call(local, "verify_text", {"text": f"قال تعالى: ﴿{arabic}﴾", "ui_lang": "en"})
        _print_quotes(out)
        print(f"  determinism_hash {out['determinism_hash'][:12]}…")


def _guess_args(schema: dict[str, Any]) -> dict[str, Any]:
    """Arguments for Al-Baqarah 2:153. The remote schema (read 2026-10-03) is
    {surah (required), ayah, through, translation_key, language}; fall back to name heuristics if it changes."""
    props: dict[str, Any] = schema.get("properties", {})
    if {"surah", "ayah"} <= props.keys():
        args: dict[str, Any] = {"surah": 2, "ayah": 153}
        if "through" in props:
            args["through"] = 153
        if "translation_key" in props:
            args["translation_key"] = "english_saheeh"
        return args
    args = {}
    for key in props:
        k = key.lower()
        if "surah" in k or "chapter" in k:
            args[key] = 2
        elif "ayah" in k or "verse" in k:
            args[key] = 153
    return args


def _first_arabic(obj: Any) -> str | None:
    import re  # noqa: PLC0415

    ar = re.compile(r"[\u0621-\u064A][\u0600-\u06FF\s]{15,}")
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, str):
            m = ar.search(cur)
            if m:
                return m.group(0).strip()
        elif isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=LOCAL)
    ap.add_argument("--no-remote", action="store_true")
    a = ap.parse_args()
    asyncio.run(part1(a.url))
    if not a.no_remote:
        asyncio.run(part2(a.url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
