"""Word-level diff between a quote and a source window, projected onto original text.

Uses ``difflib.SequenceMatcher`` on token lists (BUILD_SPEC §3.4-ج). Each op
carries token ranges on both sides plus *character* ranges on the original
strings, so the UI can highlight the user's text and the verbatim source text
without ever re-rendering religious text.

Compared on the **strict** tier so that a difference like «على/علي» is visible
(ADR-002); the loose tier would hide it.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Literal, TypedDict

Op = Literal["equal", "replace", "insert", "delete"]


class DiffOp(TypedDict):
    op: Op
    quote_range: list[int]  # token indices [start, end) in the quote
    source_range: list[int]  # token indices [start, end) in the source window
    quote_chars: list[int]  # char offsets [start, end) in the quote's original text
    source_chars: list[int]  # char offsets [start, end) in the source display text (or [-1,-1])


def _chars(spans: list[tuple[int, int]], a: int, b: int) -> list[int]:
    if a >= b or not spans or a >= len(spans):
        # empty side of an insert/delete: anchor at the boundary
        if spans and a > 0 and a <= len(spans):
            e = spans[min(a, len(spans)) - 1][1]
            return [e, e]
        if spans:
            return [spans[0][0], spans[0][0]]
        return [-1, -1]
    return [spans[a][0], spans[min(b, len(spans)) - 1][1]]


def word_diff(
    quote_tokens: list[str],
    quote_spans: list[tuple[int, int]],
    source_tokens: list[str],
    source_spans: list[tuple[int, int]] | None,
    source_alt_tokens: list[str] | None = None,
) -> list[DiffOp]:
    """``source_alt_tokens`` (E-024): the same source words in the other Quran rasm. A quote word
    equal to either spelling is treated as equal, so «كما» against Uthmani «كمآ» is not highlighted."""
    if source_alt_tokens is not None and len(source_alt_tokens) == len(source_tokens):
        # project the source onto whichever spelling the quote used, position by position, so the
        # matcher sees equality without us ever altering the displayed text
        qset = set(quote_tokens)
        source_tokens = [
            alt if (s not in qset and alt in qset) else s
            for s, alt in zip(source_tokens, source_alt_tokens, strict=True)
        ]
    sm = SequenceMatcher(a=quote_tokens, b=source_tokens, autojunk=False)
    ops: list[DiffOp] = []
    for tag_, i1, i2, j1, j2 in sm.get_opcodes():
        tag: Op = tag_  # type: ignore[assignment,unused-ignore]
        ops.append(
            DiffOp(
                op=tag,
                quote_range=[i1, i2],
                source_range=[j1, j2],
                quote_chars=_chars(quote_spans, i1, i2),
                source_chars=_chars(source_spans, j1, j2) if source_spans is not None else [-1, -1],
            )
        )
    return ops


def is_identical(ops: list[DiffOp]) -> bool:
    return all(o["op"] == "equal" for o in ops)


def diff_kinds(ops: list[DiffOp]) -> list[str]:
    """Template-able description kinds (SAFETY §1.3): only these fixed categories."""
    kinds: list[str] = []
    for o in ops:
        if o["op"] == "replace":
            kinds.append("word_replaced")
        elif o["op"] == "insert":
            kinds.append("word_missing_in_quote")
        elif o["op"] == "delete":
            kinds.append("word_added_in_quote")
    return sorted(set(kinds))
