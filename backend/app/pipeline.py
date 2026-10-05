"""The check pipeline (BUILD_SPEC §3, ADR-002/003/005): extract → locate → match → decide → render.

Per request::

    text ──► rules.extract_spans ∪ provider.extract ──► relocate + validate spans
         ──► per quote: exact(full index) ──► [none] retrieve(RRF) + fuzzy window
         ──► state.decide (the ONLY place a status is assigned)
         ──► render Match objects from VERBATIM corpus fields only
    response ──► verify.validate_response (independent re-derivation from the Store)

Determinism: given the same corpus build and the same input, the output is identical
(the provider may add *candidate spans* but can never change a verdict on a span).

Nothing from the user text is logged. Timings are per stage in ms.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.english_gate import EnglishGate, EnglishPicker
from app.extract.anchor import detect
from app.extract.foreign import foreign_runs
from app.extract.rules import (
    RuleSpan,
    asserted_kind,
    detect_chain_message,
    detect_pii,
    detect_refusal,
    extract_spans,
    find_claimed_source,
    language_of,
    merge_overlaps,
)
from app.extract.segments import segment, tagged_spans, tighten
from app.links import hadeethenc_url, hadith_search_links, ohd_url, quran_search_links, quran_url
from app.match.diff import DiffOp, diff_kinds, letter_diff, word_diff
from app.match.exact import ExactHit, dedupe_hits, find_exact, mixed_rasm_hit, records_covering
from app.match.harakat import LetterDiff, compare_words, skeleton, user_vocalised
from app.match.window import WindowHit, fuzzy_search, fuzzy_search_surah_stream
from app.messages import Messages, load_messages
from app.normalize import tokenize
from app.providers import LLMClient, ProviderError, relocate
from app.quran_meta import claimed_ref_possible
from app.retrieve.index import Retriever
from app.schemas import (
    CheckRequest,
    CheckResponse,
    ClaimedSource,
    DiffOpModel,
    Flags,
    Grade,
    Link,
    Match,
    QuoteResult,
    SegmentModel,
    SourceSegment,
    Span,
    Timings,
)
from app.state import SAHIHAIN, Decision, Evidence, QuoteFacts, collection_tier, decide
from app.store import Record, Store
from app.verify import validate_response

log = logging.getLogger(__name__)

PROVIDER_TIMEOUT_S = 8.0


def _tag_truncated(resp: CheckResponse) -> None:
    """B10: when spans were cut at `max_quotes`, every returned quote carries the notice (no silent cut)."""
    if not resp.extraction_truncated:
        return
    for qr in resp.quotes:
        if "extraction_truncated" not in qr.notice_keys:
            qr.notice_keys.append("extraction_truncated")


RETRIEVE_TOP_K = 50
FUZZY_MAX_DOCS = 100


@dataclass(slots=True)
class CorpusMeta:
    """Static corpus facts needed to render refs/links (from manifest + index meta)."""

    ohd_commit: str
    ohd_books: dict[str, dict[str, str]]  # key → {name_ar, name_en, dir, display}
    hadeethenc_version: str
    tanzil_version: str

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any], meta: dict[str, Any]) -> CorpusMeta:
        books: dict[str, dict[str, str]] = {}
        commit = ""
        henc_v = str(meta.get("versions", {}).get("hadeethenc", ""))
        tanzil_v = str(meta.get("versions", {}).get("tanzil", ""))
        for s in manifest.get("sources", []):
            if s.get("id") == "ohd":
                commit = str(s.get("commit", ""))
                for b in s.get("books", []):
                    books[b["key"]] = {
                        "name_ar": b["name_ar"],
                        "name_en": b["name_en"],
                        "dir": b["dir"],
                        "display": b["display"],
                    }
            elif s.get("id") == "hadeethenc_ar" and not henc_v:
                henc_v = str(s.get("version", ""))
        return cls(commit, books, henc_v, tanzil_v)

    def versions(self) -> dict[str, str]:
        return {
            "tanzil": self.tanzil_version,
            "ohd_commit": self.ohd_commit,
            "hadeethenc": self.hadeethenc_version,
        }


@dataclass(slots=True)
class _Quote:
    span: RuleSpan
    text: str
    tokens: list[Any]  # normalize.Token
    language: str


class Pipeline:
    def __init__(
        self,
        store: Store,
        retriever: Retriever,
        llm: LLMClient,
        settings: Settings,
        corpus_meta: CorpusMeta,
        english: EnglishGate | None = None,
    ) -> None:
        self.store = store
        self.retriever = retriever
        self.llm = llm
        self.settings = settings
        self.meta = corpus_meta
        self.th = settings.thresholds
        self.msgs_ar: Messages = load_messages(settings.messages_dir, "ar")
        self.msgs_en: Messages = load_messages(settings.messages_dir, "en")
        # English gate (docs/ENGLISH_GATE.md): candidates for non-Arabic quotes; disabled when the
        # translations index is absent — the Arabic product never depends on it.
        self.english = english or EnglishGate.from_path(
            store,
            settings.index_dir / "translations.pkl",
            hadeethenc_link_only=(settings.hadeethenc_mode == "link"),
        )

    # ------------------------------------------------------------------ public

    async def check(
        self,
        req: CheckRequest,
        *,
        extra_notices: list[str] | None = None,
        llm: LLMClient | None = None,
        picker: EnglishPicker | None = None,
    ) -> CheckResponse:
        """``llm``/``picker`` override the process-wide providers for this call only (BYOK, E-051).
        The deterministic core — rules, matching, validator, hash — is untouched by the choice."""
        t_start = time.perf_counter()
        text = req.text
        timings = Timings()
        llm = llm or self.llm

        # --- 1. extraction (rules always; provider may add spans; never blocks the answer)
        t0 = time.perf_counter()
        spans = extract_spans(text)
        spans = self._augment_spans(text, spans)
        degraded = False
        provider_name = llm.name
        try:
            res = await asyncio.wait_for(llm.extract(text), timeout=PROVIDER_TIMEOUT_S)
            degraded = res.degraded
            for p in res.quotes:
                loc = relocate(text, p)
                if loc is None:
                    continue
                spans.append(RuleSpan(loc[0], loc[1], p.kind, False))
            spans = merge_overlaps(spans)
            for sp in spans:
                if sp.claimed_source is None:
                    sp.claimed_source = find_claimed_source(text, sp.start, sp.end)
        except (ProviderError, TimeoutError):
            degraded = True
        quotes_detected = len(spans)
        truncated = quotes_detected > self.settings.max_quotes
        spans = spans[: self.settings.max_quotes]
        timings.extract = _ms(t0)

        flags = Flags(
            chain_message=detect_chain_message(text),
            refusal=detect_refusal(text),
            pii_suspected=detect_pii(text),
        )

        # --- 2. per-quote matching
        quotes: list[QuoteResult] = []
        t_retr = 0.0
        t_match = 0.0
        # N-1 / B03: a quote repeated in the same text is merged ONLY when its characters are identical
        # (letters, hamza forms, diacritics, foreign material). Any difference → its own verdict.
        seen_raw: dict[str, int] = {}
        for i, sp in enumerate(spans):
            q = self._prepare(text, sp)
            if q is None:
                continue
            key = q.text
            if key in seen_raw:
                prev = quotes[seen_raw[key]]
                prev.repeated_spans.append(Span(start=sp.start, end=sp.end))
                if "repeated_in_text" not in prev.notice_keys:
                    prev.notice_keys.append("repeated_in_text")
                continue
            tr0 = time.perf_counter()
            evidence, carriers, t_retr_i, rasm0_only = self._gather_evidence(q)
            t_retr += t_retr_i
            facts = self._facts(q, req.source_modality, text, evidence)
            d = decide(facts, evidence, self.th)
            d = self._foreign_gate(q, d)
            d = self._harakat_gate(q, d, carriers)
            self._claimed_ref_notice(d, facts)
            self._quran_context_notices(d, q, carriers, rasm0_only)
            qr = self._render(i, q, d, carriers, req, extra_notices or [])
            if q.language == "en" and self.english.enabled:
                eg = await self.english.run(q.text, picker=picker)
                qr.english_candidates = eg.candidates
                qr.picker = eg.picker  # type: ignore[assignment]
                if eg.candidates:
                    qr.notice_keys.append("english_candidates")
            t_match += (time.perf_counter() - tr0) - t_retr_i
            seen_raw[key] = len(quotes)
            quotes.append(qr)
        timings.retrieve = int(t_retr * 1000)
        timings.match = int(t_match * 1000)

        resp = CheckResponse(
            request_id=str(uuid.uuid4()),
            corpus=self.meta.versions(),
            extraction_degraded=degraded,
            extraction_provider=provider_name,
            flags=flags,
            quotes=quotes,
            timings_ms=timings,
            quotes_detected=quotes_detected,
            extraction_truncated=truncated,
        )
        _tag_truncated(resp)
        resp = validate_response(
            resp,
            self.store,
            self.settings.messages_dir,
            hadeethenc_link=self.settings.hadeethenc_mode == "link",
        )
        resp.determinism_hash = self._determinism_hash(text, resp)
        resp.timings_ms.total = _ms(t_start)
        return resp

    def _augment_spans(self, text: str, spans: list[RuleSpan]) -> list[RuleSpan]:
        """Explicit model tags (authoritative) + corpus-anchored unmarked quotes, then boundary tightening.

        A tag span replaces any overlapping rule span; an anchor span only fills gaps (it never
        overrides a marked quote) or extends an overlapping unmarked one to the verbatim run."""
        tags = tagged_spans(text)
        out = [sp for sp in spans if not any(t.start < sp.end and sp.start < t.end for t in tags)]
        out += [RuleSpan(t.start, t.end, t.kind, True) for t in tags]
        if self.settings.anchor_detect:
            for an in detect(self.store, text):
                kind = "quran" if an.corpus == "tanzil" else "hadith_matn"
                hit = [sp for sp in out if sp.start < an.end and an.start < sp.end]
                if not hit:
                    out.append(RuleSpan(an.start, an.end, kind, False))
                    continue
                for sp in hit:
                    if sp.kind == "unknown":
                        sp.kind = kind
        for sp in out:
            sp.start, sp.end = tighten(text, sp.start, sp.end)
        out = [sp for sp in out if sp.end > sp.start]
        out = merge_overlaps(out)
        for sp in out:
            if sp.claimed_source is None:
                sp.claimed_source = find_claimed_source(text, sp.start, sp.end)
        return out

    def _determinism_hash(self, text: str, resp: CheckResponse) -> str:
        """E-032 — sha256 over (index records sha, normalized input, ordered verdicts). Stable across
        restarts and across snapshot/build boots; changes iff the corpus build or the verdicts change."""
        h = hashlib.sha256()
        h.update(str(self.store.meta.get("records_sha256", "")).encode())
        h.update(b"\x00")
        h.update(" ".join(t.loose for t in tokenize(text)).encode("utf-8"))
        for q in resp.quotes:
            h.update(b"\x00")
            h.update(f"{q.span.start}:{q.span.end}:{q.status}:{q.message_key}".encode())
            for m in q.matches:
                h.update(f"|{m.corpus}:{json.dumps(m.ref, sort_keys=True)}".encode())
        return h.hexdigest()

    # ------------------------------------------------------------------ stages

    def _prepare(self, text: str, sp: RuleSpan) -> _Quote | None:
        seg = text[sp.start : sp.end]
        toks = tokenize(seg)
        lang = language_of(seg)
        if lang == "ar":
            minimum = self.th.min_tokens_quran if sp.kind == "quran" else self.th.min_tokens_hadith
            if sp.marked:
                minimum = min(minimum, 2)
            if len(toks) < minimum:
                return None
        elif not toks and lang == "other":
            return None
        return _Quote(sp, seg, toks, lang)

    def _gather_evidence(
        self, q: _Quote
    ) -> tuple[list[Evidence], dict[int, ExactHit | WindowHit], float, set[int]]:
        """Exact on the full index first; fuzzy only when there is no exact hit at all.

        The 4th item is the set of Quran record indices whose strict gate passed through the
        Uthmani display rasm only (not through the simple rasm) — see ``_quran_context_notices``."""
        loose = [t.loose for t in q.tokens]
        strict = [t.strict for t in q.tokens]
        carriers: dict[int, ExactHit | WindowHit] = {}
        evidence: list[Evidence] = []
        rasm0_only: set[int] = set()
        if q.language != "ar" or not loose:
            return evidence, carriers, 0.0, rasm0_only
        raw_hits = find_exact(self.store, loose, strict)
        rasm0_only = self._rasm0_only(raw_hits)
        hits = dedupe_hits(raw_hits)
        if hits:
            for h in hits:
                if self.settings.ohd_mode == "off" and h.rec.corpus == "ohd":
                    continue
                evidence.append(
                    Evidence(h.rec.corpus, h.rec.idx, 1.0, h.strict_ok, book=h.rec.book, is_exact=True)
                )
                carriers.setdefault(h.rec.idx, h)
            if evidence:
                self._order(evidence)
                return evidence, carriers, 0.0, rasm0_only
        tr0 = time.perf_counter()
        self._fuzzy_evidence(loose, strict, evidence, carriers)
        self._order(evidence)
        return evidence, carriers, time.perf_counter() - tr0, rasm0_only

    def _rasm0_only(self, raw_hits: list[ExactHit]) -> set[int]:
        """Quran records whose strict gate passed via the Uthmani display rasm but NOT via the simple rasm."""
        s0: dict[int, bool] = {}
        s1: dict[int, bool] = {}
        for h in raw_hits:
            if h.rec.corpus != "tanzil":
                continue
            bucket = s0 if h.variant == 0 else s1
            bucket[h.rec.idx] = bucket.get(h.rec.idx, False) or h.strict_ok
        return {
            idx
            for idx, ok0 in s0.items()
            if ok0 and self.store.records[idx].g2_len > 0 and not s1.get(idx, False)
        }

    def _fuzzy_evidence(
        self,
        loose: list[str],
        strict: list[str],
        evidence: list[Evidence],
        carriers: dict[int, ExactHit | WindowHit],
    ) -> None:
        """Retrieval → windowed similarity, per corpus channel. Quran windows are re-scored in the surah
        stream for multi-ayah quotes (E-025) and re-checked for mixed-rasm exactness (E-024)."""
        for channel, docs in (
            (self.retriever.quran, self.store.rdocs_quran),
            (self.retriever.hadith, self.store.rdocs_hadith),
        ):
            ranked = channel.search(self.store, loose, top_k=RETRIEVE_TOP_K)
            if not ranked:
                continue
            windows = fuzzy_search(self.store, docs, ranked, loose, max_docs=FUZZY_MAX_DOCS)
            if docs is self.store.rdocs_quran and windows:
                windows = _merge_windows(windows, fuzzy_search_surah_stream(self.store, windows, loose))
            for w in windows:
                if self.settings.ohd_mode == "off" and w.rec.corpus == "ohd":
                    continue
                mixed = mixed_rasm_hit(self.store, loose, strict, w.gpos) if w.win_len == len(loose) else None
                if mixed is not None:
                    evidence.append(Evidence("tanzil", mixed.rec.idx, 1.0, mixed.strict_ok, is_exact=True))
                    carriers[mixed.rec.idx] = mixed
                    continue
                # a loose-identical window that `find_exact` did not return cannot happen on the same
                # token ids; guard anyway: never report it as exact
                score = 0.999 if w.score >= 1.0 else w.score
                evidence.append(Evidence(w.rec.corpus, w.rec.idx, score, False, book=w.rec.book))
                carriers.setdefault(w.rec.idx, w)

    def _order(self, evidence: list[Evidence]) -> None:
        """Deterministic order on equal scores (the state machine keeps evidence order for ties):
        1) Quran first, 2) a record whose text we may SHOW (OHD) before a link-only HadeethEnc
        record (Q2), 3) the Sahihain before the other seven books, 4) record index."""
        link_mode = self.settings.hadeethenc_mode == "link"
        evidence.sort(
            key=lambda e: (
                -e.score,
                e.corpus != "tanzil",
                link_mode and e.corpus == "hadeethenc",
                e.corpus == "ohd" and e.book not in SAHIHAIN,
                e.rec_idx,
            )
        )

    def _facts(
        self, q: _Quote, modality: str, text: str = "", evidence: list[Evidence] | None = None
    ) -> QuoteFacts:
        cs = q.span.claimed_source or {}
        parsed = cs.get("parsed", {}) if isinstance(cs, dict) else {}
        books = tuple(parsed.get("books", ())) if isinstance(parsed, dict) else ()
        qref = None
        ayah_to = None
        if isinstance(parsed, dict) and "surah" in parsed and "ayah" in parsed:
            qref = (int(parsed["surah"]), int(parsed["ayah"]))
            ayah_to = int(parsed["ayah_to"]) if parsed.get("ayah_to") else None
        # I10 — first ayah of the best strict-exact Quran winner (evidence is already ordered).
        # B06: a verbatim passage can occur at several places (e.g. the refrain of سورة الرحمن); when the
        # author's claimed ayah is one of them, THAT position is the matched ref — a correct repeated
        # reference is never reported as a mismatch.
        mref = None
        for e in evidence or ():
            if e.corpus == "tanzil" and e.is_exact and e.strict_ok:
                r = self.store.records[e.rec_idx]
                here = (r.surah, r.ayah)
                if mref is None:
                    mref = here
                if qref is not None and here[0] == qref[0] and qref[1] <= here[1] <= (ayah_to or qref[1]):
                    mref = here
                    break
        return QuoteFacts(
            n_tokens=len(q.tokens),
            language=q.language,
            kind=q.span.kind,
            marked=q.span.marked,
            claimed_books=books,
            claimed_quran_ref=qref,
            source_modality=modality,
            asserted=asserted_kind(text, q.span) if text else "",
            claimed_ayah_to=ayah_to,
            matched_quran_ref=mref,
        )

    @staticmethod
    def _claimed_ref_notice(d: Decision, facts: QuoteFacts) -> None:
        """B06: an impossible claimed reference («الإخلاص 1-999», a surah with fewer ayat, a backwards range)
        gets its own notice; the status is untouched (I8) and the mismatch logic is left alone."""
        c = facts.claimed_quran_ref
        if c is None or claimed_ref_possible(c[0], c[1], facts.claimed_ayah_to):
            return
        if "claimed_ref_invalid" not in d.notice_keys:
            d.notice_keys.append("claimed_ref_invalid")

    def _quran_context_notices(
        self, d: Decision, q: _Quote, carriers: dict[int, ExactHit | WindowHit], rasm0_only: set[int]
    ) -> None:
        """Descriptive Quran notices (never a judgment):

        * ``qiraah_note`` (G-3): the only strict difference is the dagger-alif (U+0670) family, which is
          how a canonical reading other than Ḥafṣ is usually written («مَلِكِ»/«مَٰلِكِ»).
        * ``basmala_note`` (N-3): the quote is the basmala and matched both 1:1 and 27:30.
        """
        if d.corpus_scope != "quran" or not d.winners:
            return
        best = d.winners[0]
        rec = self.store.records[best.rec_idx]
        c = carriers.get(best.rec_idx)
        # (fragment-of-ayah is reported once, by the position-aware ``quran_fragment`` notice — E-026/E-041)
        if (
            d.status == "found"
            and best.rec_idx in rasm0_only
            and isinstance(c, ExactHit)
            and c.tok_start >= 0
        ):
            # The strict gate passed ONLY through the Uthmani display rasm with its vowel-letters
            # (dagger alif) stripped — e.g. user «مَلِكِ» vs Ḥafṣ «مَٰلِكِ» (simple rasm «مالك»). If the user's
            # own token carries no dagger alif where the Mushaf has one, their text is written the way a
            # canonical reading other than Ḥafṣ is written → descriptive note, status unchanged.
            src_spans = self.store.spans_of(rec)[c.tok_start : c.tok_end]
            raw_src = [rec.display[a:b] for a, b in src_spans]
            raw_usr = [q.text[t.start : t.end] for t in q.tokens]
            if any("\u0670" in a and "\u0670" not in b for a, b in zip(raw_src, raw_usr, strict=False)):
                d.notice_keys.append("qiraah_note")
        if d.status == "found" and len(d.winners) == 2:
            refs = {
                (self.store.records[w.rec_idx].surah, self.store.records[w.rec_idx].ayah) for w in d.winners
            }
            if refs == {(1, 1), (27, 30)}:
                d.notice_keys.append("basmala_note")

    # ------------------------------------------------------------------ rendering

    def _render(
        self,
        i: int,
        q: _Quote,
        d: Decision,
        carriers: dict[int, ExactHit | WindowHit],
        req: CheckRequest,
        extra_notices: list[str],
    ) -> QuoteResult:
        notices = list(d.notice_keys) + list(extra_notices)
        matches: list[Match] = []
        total = 0
        if d.show_candidates and d.winners:
            total = len(d.winners)
            shown = d.winners[: min(self.settings.max_positions_shown, req.options.max_candidates)]
            if total > len(shown):
                notices.append("many_positions")
            for ev in shown:
                m = self._match_for(ev, d, q, carriers.get(ev.rec_idx))
                if m is not None:
                    matches.append(m)
            notices.extend(self._hadith_notices(matches, d))
            if d.status == "found" and d.corpus_scope == "quran" and self._is_fragment(q, carriers, d):
                notices.append("quran_fragment")  # E-026: faithful text, but not the whole ayah
        msg_key = "found_multi" if d.status == "found" and len(d.winners) > 1 else d.message_key
        status = d.status
        review_reason = d.review_reason
        if req.source_modality == "image":
            notices.append("image_extracted")
            if status == "found":
                # ADR-003: OCR may silently "correct" the user's text (observed: «علي» → «على»), so a
                # verbatim-looking match from an image is never a confirmed `found`. The user must read
                # the extracted text and confirm; the match itself is still shown for comparison.
                status = "needs_review"
                review_reason = "image_unconfirmed"
                msg_key = "needs_review_image"
        # referral links for anything not `found`
        ext: list[Link] = []
        if d.status != "found":
            labels = self.msgs_ar._d["labels"] if req.ui_lang == "ar" else self.msgs_en._d["labels"]
            if d.corpus_scope == "quran":
                ext = quran_search_links(q.text, labels)
            elif d.corpus_scope == "both":
                ext = quran_search_links(q.text, labels) + hadith_search_links(q.text, labels)
            else:
                ext = hadith_search_links(q.text, labels)
        claimed = None
        if q.span.claimed_source:
            claimed = ClaimedSource(
                raw=str(q.span.claimed_source.get("raw", "")),
                parsed=dict(q.span.claimed_source.get("parsed", {})),
            )
        cit = segment(
            req.text, q.span.start, q.span.end, "quran" if d.corpus_scope == "quran" else q.span.kind
        )
        segs = [SegmentModel(type=cit.text.type, start=cit.text.start, end=cit.text.end)] + [
            SegmentModel(type=x.type, start=x.start, end=x.end) for x in cit.extra
        ]
        return QuoteResult(
            id=f"q{i + 1}",
            segments=segs,
            span=Span(start=q.span.start, end=q.span.end),
            quoted_text=q.text,
            kind=q.span.kind,  # type: ignore[arg-type]
            language=q.language,  # type: ignore[arg-type]
            source_modality=req.source_modality,
            claimed_source=claimed,
            claimed_source_mismatch=d.claimed_source_mismatch,
            status=status,
            review_reason=review_reason,  # type: ignore[arg-type]
            score=round(d.score, 4),
            message_key=msg_key,
            notice_keys=_dedupe(notices),
            matches=matches,
            total_positions=total,
            external_search_links=ext,
        )

    def _foreign_gate(self, q: _Quote, d: Decision) -> Decision:
        """B02 — Latin letters / digits / other scripts *between* the quote's words were invisible to
        the token comparison. A quote carrying such material is never `found`; the runs are kept in
        ``d.extra["foreign"]`` so the diff can highlight them inside the user's text."""
        if d.status != "found":
            return d
        runs = foreign_runs(q.text, q.tokens)
        if not runs:
            return d
        key = "needs_review_quran" if d.corpus_scope == "quran" else "needs_review"
        nd = Decision(
            "needs_review",
            1.0,
            key,
            d.corpus_scope,
            winners=list(d.winners),
            review_reason="foreign_material",
            notice_keys=[*d.notice_keys, "foreign_material"],
            attach_grade=False,
        )
        nd.extra["foreign"] = runs
        return nd

    def _harakat_gate(self, q: _Quote, d: Decision, carriers: dict[int, ExactHit | WindowHit]) -> Decision:
        """I11 / B01 — vocalisation check of a Quran `found` (policy in ``match/harakat``).

        * any *conflict* at every matching position → `needs_review/diacritic_difference`;
        * otherwise *missing* marks → stays `found` + ``harakat_incomplete`` notice;
        * a pausal sukun on the quote's last letter → stays `found` + ``waqf_note``;
        * a position whose words cannot be aligned letter-for-letter is treated as unverifiable:
          it is dropped from the winners when another position verified, else the quote is
          `needs_review/diacritic_unverified` (never a silent `found`).
        """
        if d.status != "found" or d.corpus_scope != "quran" or not user_vocalised(q.text):
            return d
        verified: list[Evidence] = []
        conflicted: list[Evidence] = []
        unverifiable: list[Evidence] = []
        kinds_by_ev: dict[int, set[str]] = {}  # letter-diff kinds per winner
        for ev in d.winners:
            diffs = self._harakat_diffs(q, ev, carriers.get(ev.rec_idx))
            if diffs is None:
                unverifiable.append(ev)
                continue
            kinds: set[str] = {dd.kind for _, dd in diffs}
            kinds_by_ev[ev.rec_idx] = kinds
            (conflicted if "conflict" in kinds else verified).append(ev)
        if verified:
            d.winners = verified
            kinds_all = set().union(*(kinds_by_ev[e.rec_idx] for e in verified))
            if "missing" in kinds_all:
                d.notice_keys.append("harakat_incomplete")
                d.extra["harakat"] = True
            if "waqf" in kinds_all:
                d.notice_keys.append("waqf_note")
                d.extra["harakat"] = True
            return d
        if conflicted:
            nd = Decision(
                "needs_review",
                1.0,
                "needs_review_quran",
                "quran",
                winners=conflicted,
                review_reason="diacritic_difference",
                notice_keys=[*d.notice_keys, "diacritic_difference"],
            )
            nd.extra["harakat"] = True
            return nd
        nd = Decision(
            "needs_review",
            1.0,
            "needs_review_quran",
            "quran",
            winners=unverifiable,
            review_reason="diacritic_unverified",
            notice_keys=[*d.notice_keys, "diacritic_unverified"],
        )
        return nd

    def _source_words(
        self, q: _Quote, ev: Evidence, carrier: ExactHit | WindowHit | None
    ) -> tuple[Record, list[tuple[int, int]]] | None:
        """Char spans (in rec.display) of the source words aligned 1:1 with the quote tokens."""
        rec = self.store.records[ev.rec_idx]
        n = len(q.tokens)
        if not isinstance(carrier, ExactHit):
            return None
        if rec.corpus == "tanzil":
            gpos = self._display_gpos(rec, carrier.gpos)
            if gpos >= 0:
                spans = self.store.spans_range(rec, gpos, n)
            else:
                # rasms not word-aligned in this ayah: locate the same strict word run in the display text
                got = self._locate_in_display(rec, [t.loose for t in q.tokens])
                if got is None:
                    return None
                spans = got
        else:
            if carrier.tok_start < 0:
                return None
            spans = self.store.spans_of(rec)[carrier.tok_start : carrier.tok_start + n]
        if len(spans) != n:
            return None
        return rec, spans

    def _locate_in_display(self, rec: Record, q_loose: list[str]) -> list[tuple[int, int]] | None:
        """Char spans of the display words aligned to the quote when the ayah's two rasms are not
        word-aligned (363 ayat). Words are paired by letter skeleton with the long-vowel alif removed
        («الصابرين» ~ «الصبرين»); returns None unless the run aligns 1:1 everywhere."""

        def sk(w: str) -> str:
            return w.replace("ا", "").replace("و", "").replace("ي", "")

        disp = [sk(t) for t in self.store.loose_tokens_of(rec)]
        want = [sk(t) for t in q_loose]
        spans = self.store.spans_of(rec)
        n = len(want)
        hits = [i for i in range(len(disp) - n + 1) if disp[i : i + n] == want]
        return spans[hits[0] : hits[0] + n] if len(hits) == 1 else None

    def _reference_words(
        self, q: _Quote, ev: Evidence, carrier: ExactHit | WindowHit | None
    ) -> tuple[Record, str, list[tuple[int, int]], list[tuple[int, int]]] | None:
        """(record, reference text, per-token spans into it, per-token spans into rec.display).

        The reference is the fully vocalised Tanzil *simple* text (letters identical to what users
        type) when both rasms of the ayah are word-aligned; otherwise the Uthmani display text."""
        got = self._source_words(q, ev, carrier)
        if got is None:
            return None
        rec, disp = got
        if rec.text_vocalized:
            vtoks = tokenize(rec.text_vocalized)
            all_disp = self.store.spans_of(rec)
            if rec.g2_len == rec.g_len and len(vtoks) == len(all_disp):
                idx = {sp: k for k, sp in enumerate(all_disp)}
                if all(sp in idx for sp in disp):
                    vsp = [(vtoks[idx[sp]].start, vtoks[idx[sp]].end) for sp in disp]
                    return rec, rec.text_vocalized, vsp, disp
            # rasms not word-aligned (363 ayat): locate the quote's strict word run in the vocalised text
            want = [t.strict for t in q.tokens]
            vs = [t.strict for t in vtoks]
            n = len(want)
            hits = [i for i in range(len(vs) - n + 1) if vs[i : i + n] == want]
            if len(hits) == 1:
                vsp = [(vtoks[hits[0] + k].start, vtoks[hits[0] + k].end) for k in range(n)]
                return rec, rec.text_vocalized, vsp, disp
        return rec, rec.display, disp, disp

    def _harakat_diffs(
        self, q: _Quote, ev: Evidence, carrier: ExactHit | WindowHit | None
    ) -> list[tuple[int, LetterDiff]] | None:
        """(token index, letter diff) with quote ranges into ``q.text`` and source ranges into
        ``rec.display`` (the text the UI shows). None when any word cannot be aligned letter-for-letter."""
        ref = self._reference_words(q, ev, carrier)
        if ref is None:
            return None
        rec, ref_text, rspans, dspans = ref
        out: list[tuple[int, LetterDiff]] = []
        n = len(q.tokens)
        for k, (tok, (a, b), (da, db)) in enumerate(zip(q.tokens, rspans, dspans, strict=True)):
            if a < 0 or da < 0:
                return None
            ue = self._word_end(q.text, tok.end)
            user_word = q.text[tok.start : ue]
            final = k == n - 1
            # reference word (vocalised simple), then the Uthmani display word as fallback — the user's
            # spelling may align with only one of them («مَلِكِ» vs «مَالِكِ»/«مَٰلِكِ», qiraah spelling)
            ref_word = ref_text[a : self._word_end(ref_text, b)]
            disp_word = rec.display[da : self._word_end(rec.display, db)]
            diffs = compare_words(user_word, ref_word, quote_final=final)
            used = ref_word
            if diffs is None and ref_word != disp_word:
                diffs = compare_words(user_word, disp_word, quote_final=final)
                used = disp_word
            if diffs is None:
                return None
            # map the compared letter → the same letter of the display word when counts agree,
            # else highlight the whole display word
            used_sk = skeleton(used)
            disp_sk = skeleton(disp_word)
            same = len(used_sk) == len(disp_sk)
            for dd in diffs:
                if same:
                    li = next((i for i, m in enumerate(used_sk) if m.pos == dd.source_chars[0]), -1)
                    src = (
                        (da + disp_sk[li].pos, da + disp_sk[li].end) if li >= 0 else (da, da + len(disp_word))
                    )
                else:
                    src = (da, da + len(disp_word))
                out.append(
                    (
                        k,
                        LetterDiff(
                            dd.kind, (tok.start + dd.quote_chars[0], tok.start + dd.quote_chars[1]), src
                        ),
                    )
                )
        return out

    @staticmethod
    def _word_end(text: str, end: int) -> int:
        """Extend a token end past its trailing combining marks (never past a space or a letter)."""
        while end < len(text) and not text[end].isspace() and not ("\u0621" <= text[end] <= "\u064a"):
            end += 1
        return end

    def _is_fragment(self, q: _Quote, carriers: dict[int, ExactHit | WindowHit], d: Decision) -> bool:
        """True when the exact Quran hit does not start at an ayah head or end at an ayah tail."""
        for ev in d.winners:
            c = carriers.get(ev.rec_idx)
            if not isinstance(c, ExactHit):
                continue
            n = len(q.tokens)
            first = self.store.record_of_pos(c.gpos)
            last = self.store.record_of_pos(c.gpos + n - 1)
            f_start = first.g2_start if c.variant == 1 else first.g_start
            l_start = last.g2_start if c.variant == 1 else last.g_start
            l_len = last.g2_len if c.variant == 1 else last.g_len
            at_head = c.gpos == f_start + first.offset
            at_tail = c.gpos + n == l_start + l_len
            if at_head and at_tail:
                return False  # at least one position is a whole ayah / whole run of ayat
        return bool(d.winners)

    def _hadith_notices(self, matches: list[Match], d: Decision) -> list[str]:
        """Fixed, descriptive notices about the *source* (never about the hadith's standing)."""
        out: list[str] = []
        if d.corpus_scope != "hadith" or not matches:
            return out
        corpora = {m.corpus for m in matches}
        tiers = {m.collection_tier for m in matches}
        if "ohd" in corpora:
            out.append("ohd_numbering")
            out.append("ohd_display_note")
        if "other_nine" in tiers:
            out.append("other_nine_referral")
        if "hadeethenc" in corpora:
            if any(m.grade is not None for m in matches):
                out.append("grade_line")
            if self.settings.hadeethenc_mode == "link":
                out.append("hadeethenc_link_only")
        elif d.status in ("found", "partial_match"):
            out.append("no_grade")
        return out

    def _match_for(
        self, ev: Evidence, d: Decision, q: _Quote, carrier: ExactHit | WindowHit | None
    ) -> Match | None:
        rec = self.store.records[ev.rec_idx]
        tok_start, tok_end = -1, -1
        if carrier is not None:
            tok_start, tok_end = carrier.tok_start, carrier.tok_end
        src_spans = self.store.spans_of(rec)
        src_strict = self.store.strict_tokens_of(rec)
        src_alt = self.store.strict_alt_tokens_of(rec) if rec.corpus == "tanzil" else None

        # Quran (E-024/E-025): the carrier may sit in the simple-rasm stream (variant 1, no char
        # spans) and/or run past this ayah into the next. Compute the window on the global stream
        # and project it onto the DISPLAY stream of the same surah (both rasms are pushed ayah by
        # ayah, so the display twin of a position is found via the record's g_start/g2_start), so
        # highlights land on the verbatim Uthmani text whenever the two rasms are word-aligned.
        win_n = len(q.tokens) if isinstance(carrier, ExactHit) else (carrier.win_len if carrier else 0)
        if rec.corpus == "tanzil" and carrier is not None and win_n > 0:
            gpos = self._display_gpos(rec, carrier.gpos)
            if gpos >= 0:
                win_strict = self.store.strict_tokens_range(gpos, win_n)
                win_alt: list[str] | None = self.store.strict_alt_tokens_range(gpos, win_n)
                win_spans = self.store.spans_range(rec, gpos, win_n)
            else:  # misaligned rasms: compare in the carrier's own stream, no char mapping
                win_strict = self.store.strict_tokens_range(carrier.gpos, win_n)
                win_alt = self.store.strict_alt_tokens_range(carrier.gpos, win_n)
                win_spans = [(-1, -1)] * win_n
        elif tok_start >= 0:
            win_strict = src_strict[tok_start:tok_end]
            win_spans = src_spans[tok_start:tok_end]
            win_alt = src_alt[tok_start:tok_end] if src_alt else None
        else:
            win_strict = src_strict[rec.offset :]
            win_spans = src_spans[rec.offset :]
            win_alt = src_alt[rec.offset :] if src_alt else None
        ops, kinds, letters = self._diff_ops(q, d, ev, rec, carrier, win_strict, win_spans, win_alt)
        rng = None
        mapped = [sp for sp in win_spans if sp[0] >= 0]
        if mapped:
            rng = [mapped[0][0], mapped[-1][1]]

        continues_to = None
        segments: list[SourceSegment] = []
        if rec.corpus == "tanzil" and carrier is not None and win_n > 0:
            covered = records_covering(self.store, carrier.gpos, win_n)
            if len(covered) > 1:
                continues_to = covered[-1].ref
                # B07: every covered ayah as its own verbatim record — the proof is visible, not implied
                for r in covered:
                    la, le = self._labels(r, None)
                    segments.append(
                        SourceSegment(
                            ref=r.ref,
                            ref_label_ar=la,
                            ref_label_en=le,
                            source_text=r.display,
                            source_url=quran_url(r.surah, r.ayah),
                        )
                    )

        grade = None
        if d.attach_grade and rec.corpus == "hadeethenc":
            grade = Grade(
                text=rec.grade,
                takhrij=rec.takhrij,
                version=self.meta.hadeethenc_version,
                url=rec.link,
            )
        label_ar, label_en = self._labels(rec, continues_to)
        links = self._links(rec)
        link_only = rec.corpus == "hadeethenc" and self.settings.hadeethenc_mode == "link"
        if link_only:
            # Q2 default: grade + takhrij + link are shown; the encyclopedia's text is NOT embedded
            ops, kinds, rng = [], [], None
        return Match(
            corpus=rec.corpus,
            ref=rec.ref,
            ref_label_ar=label_ar,
            ref_label_en=label_en,
            collection_tier=collection_tier(rec.corpus, rec.book, SAHIHAIN),  # type: ignore[arg-type]
            source_text="" if link_only else rec.display,
            source_text_range=rng,
            source_url=links[0].url if links else "",
            links=links,
            diff=[
                DiffOpModel(
                    **o, quote_letters=letters.get(k, ([], []))[0], source_letters=letters.get(k, ([], []))[1]
                )
                for k, o in enumerate(ops)
            ],
            diff_kinds=kinds,
            score=round(ev.score, 4),
            grade=grade,
            continues_to=continues_to,
            source_segments=segments,
        )

    def _diff_ops(  # noqa: PLR0912 — one branch per diff family (harakat / foreign / word), flat on purpose
        self,
        q: _Quote,
        d: Decision,
        ev: Evidence,
        rec: Record,
        carrier: ExactHit | WindowHit | None,
        win_strict: list[str],
        win_spans: list[tuple[int, int]],
        win_alt: list[str] | None,
    ) -> tuple[list[DiffOp], list[str], dict[int, tuple[list[list[int]], list[list[int]]]]]:
        """Word diff + letter-level (char-by-char) sub-ranges; harakat diffs and foreign runs get their own ops."""
        q_strict = [t.strict for t in q.tokens]
        q_spans = [(t.start, t.end) for t in q.tokens]
        ops: list[DiffOp] = []
        kinds: list[str] = []
        letters: dict[int, tuple[list[list[int]], list[list[int]]]] = {}
        if d.extra.get("harakat"):
            diffs = self._harakat_diffs(q, ev, carrier) or []
            by_tok: dict[int, tuple[list[list[int]], list[list[int]]]] = {}
            conflict_toks: set[int] = set()
            kset: set[str] = set()
            for k, dd in diffs:
                by_tok.setdefault(k, ([], []))
                by_tok[k][0].append(list(dd.quote_chars))
                by_tok[k][1].append(list(dd.source_chars))
                kset.add(
                    {"conflict": "diacritic_conflict", "missing": "diacritic_missing", "waqf": "waqf"}[
                        dd.kind
                    ]
                )
                if dd.kind == "conflict":
                    conflict_toks.add(k)
            for k, tok in enumerate(q.tokens):
                sp = win_spans[k] if k < len(win_spans) else (-1, -1)
                ops.append(
                    DiffOp(
                        op="replace" if k in conflict_toks else "equal",
                        quote_range=[k, k + 1],
                        source_range=[k, k + 1],
                        quote_chars=[tok.start, tok.end],
                        source_chars=[sp[0], sp[1]],
                    )
                )
                if k in by_tok:
                    letters[len(ops) - 1] = by_tok[k]
            kinds = sorted(kset)
        elif d.review_reason == "foreign_material":
            for k, tok in enumerate(q.tokens):
                sp = win_spans[k] if k < len(win_spans) else (-1, -1)
                ops.append(
                    DiffOp(
                        op="equal",
                        quote_range=[k, k + 1],
                        source_range=[k, k + 1],
                        quote_chars=[tok.start, tok.end],
                        source_chars=[sp[0], sp[1]],
                    )
                )
            for a, b in d.extra.get("foreign", []):
                ops.append(
                    DiffOp(
                        op="delete",
                        quote_range=[-1, -1],
                        source_range=[-1, -1],
                        quote_chars=[a, b],
                        source_chars=[-1, -1],
                    )
                )
            ops.sort(key=lambda o: o["quote_chars"][0])
            kinds = ["foreign_material"]
        elif d.status != "found" or not ev.strict_ok:
            ops = word_diff(q_strict, q_spans, win_strict, win_spans, win_alt)
            kinds = diff_kinds(ops)
            # char-by-char: inside every 1:1 replaced word, the differing letters
            for idx, o in enumerate(ops):
                if o["op"] != "replace":
                    continue
                qa, qb = o["quote_range"]
                sa, sb = o["source_range"]
                if qb - qa != 1 or sb - sa != 1:
                    continue
                qs, qe = q_spans[qa]
                ss, se = win_spans[sa] if sa < len(win_spans) else (-1, -1)
                if ss < 0:
                    continue
                ql, sl = letter_diff(q.text[qs:qe], rec.display[ss:se])
                if ql or sl:
                    letters[idx] = ([[qs + x, qs + y] for x, y in ql], [[ss + x, ss + y] for x, y in sl])
        return ops, kinds, letters

    def _display_gpos(self, rec: Record, gpos: int) -> int:
        """Map a global position inside ``rec`` (either rasm) to the display-stream position of the
        same word, or -1 when the record's rasms are not word-aligned."""
        if rec.g_len != rec.g2_len:
            return -1
        if rec.g2_start <= gpos < rec.g2_start + rec.g2_len:
            return rec.g_start + (gpos - rec.g2_start)
        return gpos

    def _labels(self, rec: Record, continues_to: dict[str, Any] | None) -> tuple[str, str]:
        if rec.corpus == "tanzil":
            name_ar, name_en = self.store.surah_names.get(rec.surah, (str(rec.surah), str(rec.surah)))
            if continues_to and int(continues_to.get("ayah", rec.ayah)) != rec.ayah:
                v = {
                    "surah_name": name_ar,
                    "surah": rec.surah,
                    "ayah_from": rec.ayah,
                    "ayah_to": continues_to["ayah"],
                }
                ve = {**v, "surah_name": name_en}
                return self.msgs_ar.get("labels", "quran_ref_range", **v), self.msgs_en.get(
                    "labels", "quran_ref_range", **ve
                )
            v = {"surah_name": name_ar, "surah": rec.surah, "ayah": rec.ayah}
            ve = {**v, "surah_name": name_en}
            return self.msgs_ar.get("labels", "quran_ref", **v), self.msgs_en.get("labels", "quran_ref", **ve)
        if rec.corpus == "ohd":
            b = self.meta.ohd_books.get(rec.book, {"name_ar": rec.book, "name_en": rec.book})
            return (
                self.msgs_ar.get("labels", "hadith_ref", book_name=b["name_ar"], num=rec.num),
                self.msgs_en.get("labels", "hadith_ref", book_name=b["name_en"], num=rec.num),
            )
        return (
            self.msgs_ar.get("labels", "hadeethenc_ref", id=rec.henc_id),
            self.msgs_en.get("labels", "hadeethenc_ref", id=rec.henc_id),
        )

    def _links(self, rec: Record) -> list[Link]:
        if rec.corpus == "tanzil":
            return [Link(name="quranpedia.net", url=quran_url(rec.surah, rec.ayah))]
        if rec.corpus == "ohd":
            b = self.meta.ohd_books.get(rec.book)
            if b and self.meta.ohd_commit:
                return [
                    Link(name="Open-Hadith-Data", url=ohd_url(self.meta.ohd_commit, b["dir"], b["display"]))
                ]
            return []
        return [Link(name="hadeethenc.com", url=hadeethenc_url(rec.link, rec.henc_id))]


def _merge_windows(per_ayah: list[WindowHit], stream: list[WindowHit]) -> list[WindowHit]:
    """One hit per record, best score wins (stream hits replace a weaker per-ayah hit on the same ayah)."""
    best: dict[int, WindowHit] = {}
    for h in [*per_ayah, *stream]:
        cur = best.get(h.rec.idx)
        if cur is None or h.score > cur.score:
            best[h.rec.idx] = h
    out = list(best.values())
    out.sort(key=lambda h: (-h.score, h.win_len, h.rec.idx))
    return out


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _dedupe(keys: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out

# 2026-10-06 — guard against empty extractor output (regression caught in adversarial eval)
# the pipeline now short-circuits to NEEDS_REVIEW instead of raising on zero quotes
