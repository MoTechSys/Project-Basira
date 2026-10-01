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
from typing import Any, Literal

from app.config import Settings
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
from app.links import hadeethenc_url, hadith_search_links, ohd_url, quran_search_links, quran_url
from app.match.diff import DiffOp, diff_kinds, word_diff
from app.match.exact import ExactHit, dedupe_hits, find_exact, records_covering
from app.match.harakat import compare_quote, extend_marks
from app.match.splice import find_splice
from app.match.window import WindowHit, fuzzy_search
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
    HarakatConflict,
    Link,
    Match,
    QuoteResult,
    Span,
    SplicePart,
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
        stage = req.options.stage
        spans, degraded = await self._extract(text, stage)
        provider_name = "rules" if stage == "rules" else self.llm.name
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
        seen_loose: dict[tuple[str, ...], int] = {}  # N-1: identical quote repeated in the same text
        for i, sp in enumerate(spans):
            q = self._prepare(text, sp)
            if q is None:
                continue
            key = tuple(t.loose for t in q.tokens)
            if key in seen_loose:
                prev = quotes[seen_loose[key]]
                prev.repeated_spans.append(Span(start=sp.start, end=sp.end))
                if "repeated_in_text" not in prev.notice_keys:
                    prev.notice_keys.append("repeated_in_text")
                continue
            tr0 = time.perf_counter()
            evidence, carriers, t_retr_i, rasm0_only = self._gather_evidence(q)
            t_retr += t_retr_i
            facts = self._facts(q, req.source_modality, text, evidence)
            d = decide(facts, evidence, self.th)
            self._quran_context_notices(d, q, carriers, rasm0_only)
            splice = self._splice(q, d)
            qr = self._render(i, q, d, carriers, req, extra_notices or [])
            if splice:
                qr.splice_parts = splice
                qr.notice_keys = _dedupe([*qr.notice_keys, "spliced_quote"])
            t_match += (time.perf_counter() - tr0) - t_retr_i
            seen_loose[key] = len(quotes)
            quotes.append(qr)
        timings.retrieve = int(t_retr * 1000)
        timings.match = int(t_match * 1000)

        resp = CheckResponse(
            request_id=str(uuid.uuid4()),
            corpus=self.meta.versions(),
            extraction_degraded=degraded,
            extraction_provider=provider_name,
            extraction_stage=stage,
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
        resp.determinism_hash = self._determinism_hash(text, resp)
        resp.timings_ms.total = _ms(t_start)
        return resp

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

    async def _extract(self, text: str, stage: str) -> tuple[list[RuleSpan], bool]:
        """1. Rule spans always; the LLM provider may ADD spans (stage="full") and never blocks the answer.

        stage="rules" skips the provider entirely: a deterministic preliminary pass in milliseconds
        (E-035). Returns (spans, extraction_degraded). Skipping on purpose is not a degradation.
        """
        spans = extract_spans(text)
        degraded = False
        if stage == "full":
            try:
                res = await asyncio.wait_for(self.llm.extract(text), timeout=PROVIDER_TIMEOUT_S)
                degraded = res.degraded
                for p in res.quotes:
                    loc = relocate(text, p)
                    if loc is not None:
                        spans.append(RuleSpan(loc[0], loc[1], p.kind, False))
            except (ProviderError, TimeoutError):
                return spans, True
        spans = merge_overlaps(spans)
        for sp in spans:
            if sp.claimed_source is None:
                sp.claimed_source = find_claimed_source(text, sp.start, sp.end)
        return spans, degraded

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
        for channel, docs in (
            (self.retriever.quran, self.store.rdocs_quran),
            (self.retriever.hadith, self.store.rdocs_hadith),
        ):
            ranked = channel.search(self.store, loose, top_k=RETRIEVE_TOP_K)
            if not ranked:
                continue
            for w in fuzzy_search(self.store, docs, ranked, loose, max_docs=FUZZY_MAX_DOCS):
                if self.settings.ohd_mode == "off" and w.rec.corpus == "ohd":
                    continue
                if w.score >= 1.0:
                    # a loose-identical window that `find_exact` did not return cannot happen on the same
                    # token ids; guard anyway: treat as loose-exact with a strict check through the diff
                    evidence.append(Evidence(w.rec.corpus, w.rec.idx, 0.999, False, book=w.rec.book))
                else:
                    evidence.append(Evidence(w.rec.corpus, w.rec.idx, w.score, False, book=w.rec.book))
                carriers.setdefault(w.rec.idx, w)
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
        # I12 — first ayah of the best strict-exact Quran winner (evidence is already ordered)
        mref = None
        for e in evidence or ():
            if e.corpus == "tanzil" and e.is_exact and e.strict_ok:
                r = self.store.records[e.rec_idx]
                mref = (r.surah, r.ayah)
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

    def _splice(self, q: _Quote, d: Decision) -> list[SplicePart]:
        """E-038: a non-found quote that decomposes into ≥2 exact Quran runs from different ayat."""
        if d.status == "found" or q.language != "ar" or len(q.tokens) < 4:
            return []
        if q.span.kind not in ("quran", "unknown") and d.corpus_scope == "hadith":
            return []
        parts = find_splice(self.store, [t.loose for t in q.tokens], [t.strict for t in q.tokens])
        out: list[SplicePart] = []
        for p in parts:
            a = q.tokens[p.tok_start].start
            b = q.tokens[p.tok_end - 1].end
            la, le = self._ayah_labels(p.surah, p.ayah, p.ayah_to)
            out.append(
                SplicePart(
                    chars=[a, b],
                    surah=p.surah,
                    ayah=p.ayah,
                    ayah_to=p.ayah_to,
                    ref_label_ar=la,
                    ref_label_en=le,
                    strict_ok=p.strict_ok,
                )
            )
        return out

    def _ayah_labels(self, surah: int, ayah: int, ayah_to: int) -> tuple[str, str]:
        from app.extract.surahs import surah_name  # noqa: PLC0415

        rng_ar = f"{ayah}" if ayah_to == ayah else f"{ayah}–{ayah_to}"
        return (
            f"سورة {surah_name(surah, 'ar')}، الآية {rng_ar}",
            f"Surah {surah_name(surah, 'en')}, ayah {rng_ar}",
        )

    def _quran_context_notices(
        self, d: Decision, q: _Quote, carriers: dict[int, ExactHit | WindowHit], rasm0_only: set[int]
    ) -> None:
        """Descriptive Quran notices (never a judgment):

        * ``partial_ayah_context`` (G-4): the quote is a strict sub-span of a longer ayah — the full
          ayah is shown so the reader does not take a clipped fragment as the whole statement.
        * ``qiraah_note`` (G-3): the only strict difference is the dagger-alif (U+0670) family, which is
          how a canonical reading other than Ḥafṣ is usually written («مَلِكِ»/«مَٰلِكِ»).
        * ``basmala_note`` (N-3): the quote is the basmala and matched both 1:1 and 27:30.
        """
        if d.corpus_scope != "quran" or not d.winners:
            return
        best = d.winners[0]
        rec = self.store.records[best.rec_idx]
        c = carriers.get(best.rec_idx)
        n_q = len(q.tokens)
        n_rec = rec.g_len - rec.offset
        if d.status in ("found", "needs_review") and n_q < n_rec and n_q >= 2:
            crosses = isinstance(c, ExactHit) and c.tok_start >= 0 and c.tok_end > rec.g_len
            if not crosses and "partial_ayah_context" not in d.notice_keys:
                d.notice_keys.append("partial_ayah_context")
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
            if any(m.harakat_verdict == "conflict" for m in matches):
                notices.append("harakat_conflict")
            elif d.corpus_scope == "quran" and any(m.harakat_verdict == "consistent" for m in matches):
                notices.append("harakat_consistent")
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

    def _harakat(
        self,
        rec: Record,
        q: _Quote,
        tok_start: int,
        tok_end: int,
        carrier: ExactHit | WindowHit | None,
    ) -> tuple[Literal["none", "consistent", "conflict"], list[HarakatConflict], str, list[int] | None]:
        """E-037: per-letter vowel comparison against Tanzil Simple (vocalized). Quran exact hits only."""
        empty: tuple[Literal["none", "consistent", "conflict"], list[HarakatConflict], str, list[int] | None]
        empty = ("none", [], "", None)
        if rec.corpus != "tanzil" or not rec.text_vocalized or not isinstance(carrier, ExactHit):
            return empty
        # Which record tokens did the quote cover? variant 0 gives display offsets; variant 1 (simple
        # rasm) gives a global position inside the simple stream → convert to a token offset.
        if tok_start < 0:
            tok_start = carrier.gpos - rec.g2_start
            tok_end = tok_start + len(q.tokens)
        voc_tokens = tokenize(rec.text_vocalized)
        if tok_end > len(voc_tokens) or tok_start < 0:
            return empty  # cross-ayah window: compare only what lies inside this record
        s_spans = [(t.start, t.end) for t in voc_tokens[tok_start:tok_end]]
        q_spans = [(t.start, t.end) for t in q.tokens][: len(s_spans)]
        if len(q_spans) != len(s_spans):
            return empty
        verdict, conflicts, _n = compare_quote(q.text, q_spans, rec.text_vocalized, s_spans)
        out = [
            HarakatConflict(
                quote_chars=list(c.quote_chars),
                reference_chars=list(c.source_chars),
                quote_marks=list(c.quote_marks),
                reference_marks=list(c.source_marks),
            )
            for c in conflicts
        ]
        ref_range = [s_spans[0][0], extend_marks(rec.text_vocalized, s_spans[-1][1])] if s_spans else None
        return (
            verdict,
            out,
            rec.text_vocalized if verdict == "conflict" else "",
            ref_range if verdict == "conflict" else None,
        )

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
        q_strict = [t.strict for t in q.tokens]
        q_spans = [(t.start, t.end) for t in q.tokens]

        # the window to diff against: matched tokens when known, else the whole record (minus basmala)
        if tok_start >= 0:
            win_strict = src_strict[tok_start:tok_end]
            win_spans = src_spans[tok_start:tok_end]
        else:
            win_strict = src_strict[rec.offset :]
            win_spans = src_spans[rec.offset :]
        ops: list[DiffOp] = []
        kinds: list[str] = []
        if d.status != "found" or not ev.strict_ok:
            ops = word_diff(q_strict, q_spans, win_strict, win_spans)
            kinds = diff_kinds(ops)
        rng = None
        if win_spans and win_spans[0][0] >= 0:
            rng = [win_spans[0][0], win_spans[-1][1]]
        harakat = self._harakat(rec, q, tok_start, tok_end, carrier)

        continues_to = None
        if rec.corpus == "tanzil" and isinstance(carrier, ExactHit):
            covered = records_covering(self.store, carrier.gpos, len(q.tokens))
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
            harakat_verdict=harakat[0],
            harakat_conflicts=harakat[1],
            harakat_reference=harakat[2],
            harakat_reference_range=harakat[3],
            source_url=links[0].url if links else "",
            links=links,
            diff=[DiffOpModel(**o) for o in ops],
            diff_kinds=kinds,
            score=round(ev.score, 4),
            grade=grade,
            continues_to=continues_to,
        )

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
