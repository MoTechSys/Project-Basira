"""Post-validator (ARCHITECTURE §2 stage 7, SAFETY §2.1) — runs on the COMPLETE response before it is sent.

Six checks. V1–V5 failures downgrade the affected quote to ``needs_review`` with
``review_reason="validator_reject"`` and empty its matches; a V6 failure downgrades to
``needs_review`` with ``review_reason="validator_unproven"`` (matches kept, so the user still sees
the closest record). Both increment ``validator_rejections``. Nothing is logged about the user text.

  V1  every ``matches[].source_text`` is byte-equal to the corpus record's display field
      for the same (corpus, ref) — no religious text may reach the user unless it is the
      verbatim corpus field; in ``HADEETHENC_MODE=link`` a HadeethEnc match must carry an
      EMPTY body (text is linked, never embedded — decision Q2);
  V2  every ``ref`` exists in the store;
  V3  ``grade`` (if present) equals the HadeethEnc record's own ``grade``/``takhrij``/``link``
      and the match corpus is ``hadeethenc``;
  V4  forbidden lexicon scan over every string WE produce (message keys are looked up in both
      languages and scanned; ``ref_label_*``, notice keys, diff kinds) — literal corpus fields,
      ``quoted_text`` (user's own text) and the grade line are exempt;
  V5  ``disclaimer_key`` and ``transparency_key`` present and resolvable;
  V6  (B04, I17) **independent proof of every ``found``**: the strict tokens of ``quoted_text`` —
      re-derived here with ``normalize.strict_tokens`` — must occur as one contiguous window inside
      the strict token stream of the first match's record (Quran: inside the surah stream starting
      at that ayah, so a quote spanning consecutive ayat is covered; either rasm per word, E-024;
      the basmala offset is honoured). The proof uses only the Store's token streams, never the
      matcher's hits, scores or carriers. A quote of a vocalised text is compared on letters only
      (tashkeel is V-independent and handled by I14 upstream).
  V7  (D-015, I18) **independent proof of every rasm-completed ``found``** (notice
      ``rasm_completed``): the user's strict tokens are NOT a window of the record (that is why the
      rasm layer fired), so V6 would reject them. Instead V7 re-derives, from the Store alone, that
      (a) the user's tokens are a contiguous window of the record under the *bare* fold (hamza /
      ى / ة unwritten), (b) every differing token is a pure completion (the user wrote no marked
      form of their own), and (c) across **all** positions in the corpus where the bare window
      occurs, the strict spelling is unique. Failure → ``needs_review`` / ``validator_unproven``.

B05 (wording, not a check): a quote that is only an attribution («رواه البخاري», «متفق عليه») or only
a narration chain that stops before any matn is never reported ``not_found`` / ``partial_match`` —
«لم يوجد في مصادرنا» would read as a verdict on something that is not a text. It becomes
``needs_review`` / ``attribution_only`` with a neutral message asking for the matn. A verbatim
``found`` is left alone (it is a true statement about the words).

The validator is deliberately independent from the pipeline: it re-derives truth from the
Store, not from any intermediate object.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.extract.rules import parse_claimed_source
from app.extract.segments import _NARRATOR  # single source of truth for the isnad shape (read-only use)
from app.match.rasm import bare, classify_token
from app.messages import load_messages, scan_forbidden
from app.normalize import loose_tokens, strict_tokens
from app.schemas import CheckResponse, Match, QuoteResult
from app.store import Record, Store

MAX_PROOF_SPAN_TOKENS = 4096  # a Quran surah stream window large enough for any real quote


def _lookup(store: Store, m: Match) -> Record | None:
    return _lookup_ref(store, m.corpus, m.ref)


def _lookup_ref(store: Store, corpus: str, r: dict[str, Any]) -> Record | None:
    try:
        if corpus == "tanzil":
            return store.lookup("tanzil", surah=int(r["surah"]), ayah=int(r["ayah"]))
        if corpus == "ohd":
            return store.lookup("ohd", book=str(r["book"]), num=int(r["num"]))
        return store.lookup("hadeethenc", id=int(r["id"]))
    except (KeyError, TypeError, ValueError):
        return None


def _match_ok(store: Store, m: Match, *, hadeethenc_link: bool) -> bool:
    rec = _lookup(store, m)
    if rec is None:  # V2
        return False
    if rec.corpus == "hadeethenc" and hadeethenc_link:
        # link mode (Q2): the full text is NOT embedded; only an empty body is acceptable
        if m.source_text != "":
            return False
    elif m.source_text != rec.display:  # V1 (byte-exact; display is the verbatim corpus field)
        return False
    if m.grade is not None:  # V3
        if rec.corpus != "hadeethenc":
            return False
        if m.grade.text != rec.grade or m.grade.takhrij != rec.takhrij or m.grade.url != rec.link:
            return False
    return _segments_ok(store, m)


def _segments_ok(store: Store, m: Match) -> bool:
    """B07: every source segment is itself a record, byte-exact (V1/V2 per element — never a joined line)."""
    for seg in m.source_segments:
        srec = _lookup_ref(store, "tanzil", seg.ref)
        if srec is None or seg.source_text != srec.display:
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


# --------------------------------------------------------------------------- B05 attribution-only wording

_QUOTE_MARKS = "«»\"“”‹›﴾﴿()[]'’"
_BRACKETED = re.compile(r"«([^«»]+)»|“([^“”]+)”|\"([^\"]+)\"|﴿([^﴾﴿]+)﴾")
_ISNAD_TAIL = re.compile(r"[\s:：،,.؛;\-–]+$")
# Loose-token phrases that may follow a chain without being a matn: honorifics and bare reporting verbs.
_CHAIN_FILLER: frozenset[tuple[str, ...]] = frozenset(
    {
        ("صلي", "الله", "عليه", "وسلم"),
        ("صلي", "الله", "عليه", "واله", "وسلم"),
        ("عليه", "الصلاه", "والسلام"),
        ("عليه", "السلام"),
        ("رضي", "الله", "عنه"),
        ("رضي", "الله", "عنها"),
        ("رضي", "الله", "عنهم"),
        ("رضي", "الله", "عنهما"),
        ("قال",),
        ("قالت",),
        ("يقول",),
        ("انه", "قال"),
        ("ان", "رسول", "الله"),
        ("ان", "النبي"),
        ("رسول", "الله"),
        ("النبي",),
        ("سمعت",),
    }
)
_CHAIN_LINK = re.compile(r"^(?:حدثنا|حدثني|أخبرنا|أخبرني|عن|وعن|ثنا|نا|أنا|قال)\s+")
# A pure chain: «حدثنا A قال أخبرنا B عن C عن D [قال]» — every token is either a link word, a reporting
# verb, an honorific, a name particle («بن», «ابن», «أبي», «أبو», «أم») or a name; it never reaches a matn.
_CHAIN_START = ("حدثنا", "حدثني", "اخبرنا", "اخبرني", "ثنا", "انا", "عن", "وعن")
_CHAIN_WORDS = frozenset(
    {*_CHAIN_START, "قال", "قالت", "يقول", "سمعت", "بن", "ابن", "ابي", "ابو", "ام", "مولي", "ان", "انه", "و"}
)
_MAX_CHAIN_TOKENS = 40


def _letters(s: str) -> int:
    return sum(1 for ch in s if ch.isalpha())


def _only_filler(rest: str) -> bool:
    """True when ``rest`` is nothing but honorifics / reporting verbs (no matn words)."""
    toks = loose_tokens(rest)
    i = 0
    while i < len(toks):
        for n in (5, 4, 3, 2, 1):
            if tuple(toks[i : i + n]) in _CHAIN_FILLER:
                i += n
                break
        else:
            return False
    return True


def attribution_only_kind(quoted_text: str) -> str | None:
    """«رواه البخاري» / «متفق عليه» / «أخرجه مسلم في صحيحه» → "attribution";
    «عن أبي هريرة رضي الله عنه قال: قال رسول الله ﷺ:» or «حدثنا … عن … عن ابن عمر» (a chain that stops
    before any matn) → "isnad"; anything with words of its own → None. Looks only at the quote."""
    inner = _quote_inner(quoted_text)
    if not inner:
        return None
    if _is_bare_attribution(inner):
        return "attribution"
    if len(loose_tokens(inner)) >= 3 and (_chain_then_filler(inner) or _pure_chain(inner)):
        return "isnad"
    return None


def _quote_inner(quoted_text: str) -> str:
    """The text inside the first bracket pair when the extractor kept an introducer («قال ﷺ: «…»»);
    otherwise the quote with edge marks stripped."""
    m = _BRACKETED.search(quoted_text)
    if m is not None:
        return next(g for g in m.groups() if g is not None).strip()
    return quoted_text.strip().strip(_QUOTE_MARKS).strip()


def _is_bare_attribution(inner: str) -> bool:
    claim = parse_claimed_source(inner)
    if claim is None:
        return False
    raw = str(claim.get("raw", ""))
    rest = inner.replace(raw, " ", 1) if raw else inner
    parsed = claim.get("parsed", {})
    return _letters(rest) <= 2 and bool(parsed.get("books") or parsed.get("muttafaq"))


def _chain_then_filler(inner: str) -> bool:
    """Peel narrator links («حدثنا X», «عن Y», «قال») from the left; an isnad is left with filler only."""
    cur = inner
    consumed = False
    for _ in range(12):
        m = _NARRATOR.match(cur)
        if m is None or m.end() == 0:
            break
        consumed = True
        cur = _ISNAD_TAIL.sub("", cur[m.end() :]).lstrip()
        if _only_filler(cur):
            return True
        cur2 = re.sub(r"^(?:قال|قالت)\s+", "", cur)  # «حدثنا A قال حدثنا B …»
        if cur2 == cur and not _CHAIN_LINK.match(cur):
            break
        cur = cur2
    return consumed and _only_filler(cur)


def _pure_chain(inner: str) -> bool:
    """«حدثنا … عن … عن ابن عمر» with no reporting verb at the end: at least two link words, and every
    non-link token is a name-like token that is immediately preceded (within two tokens) by a link
    word or a name particle — i.e. the text is nothing but narrators."""
    toks = loose_tokens(inner)
    if not (3 <= len(toks) <= _MAX_CHAIN_TOKENS) or toks[0] not in _CHAIN_START:
        return False
    links = sum(1 for t in toks if t in _CHAIN_START)
    if links < 2:
        return False
    for i, t in enumerate(toks):
        if t in _CHAIN_WORDS:
            continue
        window = toks[max(0, i - 2) : i]
        if not any(w in _CHAIN_WORDS for w in window):
            return False
    return True


def _attribution_only(q: QuoteResult) -> None:
    q.status = "needs_review"
    q.review_reason = "attribution_only"
    q.message_key = "needs_review_attribution_only"
    q.matches = []
    q.external_search_links = []
    q.total_positions = 0
    q.score = 0.0
    q.notice_keys = [k for k in q.notice_keys if k in {"image_extracted", "repeated_in_text"}]


# --------------------------------------------------------------------------- V6 independent proof


def _window_matches(stream: list[str], alt: list[str] | None, needle: list[str], start: int) -> bool:
    for k, tok in enumerate(needle):
        pos = start + k
        if stream[pos] == tok:
            continue
        if alt is not None and alt[pos] == tok:
            continue
        return False
    return True


def _contains_window(stream: list[str], alt: list[str] | None, needle: list[str]) -> bool:
    n, m = len(stream), len(needle)
    if m == 0 or m > n:
        return False
    first = needle[0]
    for i in range(n - m + 1):
        if (stream[i] == first or (alt is not None and alt[i] == first)) and _window_matches(
            stream, alt, needle, i
        ):
            return True
    return False


def _surah_stream(store: Store, g0: int, surah: int) -> tuple[list[str], list[str]]:
    """Strict (and twin-rasm) tokens from ``g0`` to the end of the surah's stream document, capped."""
    end = min(len(store.g_rec), g0 + MAX_PROOF_SPAN_TOKENS)
    doc = int(store.g_doc[g0])
    g = g0
    while g < end and int(store.g_doc[g]) == doc and store.records[int(store.g_rec[g])].surah == surah:
        g += 1
    n = g - g0
    return store.strict_tokens_range(g0, n), store.strict_alt_tokens_range(g0, n)


def _proof_streams(store: Store, rec: Record) -> list[tuple[list[str], list[str] | None]]:
    """Strict token streams a `found` quote must be a contiguous window of (any one suffices).

    Hadith: the record's own tokens. Quran: the surah stream from this ayah's first indexed token
    (after the basmala offset) to the end of the surah — covers cross-ayah quotes attributed to the
    ayah where the window starts (E-025) — in **each** rasm the index holds (Uthmani display stream
    and the simple-rasm stream, `g2_*`), each with its word-aligned twin (E-024). The two rasms are
    separate streams because 363 ayat differ in word count («يأيها» vs «يا أيها»); a quote in the
    simple rasm of such an ayah is provable only in its own stream.
    """
    if rec.corpus != "tanzil":
        return [(store.strict_tokens_of(rec), None)]
    out: list[tuple[list[str], list[str] | None]] = [
        _surah_stream(store, rec.g_start + rec.offset, rec.surah)
    ]
    if rec.g2_start >= 0 and rec.g2_len > 0:
        out.append(_surah_stream(store, rec.g2_start + rec.offset, rec.surah))
    return out


def prove_found(store: Store, q: QuoteResult) -> bool:
    """V6: True iff the quote's strict tokens are a contiguous window of the first match's record stream."""
    if not q.matches:
        return False
    rec = _lookup(store, q.matches[0])
    if rec is None:
        return False
    needle = strict_tokens(q.quoted_text)
    if not needle:
        return False
    return any(_contains_window(stream, alt, needle) for stream, alt in _proof_streams(store, rec))


_RANK = {"equal": 0, "completion": 1, "swap": 2, "other": 3}


def _best_class(user: str, prim: str, alt: str | None) -> str:
    a = classify_token(user, prim)
    if alt is None:
        return a
    b = classify_token(user, alt)
    return a if _RANK[a] <= _RANK[b] else b


def _bare_window_is_completion(stream: list[str], alt: list[str] | None, user: list[str]) -> bool:
    """(a)+(b) of V7: the user's tokens occur as a contiguous window of ``stream`` under the bare
    fold and every differing token is a pure completion (never a swap or another letter)."""
    n = len(user)
    user_bare = [bare(t) for t in user]
    for i in range(len(stream) - n + 1):
        hit = all(
            bare(stream[i + k]) == user_bare[k] or (alt is not None and bare(alt[i + k]) == user_bare[k])
            for k in range(n)
        )
        if hit and all(
            _best_class(user[k], stream[i + k], alt[i + k] if alt is not None else None)
            in ("equal", "completion")
            for k in range(n)
        ):
            return True
    return False


def _loose_window_starts(store: Store, quoted_text: str, n: int) -> list[int] | None:
    """Every global start position of the quote's LOOSE token sequence, inside one stream document."""
    ids = [store.token_id(t) for t in loose_tokens(quoted_text)]
    if len(ids) != n or any(i < 0 for i in ids):
        return None
    cand = store.postings(ids[0]).astype("int64")
    for j in range(1, n):
        cand = cand[cand + j < len(store.G)]
        cand = cand[store.G[cand + j] == ids[j]]
    return [g for g in cand.tolist() if int(store.g_doc[g]) == int(store.g_doc[g + n - 1])]


def _spelling_is_unique(store: Store, starts: list[int], user: list[str]) -> bool:
    """(c) of V7: across every corpus position of the bare window, exactly one strict spelling."""
    n = len(user)
    spellings: set[tuple[str, ...]] = set()
    for g in starts:
        prim = store.strict_tokens_range(g, n)
        altt = store.strict_alt_tokens_range(g, n)
        # same pick as match/rasm.prove: the rasm variant closest to the user's token
        chosen = tuple(
            p if _RANK[classify_token(user[k], p)] <= _RANK[classify_token(user[k], a)] else a
            for k, (p, a) in enumerate(zip(prim, altt, strict=True))
        )
        spellings.add(chosen)
        if len(spellings) > 1:
            return False
    return len(spellings) == 1


def prove_rasm_found(store: Store, q: QuoteResult) -> bool:
    """V7: re-derive the rasm-uniqueness proof from the Store alone (see module docstring).

    Uses the loose positional index for the window census (the same primitive as the matcher, on
    ids only) and the strict streams for the spelling census. No pipeline object is consulted.
    """
    if not q.matches:
        return False
    user = strict_tokens(q.quoted_text)
    if not user:
        return False
    rec = _lookup(store, q.matches[0])
    if rec is None or not any(
        _bare_window_is_completion(stream, alt, user) for stream, alt in _proof_streams(store, rec)
    ):
        return False
    starts = _loose_window_starts(store, q.quoted_text, len(user))
    return bool(starts) and _spelling_is_unique(store, starts or [], user)


def _proven(store: Store, q: QuoteResult) -> bool:
    """V7 for a rasm-completed `found` (its strict tokens are not a window by construction), V6 otherwise."""
    if "rasm_completed" in q.notice_keys:
        return prove_rasm_found(store, q)
    return prove_found(store, q)


def _unproven(q: QuoteResult) -> None:
    q.status = "needs_review"
    q.review_reason = "validator_unproven"
    q.message_key = "needs_review_unproven"
    q.notice_keys = [k for k in q.notice_keys if k != "quran_fragment"]


def _reject(q: QuoteResult) -> None:
    q.status = "needs_review"
    q.review_reason = "validator_reject"
    q.message_key = "needs_review_failure"
    q.matches = []
    q.notice_keys = [k for k in q.notice_keys if k in {"image_extracted"}]
    q.total_positions = 0
    q.score = 0.0


def validate_response(
    resp: CheckResponse, store: Store, messages_dir: Path, *, hadeethenc_link: bool = False
) -> CheckResponse:
    rejections = 0
    for q in resp.quotes:
        bad = False
        for m in q.matches:
            if not _match_ok(store, m, hadeethenc_link=hadeethenc_link):
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
        elif q.status == "found" and not _proven(store, q):  # V6 / V7
            _unproven(q)
            rejections += 1
        elif q.status != "found" and attribution_only_kind(q.quoted_text) is not None:  # B05
            _attribution_only(q)  # wording, not a rejection: «لم يوجد» would read as a verdict on a non-text
    # V5
    ar = load_messages(messages_dir, "ar")
    if not (ar.has("fixed", resp.disclaimer_key) and ar.has("fixed", resp.transparency_key)):
        resp.disclaimer_key = "footer"
        resp.transparency_key = "transparency_notice"
    resp.validator_rejections = rejections
    return resp
