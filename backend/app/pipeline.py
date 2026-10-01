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
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.extract.rules import (
    RuleSpan,
    detect_chain_message,
    detect_pii,
    detect_refusal,
    extract_spans,
    find_claimed_source,
    language_of,
    merge_overlaps,
)
from app.links import hadeethenc_url, hadith_search_links, ohd_url, quran_search_links, quran_url
from app.match.diff import DiffOp, diff_kinds, word_diff
from app.match.exact import ExactHit, dedupe_hits, find_exact, mixed_rasm_hit, records_covering
from app.match.window import WindowHit, fuzzy_search, fuzzy_search_surah_stream
from app.messages import Messages, load_messages
from app.normalize import tokenize
from app.providers import LLMClient, ProviderError, relocate
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
    Span,
    Timings,
)
from app.state import SAHIHAIN, Decision, Evidence, QuoteFacts, collection_tier, decide
from app.store import Record, Store
from app.verify import validate_response

log = logging.getLogger(__name__)

PROVIDER_TIMEOUT_S = 8.0
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
    ) -> None:
        self.store = store
        self.retriever = retriever
        self.llm = llm
        self.settings = settings
        self.meta = corpus_meta
        self.th = settings.thresholds
        self.msgs_ar: Messages = load_messages(settings.messages_dir, "ar")
        self.msgs_en: Messages = load_messages(settings.messages_dir, "en")

    # ------------------------------------------------------------------ public

    async def check(self, req: CheckRequest, *, extra_notices: list[str] | None = None) -> CheckResponse:
        t_start = time.perf_counter()
        text = req.text
        timings = Timings()

        # --- 1. extraction (rules always; provider may add spans; never blocks the answer)
        t0 = time.perf_counter()
        spans = extract_spans(text)
        degraded = False
        provider_name = self.llm.name
        try:
            res = await asyncio.wait_for(self.llm.extract(text), timeout=PROVIDER_TIMEOUT_S)
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
        for i, sp in enumerate(spans):
            q = self._prepare(text, sp)
            if q is None:
                continue
            tr0 = time.perf_counter()
            evidence, carriers, t_retr_i = self._gather_evidence(q)
            t_retr += t_retr_i
            facts = self._facts(q, req.source_modality)
            d = decide(facts, evidence, self.th)
            qr = self._render(i, q, d, carriers, req, extra_notices or [])
            t_match += (time.perf_counter() - tr0) - t_retr_i
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
        )
        resp = validate_response(
            resp,
            self.store,
            self.settings.messages_dir,
            hadeethenc_link=self.settings.hadeethenc_mode == "link",
        )
        resp.timings_ms.total = _ms(t_start)
        return resp

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

    def _gather_evidence(self, q: _Quote) -> tuple[list[Evidence], dict[int, ExactHit | WindowHit], float]:
        """Exact on the full index first; fuzzy only when there is no exact hit at all."""
        loose = [t.loose for t in q.tokens]
        strict = [t.strict for t in q.tokens]
        carriers: dict[int, ExactHit | WindowHit] = {}
        evidence: list[Evidence] = []
        if q.language != "ar" or not loose:
            return evidence, carriers, 0.0
        hits = dedupe_hits(find_exact(self.store, loose, strict))
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
                return evidence, carriers, 0.0
        tr0 = time.perf_counter()
        self._fuzzy_evidence(loose, strict, evidence, carriers)
        self._order(evidence)
        return evidence, carriers, time.perf_counter() - tr0

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

    def _facts(self, q: _Quote, modality: str) -> QuoteFacts:
        cs = q.span.claimed_source or {}
        parsed = cs.get("parsed", {}) if isinstance(cs, dict) else {}
        books = tuple(parsed.get("books", ())) if isinstance(parsed, dict) else ()
        qref = None
        if isinstance(parsed, dict) and "surah" in parsed and "ayah" in parsed:
            qref = (int(parsed["surah"]), int(parsed["ayah"]))
        return QuoteFacts(
            n_tokens=len(q.tokens),
            language=q.language,
            kind=q.span.kind,
            marked=q.span.marked,
            claimed_books=books,
            claimed_quran_ref=qref,
            source_modality=modality,
        )

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
            else:
                ext = hadith_search_links(q.text, labels)
        claimed = None
        if q.span.claimed_source:
            claimed = ClaimedSource(
                raw=str(q.span.claimed_source.get("raw", "")),
                parsed=dict(q.span.claimed_source.get("parsed", {})),
            )
        return QuoteResult(
            id=f"q{i + 1}",
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
        q_strict = [t.strict for t in q.tokens]
        q_spans = [(t.start, t.end) for t in q.tokens]

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
        ops: list[DiffOp] = []
        kinds: list[str] = []
        if d.status != "found" or not ev.strict_ok:
            ops = word_diff(q_strict, q_spans, win_strict, win_spans, win_alt)
            kinds = diff_kinds(ops)
        rng = None
        mapped = [sp for sp in win_spans if sp[0] >= 0]
        if mapped:
            rng = [mapped[0][0], mapped[-1][1]]

        continues_to = None
        if rec.corpus == "tanzil" and carrier is not None and win_n > 0:
            covered = records_covering(self.store, carrier.gpos, win_n)
            if len(covered) > 1:
                continues_to = covered[-1].ref

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
            diff=[DiffOpModel(**o) for o in ops],
            diff_kinds=kinds,
            score=round(ev.score, 4),
            grade=grade,
            continues_to=continues_to,
        )

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
