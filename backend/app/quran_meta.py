"""Fixed Mushaf metadata (Hafs / Kufic count): the number of ayat in each of the 114 surahs.

Data, not text: used only to reject an impossible claimed reference («الإخلاص 1-999», «البقرة 300») with a
notice (B06). Total = 6 236, asserted at import so a typo can never ship.
"""

from __future__ import annotations

AYAH_COUNTS: tuple[int, ...] = (
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135,
    112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85,
    54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13,
    14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42,
    29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11,
    11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6,
)  # fmt: skip
assert len(AYAH_COUNTS) == 114 and sum(AYAH_COUNTS) == 6236


def ayah_count(surah: int) -> int | None:
    return AYAH_COUNTS[surah - 1] if 1 <= surah <= 114 else None


def claimed_ref_possible(surah: int, ayah: int, ayah_to: int | None) -> bool:
    """A claimed reference is *possible* when the surah exists, every ayah number is within the surah, and a
    range runs forward. Says nothing about the text — only whether the reference can exist in a Mushaf."""
    n = ayah_count(surah)
    if n is None or not 1 <= ayah <= n:
        return False
    return ayah_to is None or ayah <= ayah_to <= n
