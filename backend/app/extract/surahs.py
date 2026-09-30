"""Surah name lookup (dictionary, deterministic) from corpus/surah_names.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.normalize import loose_join

_ALIASES: dict[str, int] = {
    "ال عمران": 3,
    "عمران": 3,
    "بني اسراييل": 17,
    "الاسراء": 17,
    "المومنون": 23,
    "المومنين": 23,
    "غافر": 40,
    "المومن": 40,
    "الشرح": 94,
    "الانشراح": 94,
    "الاخلاص": 112,
    "التوحيد": 112,
    "براءه": 9,
    "الكافرون": 109,
    "الكافرين": 109,
    "الانسان": 76,
    "الدهر": 76,
    "الملك": 67,
    "تبارك": 67,
    "فاطر": 35,
    "الملايكه": 35,
}


@lru_cache(maxsize=1)
def _table() -> tuple[dict[int, tuple[str, str]], dict[str, int]]:
    p = settings.manifest_path.parent / "surah_names.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    names: dict[int, tuple[str, str]] = {}
    lookup: dict[str, int] = dict(_ALIASES)
    for k, v in raw.items():
        n = int(k)
        names[n] = (v["ar"], v["en"])
        lookup[loose_join(v["ar"])] = n
        lookup[v["en"].lower().replace("'", "").replace("-", " ")] = n
        # without the definite article
        ar = loose_join(v["ar"])
        if ar.startswith("ال") and len(ar) > 3:
            lookup[ar[2:]] = n
    return names, lookup


def surah_number(name: str) -> int | None:
    _, lookup = _table()
    key = loose_join(name)
    if key in lookup:
        return lookup[key]
    key_en = name.strip().lower().replace("'", "").replace("-", " ")
    return lookup.get(key_en)


def surah_name(n: int, lang: str) -> str:
    names, _ = _table()
    ar, en = names.get(n, (str(n), str(n)))
    return ar if lang == "ar" else en


def surah_names_path() -> Path:
    return settings.manifest_path.parent / "surah_names.json"
