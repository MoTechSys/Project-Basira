"""Developer gate — shared, transport-agnostic core behind the MCP tools and the `/v1/*` developer routes.

One implementation, three doors (docs/API.md, docs/GUARD.md, docs/INTEGRATIONS.md §3.1):

* ``compact_check``  — ``CheckResponse`` → the short shape a model or an integrator needs
  (status, kind, quoted_text, review_reason, matches[ref, ref_label, source_text, source_url,
  diff_kinds], notices rendered as sentences from ``messages/*.json``, determinism_hash).
* ``verify_quote``   — one quotation + an optional claimed reference («2:255», «البخاري 1»): the quote
  is wrapped as a marked citation followed by the claim so the *existing* extractor and claimed-source
  logic run unchanged; nothing is re-implemented here.
* ``sources_info``   — ``corpus/manifest.json`` → sources, versions, licences, sha256.
* ``grounding_rules``— fixed text drawn from ``SAFETY.md`` (the four states, the red lines, what
  «لم يوجد في مصادرنا» does and does not mean) for a model to load once as instructions.
* ``issue_receipt`` / ``verify_receipt`` — the stateless verification receipt (docs/API.md §Receipt):
  the receipt *is* the input. ``token = base64url(zlib(json{v:1,t:text,l:ui_lang}))`` — a compressed
  payload, no secret, no database. ``GET /v/{token}`` re-runs the whole pipeline and compares the fresh
  ``determinism_hash`` with the one the holder presents (``?h=``): equal → ``verified_now``; different →
  ``stale`` (the corpus build or a verdict changed — said explicitly, never hidden).

Red lines hold at this layer: the only religious text that leaves is ``source_text`` — the corpus
record verbatim as produced by the pipeline (already V1-validated). Nothing is stored or logged.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.config import Settings
from app.messages import Messages, load_messages
from app.pipeline import Pipeline
from app.schemas import CheckOptions, CheckRequest, CheckResponse, QuoteResult

UiLang = Literal["ar", "en"]
REPO_ROOT = Path(__file__).resolve().parents[2]
SAFETY_MD = REPO_ROOT / "SAFETY.md"

# Notices that are UI chrome / display hints rather than facts about the quotation. They are kept
# in ``notice_keys`` but not rendered as sentences for a model.
_DISPLAY_ONLY_NOTICES: frozenset[str] = frozenset(
    {"ohd_display_note", "ohd_numbering", "hadeethenc_link_only", "many_positions", "other_nine_referral"}
)


class DevGateError(ValueError):
    """Input problem with a stable machine code; the transports map it to their envelope."""

    def __init__(self, code: str, **vars: Any) -> None:
        super().__init__(code)
        self.code = code
        self.vars = vars


# --------------------------------------------------------------------------- validation


def validate_text(text: str, settings: Settings) -> str:
    if not isinstance(text, str) or not text.strip():
        raise DevGateError("invalid_input")
    if len(text) > settings.max_text_chars:
        raise DevGateError("text_too_long", max=settings.max_text_chars)
    return text


def validate_lang(ui_lang: str) -> UiLang:
    return "en" if ui_lang == "en" else "ar"


# --------------------------------------------------------------------------- compact shape


def _render_notices(q: QuoteResult, msgs: Messages, source_name: str, ref: str) -> list[str]:
    out: list[str] = []
    for key in q.notice_keys:
        if key in _DISPLAY_ONLY_NOTICES or key == "grade_line" or not msgs.has("notice", key):
            continue
        out.append(msgs.get("notice", key, source_name=source_name, ref=ref, count=q.total_positions))
    return out


def compact_quote(q: QuoteResult, msgs: Messages, ui_lang: UiLang) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for m in q.matches:
        matches.append(
            {
                "corpus": m.corpus,
                "ref": m.ref,
                "ref_label": m.ref_label_en if ui_lang == "en" else m.ref_label_ar,
                "source_text": m.source_text,  # corpus record, verbatim (V1)
                "source_url": m.source_url,
                "diff_kinds": list(m.diff_kinds),
                "score": m.score,
                "grade": None
                if m.grade is None
                else {
                    "text": m.grade.text,
                    "takhrij": m.grade.takhrij,
                    "source": m.grade.source,
                    "url": m.grade.url,
                },
            }
        )
    first_label = matches[0]["ref_label"] if matches else ""
    source_name = ""
    if matches:
        source_name = msgs.get("labels", "source_quran") if matches[0]["corpus"] == "tanzil" else first_label
    status_line = (
        msgs.get(
            "status",
            q.message_key,
            source_name=source_name,
            ref=first_label,
            count=q.total_positions,
            shown=len(matches),
        )
        if msgs.has("status", q.message_key)
        else ""
    )
    return {
        "id": q.id,
        "span": {"start": q.span.start, "end": q.span.end},
        "quoted_text": q.quoted_text,
        "kind": q.kind,
        "status": q.status,
        "review_reason": q.review_reason,
        "status_message": status_line,
        "claimed_source": None if q.claimed_source is None else q.claimed_source.raw,
        "claimed_source_mismatch": q.claimed_source_mismatch,
        "matches": matches,
        "total_positions": q.total_positions,
        "notice_keys": list(q.notice_keys),
        "notices": _render_notices(q, msgs, source_name, first_label),
    }


def compact_check(resp: CheckResponse, settings: Settings, ui_lang: UiLang) -> dict[str, Any]:
    msgs = load_messages(settings.messages_dir, ui_lang)
    return {
        "request_id": resp.request_id,
        "ui_lang": ui_lang,
        "corpus": resp.corpus,
        "extraction_provider": resp.extraction_provider,
        "extraction_degraded": resp.extraction_degraded,
        "flags": resp.flags.model_dump(),
        "quotes": [compact_quote(q, msgs, ui_lang) for q in resp.quotes],
        "validator_rejections": resp.validator_rejections,
        "determinism_hash": resp.determinism_hash,
        "disclaimer": msgs.get("fixed", "footer"),
        "transparency": msgs.get("fixed", "transparency_notice"),
    }


# --------------------------------------------------------------------------- operations


async def verify_text(
    pipeline: Pipeline, settings: Settings, text: str, ui_lang: str = "ar"
) -> dict[str, Any]:
    lang = validate_lang(ui_lang)
    text = validate_text(text, settings)
    resp = await pipeline.check(CheckRequest(text=text, ui_lang=lang, options=CheckOptions(max_candidates=3)))
    return compact_check(resp, settings, lang)


_CLAIMED_REF_OK = re.compile(r"^[\w\u0600-\u06FF\s:،,.\-–/()'’]{1,60}$")


def quote_with_claim(text: str, claimed_ref: str | None) -> str:
    """Build the text the pipeline sees for ``verify_quote``: «quote» [claimed_ref]."""
    q = text.strip().strip('«»"“”‹›﴾﴿()[]').strip()
    body = f"«{q}»"
    if claimed_ref:
        ref = claimed_ref.strip()
        if not _CLAIMED_REF_OK.match(ref):
            raise DevGateError("invalid_input")
        body = f"{body} [{ref}]"
    return body


async def verify_quote(
    pipeline: Pipeline, settings: Settings, text: str, claimed_ref: str | None = None, ui_lang: str = "ar"
) -> dict[str, Any]:
    lang = validate_lang(ui_lang)
    text = validate_text(text, settings)
    composed = quote_with_claim(text, claimed_ref)
    if len(composed) > settings.max_text_chars:
        raise DevGateError("text_too_long", max=settings.max_text_chars)
    resp = await pipeline.check(
        CheckRequest(text=composed, ui_lang=lang, options=CheckOptions(max_candidates=3))
    )
    full = compact_check(resp, settings, lang)
    if not full["quotes"]:
        return {
            "status": "not_found",
            "kind": "unknown",
            "claimed_ref": claimed_ref,
            "claimed_source_mismatch": False,
            "quote": None,
            "determinism_hash": resp.determinism_hash,
            "disclaimer": full["disclaimer"],
        }
    q = full["quotes"][0]
    return {
        "status": q["status"],
        "kind": q["kind"],
        "review_reason": q["review_reason"],
        "claimed_ref": claimed_ref,
        "claimed_source_mismatch": bool(q["claimed_source_mismatch"]),
        "quote": q,
        "determinism_hash": resp.determinism_hash,
        "disclaimer": full["disclaimer"],
    }


# --------------------------------------------------------------------------- verification receipt (E-052)

RECEIPT_VERSION = 1
RECEIPT_ID_HEX = 16
# Token bound: a zlib payload is never much larger than its input, and the input is bounded by
# max_text_chars; this is the absolute cap on *bytes of token* before anything is decoded (zip-bomb guard).
_TOKEN_OVERHEAD = 256


def encode_receipt_token(text: str, ui_lang: UiLang) -> str:
    payload = json.dumps(
        {"v": RECEIPT_VERSION, "t": text, "l": ui_lang}, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(payload, 9)).rstrip(b"=").decode("ascii")


def decode_receipt_token(token: str, settings: Settings) -> tuple[str, UiLang]:
    """Inverse of :func:`encode_receipt_token`. Any malformed token → ``receipt_invalid``; an oversized one →
    ``text_too_long`` (same code as the REST body limit, so clients see one rule)."""
    max_payload = settings.max_text_chars * 4 + _TOKEN_OVERHEAD  # UTF-8 worst case + JSON envelope
    max_token = 4 * max_payload // 3 + 4
    if not isinstance(token, str) or not token:
        raise DevGateError("receipt_invalid")
    if len(token) > max_token:
        raise DevGateError("text_too_long", max=settings.max_text_chars)
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload = zlib.decompressobj().decompress(raw, max_payload)
        obj = json.loads(payload.decode("utf-8"))
    except (binascii.Error, zlib.error, UnicodeDecodeError, ValueError):
        raise DevGateError("receipt_invalid") from None
    if not isinstance(obj, dict) or obj.get("v") != RECEIPT_VERSION or not isinstance(obj.get("t"), str):
        raise DevGateError("receipt_invalid")
    text = validate_text(str(obj["t"]), settings)
    return text, validate_lang(str(obj.get("l", "ar")))


def _receipt_of(
    resp: CheckResponse, settings: Settings, lang: UiLang, token: str, *, index_sha256: str, build_sha: str
) -> dict[str, Any]:
    full = compact_check(resp, settings, lang)
    by_status: dict[str, int] = {}
    for q in resp.quotes:
        by_status[q.status] = by_status.get(q.status, 0) + 1
    return {
        "receipt_id": resp.determinism_hash[:RECEIPT_ID_HEX],
        "determinism_hash": resp.determinism_hash,
        "corpus": resp.corpus,
        "index_sha256": index_sha256,
        "build_sha": build_sha,
        "issued_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "ui_lang": lang,
        "summary": {"quotes": len(resp.quotes), "by_status": by_status},
        "quotes": full["quotes"],
        "validator_rejections": resp.validator_rejections,
        "disclaimer": full["disclaimer"],
        "token": token,
    }


async def issue_receipt(
    pipeline: Pipeline,
    settings: Settings,
    text: str,
    ui_lang: str = "ar",
    *,
    index_sha256: str = "",
    build_sha: str = "",
) -> dict[str, Any]:
    """``POST /v1/receipt`` and the MCP ``issue_receipt`` tool. Nothing is stored: the token carries the input."""
    lang = validate_lang(ui_lang)
    text = validate_text(text, settings)
    resp = await pipeline.check(CheckRequest(text=text, ui_lang=lang, options=CheckOptions(max_candidates=3)))
    token = encode_receipt_token(text, lang)
    return _receipt_of(resp, settings, lang, token, index_sha256=index_sha256, build_sha=build_sha)


async def verify_receipt(
    pipeline: Pipeline,
    settings: Settings,
    token: str,
    h: str | None = None,
    *,
    index_sha256: str = "",
    build_sha: str = "",
) -> dict[str, Any]:
    """``GET /v/{token}?h=``: decode, re-run in full, and say whether the presented hash still holds."""
    text, lang = decode_receipt_token(token, settings)
    resp = await pipeline.check(CheckRequest(text=text, ui_lang=lang, options=CheckOptions(max_candidates=3)))
    out = _receipt_of(resp, settings, lang, token, index_sha256=index_sha256, build_sha=build_sha)
    presented = (h or "").strip().lower()
    out["presented_hash"] = presented or None
    out["verified_now"] = bool(presented) and presented == resp.determinism_hash
    out["stale"] = bool(presented) and presented != resp.determinism_hash
    return out


def sources_info(manifest: dict[str, Any], counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    counts = counts or {}
    out: list[dict[str, Any]] = []
    for s in manifest.get("sources", []):
        sid = str(s["id"])
        key = (
            "tanzil" if sid.startswith("tanzil") else ("hadeethenc" if sid.startswith("hadeethenc") else sid)
        )
        item: dict[str, Any] = {
            "id": sid,
            "name": str(s.get("name", sid)),
            "type": str(s.get("type", "")),
            "url": str(s.get("url") or s.get("repo") or ""),
            "version": str(s.get("version") or s.get("commit") or ""),
            "license": str(s.get("license", "")),
            "license_url": str(s.get("license_url", "")),
            "purpose": str(s.get("purpose", "")),
            "sha256": str(s.get("sha256") or ""),
            "records": int(counts.get(key, 0) or s.get("expected_records", 0) or 0),
            "downloaded_at": s.get("downloaded_at"),
        }
        if "books" in s:
            item["books"] = [
                {
                    "key": b["key"],
                    "name_ar": b["name_ar"],
                    "name_en": b["name_en"],
                    "sha256_plain": b.get("sha256_plain", ""),
                    "sha256_display": b.get("sha256_display", ""),
                }
                for b in s["books"]
            ]
        out.append(item)
    return out


# --------------------------------------------------------------------------- grounding rules

_RULES_EN = """Basira grounding rules (read once per session; source of truth: SAFETY.md in the repository)

What Basira is: a deterministic checker. Given text, it locates every Quran/Hadith quotation and compares
it byte-for-byte against licensed sources (Tanzil Hafs Quran; Open-Hadith-Data nine books; HadeethEnc).
Same input on the same corpus build => same output (determinism_hash).

The four states, and the ONLY meanings they carry:
  found         - the quoted words match a source record exactly (strict orthography). source_text is that record.
  partial_match - hadith only: overlaps a record with differences; a transmission variant is possible.
  needs_review  - the quote differs from the closest record (Quran: ANY difference lands here, never partial_match),
                  or could not be verified (non-Arabic, image, foreign material, short quote).
  not_found     - nothing close enough in OUR sources. This is NOT a verdict on the text itself.
                  Say: "not found in Basira's sources"; recommend checking with qualified scholars.

Red lines - never cross them when presenting Basira results:
  1. Do not generate, correct, complete or "fix" religious text. Show only source_text as given.
  2. Do not assign any authenticity grade and do not issue rulings. If a grade line appears in a
     result it is HadeethEnc's own, quoted verbatim and attributed; present it as theirs, never as Basira's.
  3. Do not store or echo user text beyond answering the request.
  4. A claimed_source_mismatch means the reference the user wrote does not match where the text was
     found; the status is unaffected. Report both facts.
  5. Image-sourced quotations are never confirmed; they are always needs_review.

How to use the tools: verify_text for a whole answer or post; verify_quote for one quotation with an
optional claimed reference such as "2:255" or "البخاري 1"; guard_answer before showing a chatbot answer;
list_sources for provenance. Basira complements retrieval servers (e.g. get_quran_verses): they fetch
the text, Basira tells you whether the text in hand is that text.
"""

_RULES_AR = """قواعد التأريض لبصيرة (تُقرأ مرة في الجلسة؛ المرجع: SAFETY.md في المستودع)

ما هي بصيرة: مدقّق حتمي. يحدّد كل اقتباس قرآني/حديثي في النص ويقارنه حرفًا بحرف مع مصادر مرخّصة
(مصحف تنزيل برواية حفص؛ الكتب التسعة من Open-Hadith-Data؛ موسوعة الأحاديث النبوية). نفس المدخل على نفس
بناء المدوّنة = نفس المخرج (determinism_hash).

الحالات الأربع، وهذه معانيها فقط:
  found         وُجد: الكلمات المنقولة تطابق سجلًا في المصدر تطابقًا تامًّا. source_text هو ذلك السجل.
  partial_match تطابق جزئي (للحديث فقط): يتقاطع مع سجل مع فروق؛ قد يكون اختلاف رواية.
  needs_review  يحتاج مراجعة: يختلف عن أقرب سجل (في القرآن أي فرق يصل هنا، ولا يكون جزئيًّا أبدًا)،
                أو تعذّر التحقق (غير عربي، صورة، مادة أجنبية داخل النص، اقتباس قصير).
  not_found     لم يوجد في مصادرنا. هذا ليس حكمًا على النص. قل: «لم يوجد في مصادر بصيرة» وانصح بسؤال أهل العلم.

الخطوط الحمراء عند عرض نتائج بصيرة:
  1. لا تولّد ولا تصحّح ولا تكمّل نصًّا دينيًّا. اعرض source_text كما ورد فقط.
  2. لا تُصدر درجة ولا حكمًا. إن ظهرت درجة في النتيجة فهي سطر موسوعة الأحاديث نفسه منقولًا منسوبًا؛ اعرضه بوصفه كذلك.
  3. لا تخزّن نص المستخدم ولا تعيد نشره خارج الرد.
  4. claimed_source_mismatch يعني أن المرجع الذي كتبه المستخدم لا يطابق موضع النص؛ الحالة لا تتغيّر. اذكر الأمرين.
  5. ما قُرئ من صورة لا يُؤكَّد أبدًا؛ حالته دائمًا «يحتاج مراجعة».

الاستخدام: verify_text لنص أو إجابة كاملة؛ verify_quote لاقتباس واحد مع مرجع مدّعى مثل «2:255» أو «البخاري 1»؛
guard_answer قبل عرض إجابة الشات بوت؛ list_sources لمعرفة المصادر. بصيرة تكمّل خوادم الاسترجاع
(مثل get_quran_verses): هي تجلب النص، وبصيرة تقول هل ما بين يديك هو ذلك النص.
"""


def grounding_rules(ui_lang: str = "en") -> dict[str, Any]:
    """Fixed instructions for models. ``safety_sha256`` lets a client detect that SAFETY.md moved on."""
    import hashlib  # noqa: PLC0415

    sha = hashlib.sha256(SAFETY_MD.read_bytes()).hexdigest() if SAFETY_MD.exists() else ""
    return {
        "ui_lang": validate_lang(ui_lang),
        "text": _RULES_AR if validate_lang(ui_lang) == "ar" else _RULES_EN,
        "states": ["found", "partial_match", "needs_review", "not_found"],
        "source": "SAFETY.md",
        "safety_sha256": sha,
    }


def all_rule_texts() -> list[str]:
    return [_RULES_AR, _RULES_EN]
