"""Referral/source URL builders — every scheme verified live on 2026-10-01 (see docs/experiments E-014).

* Quran source: Tanzil is the corpus; the public ayah page is quranpedia (approved by the
  scientific package): ``https://quranpedia.net/surah/1/{surah}/{ayah}`` → 301 → ayah page (200).
* Hadith referral searches: ``https://dorar.net/hadith/search?q=…`` (200),
  ``https://shamela.ws/search?q=…`` (200). Both approved by the scientific package.
* HadeethEnc record page: ``https://hadeethenc.com/ar/browse/hadith/{id}`` (200) — but the
  per-record ``link`` field from the corpus is always preferred when present.
* Open-Hadith-Data record: GitHub blob of the book file at the pinned commit (no per-row anchor).

No URL ever embeds anything but the user's quote (for searches) or a numeric reference.
"""

from __future__ import annotations

from urllib.parse import quote

from app.schemas import Link

QURANPEDIA_AYAH = "https://quranpedia.net/surah/1/{surah}/{ayah}"
DORAR_SEARCH = "https://dorar.net/hadith/search?q={q}"
SHAMELA_SEARCH = "https://shamela.ws/search?q={q}"
QURANPEDIA_SEARCH = "https://quranpedia.net/search?q={q}"
HADEETHENC_PAGE = "https://hadeethenc.com/ar/browse/hadith/{id}"
OHD_BLOB = "https://github.com/mhashim6/Open-Hadith-Data/blob/{commit}/{dir}/{file}"


def quran_url(surah: int, ayah: int) -> str:
    return QURANPEDIA_AYAH.format(surah=surah, ayah=ayah)


def hadeethenc_url(record_link: str, henc_id: int) -> str:
    return record_link or HADEETHENC_PAGE.format(id=henc_id)


def ohd_url(commit: str, book_dir: str, display_file: str) -> str:
    return OHD_BLOB.format(commit=commit, dir=book_dir, file=display_file)


def _q(text: str, max_chars: int = 120) -> str:
    return quote(text.strip()[:max_chars], safe="")


def hadith_search_links(quote_text: str, labels: dict[str, str]) -> list[Link]:
    q = _q(quote_text)
    return [
        Link(name=labels["search_dorar"], url=DORAR_SEARCH.format(q=q)),
        Link(name=labels["search_shamela"], url=SHAMELA_SEARCH.format(q=q)),
    ]


def quran_search_links(quote_text: str, labels: dict[str, str]) -> list[Link]:
    return [Link(name=labels["search_quranpedia"], url=QURANPEDIA_SEARCH.format(q=_q(quote_text)))]
