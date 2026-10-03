"""Loader for messages/{ar,en}.json + the forbidden-lexicon scanner (SAFETY §1.3, ADR-003).

The scanner is whole-word on normalized (loose) tokens so inflected forms
(«ضعيفة», «موضوعة», «الضعيف») are caught. Whitelisted: literal corpus fields,
manifest book names and the grade line (attributed quotation).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.normalize import loose_tokens

# Arabic stems (loose-normalized) — matched as whole tokens after stripping the definite article
# and common suffixes; see _forbidden_token().
_FORBIDDEN_AR_STEMS: frozenset[str] = frozenset(
    {
        "محرف",
        "مكذوب",
        "موضوع",
        "باطل",
        "ضعيف",
        "صحيح",
        "حسن",
        "بدعه",
        "حرام",
        "يجوز",
        "الراجح",
        "راجح",
        "فتوي",
        "مزيف",
        "مزيفه",
        "مضلل",
    }
)
_FORBIDDEN_AR_PHRASES: tuple[tuple[str, ...], ...] = (("لا", "اصل", "له"),)
_FORBIDDEN_EN = re.compile(
    r"\b(fabricated|fake|forged|weak|authentic|sahih|false|haram|fatwa|inauthentic|misleading)\b",
    re.IGNORECASE,
)
_AR_SUFFIXES = ("ات", "ان", "ين", "ون", "ه", "ا")


def _strip(token: str) -> str:
    if token.startswith("ال") and len(token) > 4:
        token = token[2:]
    return token


def _forbidden_token(token: str) -> bool:
    t = _strip(token)
    if t in _FORBIDDEN_AR_STEMS:
        return True
    for suf in _AR_SUFFIXES:
        if t.endswith(suf) and len(t) > len(suf) + 2 and t[: -len(suf)] in _FORBIDDEN_AR_STEMS:
            return True
    return False


# Proper nouns that contain a forbidden stem but are book titles, not judgments (E-009 whitelist).
_BOOK_NAME_PHRASES: tuple[tuple[str, ...], ...] = (
    ("صحيح", "البخاري"),
    ("صحيح", "مسلم"),
    ("الصحيحين",),
    ("الصحيحان",),
)
_BOOK_NAME_EN = re.compile(r"Sahih (al-Bukhari|Muslim)|the two Sahihs", re.IGNORECASE)


def _mask_book_names(toks: list[str]) -> list[str]:
    out = list(toks)
    for ph in _BOOK_NAME_PHRASES:
        k = len(ph)
        for i in range(len(out) - k + 1):
            if tuple(out[i : i + k]) == ph:
                for j in range(i, i + k):
                    out[j] = "\u0000"
    return out


def scan_forbidden(text: str) -> list[str]:
    """Return the offending tokens/phrases found in ``text`` (empty list = clean)."""
    hits: list[str] = []
    toks = _mask_book_names(loose_tokens(text))
    text = _BOOK_NAME_EN.sub(" ", text)
    for i, tok in enumerate(toks):
        if _forbidden_token(tok):
            hits.append(tok)
        for ph in _FORBIDDEN_AR_PHRASES:
            if tuple(toks[i : i + len(ph)]) == ph:
                hits.append(" ".join(ph))
    hits.extend(m.group(0) for m in _FORBIDDEN_EN.finditer(text))
    return hits


class Messages:
    def __init__(self, data: dict[str, dict[str, str]], lang: str) -> None:
        self._d = data
        self.lang = lang

    def get(self, section: str, key: str, **vars: Any) -> str:
        tpl = self._d[section][key]
        try:
            return tpl.format(**vars)
        except (KeyError, IndexError):
            return tpl

    def has(self, section: str, key: str) -> bool:
        return key in self._d.get(section, {})

    def all_templates(self) -> list[tuple[str, str, str]]:
        return [(s, k, v) for s, sec in self._d.items() if isinstance(sec, dict) for k, v in sec.items()]


@lru_cache(maxsize=4)
def load_messages(messages_dir: Path, lang: str) -> Messages:
    p = messages_dir / f"{lang}.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw.pop("$comment", None)
    return Messages(raw, lang)


def self_check_templates(messages_dir: Path) -> dict[str, list[str]]:
    """Every template must be clean of the forbidden lexicon (CI + startup check)."""
    problems: dict[str, list[str]] = {}
    for lang in ("ar", "en"):
        m = load_messages(messages_dir, lang)
        for section, key, tpl in m.all_templates():
            bad = scan_forbidden(tpl)
            if bad:
                problems[f"{lang}.{section}.{key}"] = bad
    return problems
