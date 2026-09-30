"""Post-validator (BUILD_SPEC §3.6, SAFETY §2.1) — runs on the COMPLETE response before it is sent.

Five checks; any failure downgrades the affected quote to ``needs_review`` with
``review_reason="validator_reject"``, empties its matches, and increments
``validator_rejections``. Nothing is logged about the user text.

  V1  every ``matches[].source_text`` is byte-equal to the corpus record's display field
      for the same (corpus, ref) — no religious text may reach the user unless it is the
      verbatim corpus field;
  V2  every ``ref`` exists in the store;
  V3  ``grade`` (if present) equals the HadeethEnc record's own ``grade``/``takhrij``/``link``
      and the match corpus is ``hadeethenc``;
  V4  forbidden lexicon scan over every string WE produce (message keys are looked up in both
      languages and scanned; ``ref_label_*``, notice keys, diff kinds) — literal corpus fields,
      ``quoted_text`` (user's own text) and the grade line are exempt;
  V5  ``disclaimer_key`` and ``transparency_key`` present and resolvable.

The validator is deliberately independent from the pipeline: it re-derives truth from the
Store, not from any intermediate object.
"""

from __future__ import annotations

from pathlib import Path

from app.messages import load_messages, scan_forbidden
from app.schemas import CheckResponse, Match, QuoteResult
from app.store import Record, Store


def _lookup(store: Store, m: Match) -> Record | None:
    r = m.ref
    try:
        if m.corpus == "tanzil":
            return store.lookup("tanzil", surah=int(r["surah"]), ayah=int(r["ayah"]))
        if m.corpus == "ohd":
            return store.lookup("ohd", book=str(r["book"]), num=int(r["num"]))
        return store.lookup("hadeethenc", id=int(r["id"]))
    except (KeyError, TypeError, ValueError):
        return None


def _match_ok(store: Store, m: Match) -> bool:
    rec = _lookup(store, m)
    if rec is None:  # V2
        return False
    if m.source_text != rec.display:  # V1 (byte-exact; display is the verbatim corpus field)
        return False
    if m.grade is not None:  # V3
        if rec.corpus != "hadeethenc":
            return False
        if m.grade.text != rec.grade or m.grade.takhrij != rec.takhrij or m.grade.url != rec.link:
            return False
    return True


def _our_strings(q: QuoteResult, messages_dir: Path) -> list[str]:
    out: list[str] = []
    for lang in ("ar", "en"):
        msgs = load_messages(messages_dir, lang)
        if msgs.has("status", q.message_key):
            out.append(msgs.get("status", q.message_key))
        for k in q.notice_keys:
            if k == "grade_line":
                continue  # attributed quotation of the corpus grade (exempt by design)
            if msgs.has("notice", k):
                out.append(msgs.get("notice", k))
    for m in q.matches:
        out.append(m.ref_label_ar)
        out.append(m.ref_label_en)
        out.extend(m.diff_kinds)
    return out


def _reject(q: QuoteResult) -> None:
    q.status = "needs_review"
    q.review_reason = "validator_reject"
    q.message_key = "needs_review_failure"
    q.matches = []
    q.notice_keys = [k for k in q.notice_keys if k in {"image_extracted"}]
    q.total_positions = 0
    q.score = 0.0


def validate_response(resp: CheckResponse, store: Store, messages_dir: Path) -> CheckResponse:
    rejections = 0
    for q in resp.quotes:
        bad = False
        for m in q.matches:
            if not _match_ok(store, m):
                bad = True
                break
        if not bad:
            for s in _our_strings(q, messages_dir):
                if scan_forbidden(s):
                    bad = True
                    break
        if not bad and q.status == "found" and not q.matches:
            bad = True  # a `found` without a verbatim source is impossible
        if bad:
            _reject(q)
            rejections += 1
    # V5
    ar = load_messages(messages_dir, "ar")
    if not (ar.has("fixed", resp.disclaimer_key) and ar.has("fixed", resp.transparency_key)):
        resp.disclaimer_key = "footer"
        resp.transparency_key = "transparency_notice"
    resp.validator_rejections = rejections
    return resp
