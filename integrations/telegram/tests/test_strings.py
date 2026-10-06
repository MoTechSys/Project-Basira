"""Every string the bot authors passes the backend's forbidden-lexicon scanner (V4, SAFETY §1.3)."""

from __future__ import annotations

from app.messages import scan_forbidden

from bot import strings_ar as txt


def test_strings_module_is_non_empty_and_clean() -> None:
    items = txt.all_strings()
    assert len(items) >= 30
    hits = {name: scan_forbidden(value) for name, value in items if scan_forbidden(value)}
    assert hits == {}


def test_scanner_is_live() -> None:
    """Guard against a vacuous pass: the scanner must catch a judgement word."""
    assert scan_forbidden("هذا حديث ضعيف")
    assert scan_forbidden("fabricated")
    assert scan_forbidden("صحيح البخاري") == []  # book title, whitelisted (E-009)


def test_book_names_match_the_manifest() -> None:
    import json

    from conftest import ROOT

    manifest = json.loads((ROOT / "corpus/manifest.json").read_text(encoding="utf-8"))
    books = {b["key"]: b["name_ar"] for b in next(s for s in manifest["sources"] if s.get("books"))["books"]}
    assert books == txt.BOOK_NAMES
