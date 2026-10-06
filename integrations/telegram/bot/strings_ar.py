"""Every fixed string the bot itself authors (UI chrome only — never a word about a quotation's content).

Status texts, notices, error messages, the transparency/privacy lines and the refusal text are NOT here: they
come verbatim from ``messages/*.json`` (served by ``GET /v1/messages/{lang}``) or from the API error envelope.
``tests/test_strings.py`` runs the backend's forbidden-lexicon scanner over every value in this module.
"""

from __future__ import annotations

from typing import Final

# State markers (shape only); the label next to each comes from messages ``labels.<status>``.
STATUS_ICON: Final[dict[str, str]] = {
    "found": "✅",
    "partial_match": "◐",
    "needs_review": "⚠️",
    "not_found": "○",
}

WELCOME: Final = (
    "<b>بصيرة</b> — تحقق من نقل الآيات والأحاديث قبل النشر.\n"
    "<i>Basira checks Quran and Hadith quotations against their sources before you share them.</i>\n\n"
    "أرسل أو أعد توجيه (Forward) أي نص أو صورة فيها آية أو حديث، وسأعرض لك نص المصدر كما ورد "
    "ومرجعه والفروق إن وُجدت."
)
HELP: Final = (
    "<b>طريقة الاستخدام</b>\n"
    "• في المحادثة الخاصة: أرسل النص أو الصورة مباشرة، أو أعد توجيهها من أي محادثة.\n"
    "• في المجموعات: ردّ على الرسالة بالأمر /check، أو اكتب /check ثم النص، أو اذكرني ثم النص.\n"
    "• /limits حدود ما تفحصه بصيرة · /sources المصادر وإصداراتها ورخصها.\n\n"
    "الحد الأقصى للنص {max_chars} حرف، وللصورة {max_mb} ميجابايت (PNG أو JPEG أو WebP)."
)
CHECKING: Final = "⏳ جارٍ الفحص…"
CHECKING_IMAGE: Final = "⏳ جارٍ قراءة الصورة وفحصها…"
OCR_HEADING: Final = "النص كما قُرئ من الصورة — راجعه"
USAGE_GROUP: Final = "ردّ على رسالة فيها نص أو صورة بالأمر /check، أو اكتب /check ثم النص."
USAGE_PRIVATE: Final = "أرسل نصًا أو صورة فيها آية أو حديث، أو أعد توجيهها إليّ."
UNSUPPORTED: Final = "أستقبل النصوص والصور فقط (PNG أو JPEG أو WebP)."
TRY_IN_A_MINUTE: Final = "حاول بعد دقيقة."
UNREACHABLE: Final = "تعذّر الوصول إلى خادم بصيرة الآن؛ حاول بعد قليل."
TIMEOUT: Final = "استغرق الفحص وقتًا أطول من المعتاد ولم يكتمل؛ حاول مرة أخرى بعد قليل."
QUOTE_HEADING: Final = "الاقتباس {i} من {n}"
YOUR_TEXT: Final = "نصك"
SOURCE_TEXT: Final = "نص المصدر"
OTHER_POSITIONS: Final = "مواضع أخرى"
LINKS: Final = "روابط"
DIFF_LEGEND: Final = "الكلمات المختلفة بالخط العريض."
ELLIPSIS: Final = "…"
LIMITS_HEADING: Final = "<b>حدود ما تفحصه بصيرة</b>"
LIMITS_MORE: Final = "النص الكامل: {url}"
SOURCES_HEADING: Final = "<b>المصادر</b> (من {url}/v1/sources)"
SOURCE_LINE: Final = "• <b>{name}</b>\n  الإصدار: {version} · السجلات: {records}\n  الرخصة: {license}"
OPEN_SITE: Final = "افتح موقع بصيرة"

KIND: Final[dict[str, str]] = {
    "quran": "قرآن",
    "hadith_matn": "حديث",
    "isnad": "إسناد",
    "attributed_saying": "قول منسوب",
    "unknown": "اقتباس",
}

# Book titles for the ``{source_name}`` variable of the status templates — the same proper nouns as
# corpus/manifest.json ``books[].name_ar`` (and frontend QuoteCard BOOK_NAMES). Titles, not judgements (E-009).
BOOK_NAMES: Final[dict[str, str]] = {
    "sahih_al-bukhari": "صحيح البخاري",
    "sahih_muslim": "صحيح مسلم",
    "sunan_abu-dawud": "سنن أبي داود",
    "sunan_al-tirmidhi": "سنن الترمذي",
    "sunan_al-nasai": "سنن النسائي",
    "sunan_ibn-maja": "سنن ابن ماجه",
    "maliks_muwataa": "موطأ مالك",
    "musnad_ahmad": "مسند أحمد",
    "sunan_al-darimi": "سنن الدارمي",
}
HADEETHENC_NAME: Final = "موسوعة الأحاديث النبوية"


def all_strings() -> list[tuple[str, str]]:
    """(name, value) for every string in this module — used by the lexicon test."""
    out: list[tuple[str, str]] = []
    for name, value in globals().items():
        if name.isupper() and isinstance(value, str):
            out.append((name, value))
        elif name.isupper() and isinstance(value, dict):
            out.extend((f"{name}.{k}", v) for k, v in value.items() if isinstance(v, str))
    return out
