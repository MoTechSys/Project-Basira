"""Fixed templates for the Guard summaries (docs/GUARD.md). Deliberately NOT in messages/*.json
(owned by another engineer); same discipline: no word of the forbidden lexicon, no religious text,
no judgment. Every template is scanned by ``app.messages.scan_forbidden`` in tests.

Variables: ``{n}`` total quotations, ``{k}`` quotations that are not ``found``, ``{found}`` found count.
Arabic uses the dual/plural-neutral form «اقتباسًا/اقتباسات» chosen by ``arabic_count``.
"""

from __future__ import annotations

Verdict = str  # "clear" | "flagged" | "no_quotes"

TEMPLATES: dict[str, dict[str, str]] = {
    "ar": {
        "no_quotes": "لم نجد في الإجابة اقتباسًا قرآنيًّا أو حديثيًّا يمكن التحقق منه.",
        "clear": "في الإجابة {n_ar}؛ وُجدت كلها في مصادر بصيرة مطابقةً للنص المصدر.",
        "flagged": "في الإجابة {n_ar}؛ {k_ar} يحتاج مراجعة قبل النشر (لم يُوجد مطابقًا في مصادر بصيرة أو يختلف عن النص المصدر).",
        "footer": "بصيرة أداة مساعدة حتمية؛ «لم يوجد في مصادرنا» ليس حكمًا على النص. راجع أهل العلم عند الشك.",
    },
    "en": {
        "no_quotes": "No Quran or Hadith quotation that can be checked was found in the answer.",
        "clear": "The answer contains {n} quotation(s); all of them were found in Basira's sources matching the source text.",
        "flagged": "The answer contains {n} quotation(s); {k} of them need review before publishing (not found verbatim in Basira's sources, or differing from the source text).",
        "footer": 'Basira is a deterministic aid; "not found in our sources" is not a verdict on the text. Consult qualified scholars when in doubt.',
    },
}


def arabic_count(
    n: int,
    singular: str = "اقتباس واحد",
    dual: str = "اقتباسان",
    plural_few: str = "اقتباسات",
    plural_many: str = "اقتباسًا",
) -> str:
    """Arabic number agreement: 1 → «اقتباس واحد», 2 → «اقتباسان», 3–10 → «N اقتباسات», 11+ → «N اقتباسًا»."""
    if n == 1:
        return singular
    if n == 2:
        return dual
    if 3 <= n <= 10:
        return f"{n} {plural_few}"
    return f"{n} {plural_many}"


def arabic_k(k: int) -> str:
    """«منها» phrase for the flagged count: 1 → «واحد منها», 2 → «اثنان منها», else «N منها»."""
    if k == 1:
        return "واحد منها"
    if k == 2:
        return "اثنان منها"
    return f"{k} منها"


def render(verdict: Verdict, lang: str, *, n: int, k: int) -> str:
    t = TEMPLATES["en" if lang == "en" else "ar"]
    body = t[verdict].format(n=n, k=k, n_ar=arabic_count(n), k_ar=arabic_k(k))
    return f"{body} {t['footer']}"


def all_templates() -> list[str]:
    return [tpl for lang in TEMPLATES.values() for tpl in lang.values()]
