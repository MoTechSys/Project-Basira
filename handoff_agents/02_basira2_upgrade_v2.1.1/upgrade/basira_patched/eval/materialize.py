"""Turn a declarative eval case into a concrete user text + expectations — WITHOUT writing religious text.

A case never contains Quran/Hadith text. It points at a corpus record and a token window; the
quote is cut from the record at run time (``text_simple`` for Quran — what users actually type —
or the display field for hadith). Optional *mutations* are mechanical edits (drop/duplicate/swap a
token, substitute a token taken from ANOTHER corpus record, or an orthographic fold such as ى→ي)
so the expected outcome is known by construction. The *wrapper* (the surrounding post) is plain
prose written by the engineer and contains no religious text.

Mutation catalogue (all deterministic):
  none                    — verbatim window                                  → found
  ortho:<kind>            — loose-preserving, strict-breaking character fold  → needs_review/orthographic_difference
                            kinds: ya2alef_maqsura (ي→ى), ta2ha (ة→ه), hamza_drop (أإآ→ا), ha2ta (ه→ة)
  drop:<k>                — delete token k (0-based inside the window)
  dup:<k>                 — duplicate token k
  swap:<k>                — swap tokens k and k+1
  subst:<k>:<corpus>:<ref…>:<j> — replace token k with token j of another record (surface form)
  multi:<m1>|<m2>|…       — apply several mutations in order
Source option ``join_next`` appends a window of another record (cross-ayah quotes).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.normalize import tokenize  # noqa: E402
from app.store import Record, Store  # noqa: E402

_ORTHO = {
    "ya2alef_maqsura": ("\u064a", "\u0649"),  # ي → ى   (loose both → ي)
    "ta2ha": ("\u0629", "\u0647"),  # ة → ه
    "ha2ta": ("\u0647", "\u0629"),  # ه → ة   (only at token end)
    "hamza_drop": ("\u0623\u0625\u0622", "\u0627"),  # أ إ آ → ا
}


@dataclass(slots=True)
class Materialized:
    case_id: str
    category: str
    text: str
    quote: str
    expect: dict[str, Any]
    notes: list[str] = field(default_factory=list)


def _surface_tokens(rec: Record) -> list[str]:
    base = rec.text_simple if rec.corpus == "tanzil" else rec.display
    toks = tokenize(base)
    return [base[t.start : t.end] for t in toks]


def _lookup(store: Store, src: dict[str, Any]) -> Record:
    c = src["corpus"]
    if c == "tanzil":
        rec = store.lookup("tanzil", surah=int(src["surah"]), ayah=int(src["ayah"]))
    elif c == "ohd":
        rec = store.lookup("ohd", book=str(src["book"]), num=int(src["num"]))
    else:
        rec = store.lookup("hadeethenc", id=int(src["id"]))
    if rec is None:
        raise KeyError(f"record not in store: {src}")
    return rec


def window_tokens(store: Store, src: dict[str, Any]) -> list[str]:
    rec = _lookup(store, src)
    toks = _surface_tokens(rec)
    a, b = src.get("tokens", [0, len(toks)])
    if rec.corpus == "tanzil" and a < rec.offset:
        a = rec.offset  # never cut inside the display-only basmala
    out = toks[a:b]
    if not out:
        raise ValueError(f"empty window {src}")
    return out


def _apply_ortho(tokens: list[str], kind: str) -> list[str]:
    src_chars, dst = _ORTHO[kind]
    out: list[str] = []
    changed = False
    for t in tokens:
        if changed:
            out.append(t)
            continue
        if kind == "ha2ta":
            if t.endswith("\u0647") and len(t) > 2:
                out.append(t[:-1] + dst)
                changed = True
                continue
            out.append(t)
            continue
        if kind == "ya2alef_maqsura":
            if t.endswith("\u064a") and len(t) > 2:
                out.append(t[:-1] + dst)
                changed = True
                continue
            out.append(t)
            continue
        new = t
        for ch in src_chars:
            new = new.replace(ch, dst)
        if new != t:
            changed = True
        out.append(new)
    if not changed:
        raise ValueError(f"ortho mutation {kind} had no effect")
    return out


def mutate(store: Store, tokens: list[str], mutation: str | None) -> tuple[list[str], str]:  # noqa: PLR0911
    """Return (tokens, applied_description)."""
    if not mutation or mutation == "none":
        return tokens, "none"
    kind, _, rest = mutation.partition(":")
    toks = list(tokens)
    if kind == "multi":  # multi:drop:1|swap:2|subst:...
        for part in rest.split("|"):
            toks, _ = mutate(store, toks, part)
        return toks, mutation
    if kind == "ortho":
        return _apply_ortho(toks, rest), mutation
    if kind == "drop":
        k = int(rest)
        del toks[k]
        return toks, mutation
    if kind == "dup":
        k = int(rest)
        toks.insert(k, toks[k])
        return toks, mutation
    if kind == "swap":
        k = int(rest)
        toks[k], toks[k + 1] = toks[k + 1], toks[k]
        return toks, mutation
    if kind == "subst":
        parts = rest.split(":")
        k = int(parts[0])
        corpus = parts[1]
        if corpus == "tanzil":
            src = {"corpus": "tanzil", "surah": parts[2], "ayah": parts[3]}
            j = int(parts[4])
        elif corpus == "ohd":
            src = {"corpus": "ohd", "book": parts[2], "num": parts[3]}
            j = int(parts[4])
        else:
            src = {"corpus": "hadeethenc", "id": parts[2]}
            j = int(parts[3])
        donor = _surface_tokens(_lookup(store, src))
        if donor[j] == toks[k]:
            raise ValueError("subst donor token identical")
        toks[k] = donor[j]
        return toks, mutation
    raise ValueError(f"unknown mutation {mutation!r}")


def materialize(store: Store, case: dict[str, Any]) -> Materialized:
    notes: list[str] = []
    if "source" in case:
        toks = window_tokens(store, case["source"])
        nxt = case["source"].get("join_next")
        if nxt:
            toks = toks + window_tokens(store, nxt)
        toks, applied = mutate(store, toks, case.get("mutation"))
        quote = " ".join(toks)
        notes.append(f"mutation={applied}; n_tokens={len(toks)}")
    else:
        quote = case.get("literal", "")  # only for non-religious literals (category J/K/L wrappers)
    text = case["wrapper"].replace("{q}", quote)
    return Materialized(case["id"], case["category"], text, quote, dict(case.get("expect", {})), notes)
