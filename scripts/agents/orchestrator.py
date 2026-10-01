#!/usr/bin/env python3
"""scripts/agents/orchestrator.py — multi-model sub-agent runner for the Basira team.

Implements docs/TEAM.md + docs/model-analysis/06-roster-decision.md:
  * one role -> one frontier model -> max reasoning
  * shared Semaphore(18) under the measured platform cap of 20 in-flight/user
  * exponential backoff on HTTP 429
  * red lines injected into EVERY system prompt as non-negotiable constraints
  * outputs written to .scratch/agents/<run>/<role>.md (git-ignored) — only
    verified artefacts are ever committed by the orchestrating engineer.

Usage (library):
    from scripts.agents.orchestrator import run_role, run_many
    out = asyncio.run(run_role("architect", brief_text, files=["backend/app/state.py"]))

Usage (CLI smoke):
    python3 scripts/agents/orchestrator.py --selftest

Stdlib + httpx only (httpx is preinstalled in the sandbox).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".scratch" / "agents"

# --------------------------------------------------------------------------- platform facts (measured 2026-10-01)
PLATFORM_CONCURRENCY_CAP = 20  # "Too many concurrent requests. Maximum 20 allowed per user."
SAFE_CONCURRENCY = 18
MAX_RETRIES_429 = 4

ANTHROPIC_URL = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/") + "/v1/messages"
OPENAI_URL = os.environ.get("OPENAI_BASE_URL", "").rstrip("/") + "/chat/completions"


def _require_env() -> None:
    missing = [k for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_KEY") if not os.environ.get(k)]
    if missing:
        sys.exit(f"missing env: {missing} — inject LLM keys from the Genspark project (API Keys → Inject)")


# --------------------------------------------------------------------------- red lines (always injected)
RED_LINES = """\
NON-NEGOTIABLE CONSTRAINTS (project Basira — do not argue with these; if you disagree, state it in one line and comply):
1. Never generate, complete, paraphrase or "correct" Quran or Hadith text. Religious text is displayed byte-exact from the corpus by ID.
2. Never grade a hadith or ayah. Never produce the words صحيح / ضعيف / موضوع / محرّف / مكذوب / لا أصل له or their English equivalents as judgments. "Not found in our sources" is not a judgment.
3. Never reference or reproduce content from .intake/ or docs/internal/ (confidential organizer material).
4. Output must be verifiable: code must compile and be accompanied by tests; claims must cite file:line or a URL with a quoted excerpt.
5. If the brief is ambiguous, list assumptions explicitly instead of guessing silently.
"""


@dataclass(frozen=True)
class RoleSpec:
    model: str
    family: str  # "anthropic" | "openai"
    reasoning: dict[str, Any]
    system: str


# docs/model-analysis/06-roster-decision.md
ROSTER: dict[str, RoleSpec] = {
    "architect": RoleSpec(
        "claude-opus-5-5", "anthropic", {"thinking": {"type": "enabled", "budget_tokens": 16000}},
        "You are the chief architect and core author. Produce a unified diff plus a short rationale and an explicit list of assumptions. No prose outside those three sections.",
    ),
    "author2": RoleSpec(
        "claude-fable-5-1", "anthropic", {"thinking": {"type": "enabled", "budget_tokens": 16000}},
        "You are the second author working on an independent track (eval, frontend). Same output contract: diff, rationale, assumptions.",
    ),
    "reviewer": RoleSpec(
        "gpt-6-astra", "openai", {"reasoning_effort": "xhigh"},
        "You are an adversarial code reviewer from a different model family. Return a findings table: severity | file:line | issue | concrete fix. If the table is empty, list exactly what you checked. Do not propose relaxing the constraints above.",
    ),
    "tester": RoleSpec(
        "gpt-6.1-sol", "openai", {"reasoning_effort": "xhigh"},
        "You are the test engineer. Produce pytest code that tries to break the artefact: boundary values, adversarial inputs, property tests. Tests must be runnable as-is.",
    ),
    "safety": RoleSpec(
        "claude-opus-5-5", "anthropic", {"thinking": {"type": "enabled", "budget_tokens": 16000}},
        "You are the Sharia-safety and messages auditor. Flag any user-facing string that states or IMPLIES a religious judgment, generates religious text, or leaks confidential material. Return a table: string | location | problem | safe rewrite.",
    ),
    "research": RoleSpec(
        "claude-opus-5-5", "anthropic", {"thinking": {"type": "enabled", "budget_tokens": 16000}},
        "You are the research analyst. Every claim MUST carry a URL and a verbatim quoted excerpt. Mark vendor-reported vs independent. No claim without a source.",
    ),
    "risk": RoleSpec(
        "gpt-6-astra", "openai", {"reasoning_effort": "xhigh"},
        "You are the risk officer. Enumerate failure modes as a register: id | risk | likelihood | impact | mitigation | owner | detection signal.",
    ),
    "docs": RoleSpec(
        "claude-opus-5-5", "anthropic", {"thinking": {"type": "enabled", "budget_tokens": 8000}},
        "You are the delivery-docs writer. Clear, key information first, follow the project's writing rules. The project is the owner's work; AI systems are tools used by the owner (never phrase otherwise).",
    ),
    "evalgen": RoleSpec(
        "claude-fable-5-1", "anthropic", {"thinking": {"type": "enabled", "budget_tokens": 8000}},
        "You generate evaluation cases as YAML. Never write Quran/Hadith text yourself: reference corpus records by ID and describe the user-post wrapper only.",
    ),
}

_SEM = asyncio.Semaphore(SAFE_CONCURRENCY)


@dataclass
class AgentResult:
    role: str
    model: str
    ok: bool
    text: str
    seconds: float
    attempts: int
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _attach(files: list[str] | None) -> str:
    if not files:
        return ""
    parts = ["\n\n--- ATTACHED FILES (read-only context) ---"]
    for f in files:
        p = ROOT / f
        body = p.read_text(encoding="utf-8") if p.exists() else f"<missing: {f}>"
        parts.append(f"\n### {f}\n```\n{body}\n```")
    return "\n".join(parts)


async def _post(client: httpx.AsyncClient, spec: RoleSpec, system: str, user: str) -> tuple[int, dict[str, Any]]:
    if spec.family == "anthropic":
        body: dict[str, Any] = {"model": spec.model, "max_tokens": 32000, "system": system, "messages": [{"role": "user", "content": user}], **spec.reasoning}
        r = await client.post(ANTHROPIC_URL, headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}, json=body)
    else:
        body = {"model": spec.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], **spec.reasoning}
        r = await client.post(OPENAI_URL, headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}, json=body)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"raw": r.text[:500]}


def _extract(spec: RoleSpec, d: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if spec.family == "anthropic":
        text = "\n".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    else:
        text = d.get("choices", [{}])[0].get("message", {}).get("content", "")
    return text, d.get("usage", {})


async def run_role(role: str, brief: str, files: list[str] | None = None, *, client: httpx.AsyncClient | None = None, run_id: str | None = None) -> AgentResult:
    """Run one role once. Honors the shared semaphore and 429 backoff."""
    _require_env()
    spec = ROSTER[role]
    system = RED_LINES + "\n" + spec.system
    user = brief + _attach(files)
    own = client is None
    client = client or httpx.AsyncClient(timeout=900)
    t0 = time.perf_counter()
    attempts = 0
    try:
        async with _SEM:
            while True:
                attempts += 1
                code, d = await _post(client, spec, system, user)
                if code == 429 and attempts < MAX_RETRIES_429:
                    await asyncio.sleep(0.5 * 2 ** (attempts - 1))
                    continue
                break
        if code != 200:
            res = AgentResult(role, spec.model, False, "", time.perf_counter() - t0, attempts, error=f"HTTP {code}: {json.dumps(d)[:300]}")
        else:
            text, usage = _extract(spec, d)
            res = AgentResult(role, spec.model, True, text, time.perf_counter() - t0, attempts, usage)
    finally:
        if own:
            await client.aclose()
    if run_id:
        out = OUT_DIR / run_id
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{role}.md").write_text(f"# {role} — {spec.model}\n\n{res.text or res.error}\n", encoding="utf-8")
        (out / f"{role}.meta.json").write_text(json.dumps({k: v for k, v in res.__dict__.items() if k != "text"}, indent=1), encoding="utf-8")
    return res


async def run_many(jobs: Sequence[tuple[str, str, list[str] | None]], run_id: str) -> list[AgentResult]:
    """Run many (role, brief, files) jobs concurrently under the shared cap."""
    async with httpx.AsyncClient(timeout=900) as c:
        return list(await asyncio.gather(*[run_role(r, b, f, client=c, run_id=run_id) for r, b, f in jobs]))


# --------------------------------------------------------------------------- self-test
async def _selftest() -> int:
    brief = "Reply with exactly one line: ROLE_OK <your model id as you know it>. Do not add anything else."
    jobs = [(r, brief, None) for r in ROSTER]
    res = await run_many(jobs, run_id=f"selftest-{int(time.time())}")
    bad = 0
    for r in res:
        flag = "✓" if r.ok and r.text.strip() else "✗"  # reachability only; role prompts may legitimately reshape the reply
        bad += flag == "✗"
        print(f"{flag} {r.role:10} {r.model:18} {r.seconds:5.1f}s attempts={r.attempts} {(r.text or r.error or '')[:60]!r}")
    print(f"{len(res) - bad}/{len(res)} roles OK")
    return 0 if bad == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true", help="ping every role's model once through the semaphore")
    args = ap.parse_args(argv)
    if args.selftest:
        return asyncio.run(_selftest())
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
