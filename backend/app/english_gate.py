"""English gate — a non-Arabic quote is routed back to its Arabic original (docs/ENGLISH_GATE.md §6.2–6.3).

Flow for a quote whose ``language != "ar"`` (invariant I7 keeps it ``needs_review/non_arabic``):

1. ``TranslationIndex.candidates`` (deterministic BM25 over QuranEnc / HadeethEnc English) → ≤ k candidates.
2. Each candidate is **cross-referenced to the Arabic record** in the Store (``tanzil s:a`` /
   ``hadeethenc id``); a candidate whose record is absent is dropped — nothing is shown that is not
   byte-exact corpus text.
3. A **picker** marks at most one candidate ``selected``:
   * ``rule`` — top-1 score ≥ ``RULE_MIN_TOP1`` and gap to top-2 ≥ ``RULE_MIN_GAP`` (thresholds taken
     from the measured separation in ENGLISH_GATE.md §3–4: positives ≥ 0.497, negatives ≤ 0.465);
   * ``model`` — an optional ``EnglishPicker`` (LLM under the provider layer) chooses an index or
     refuses; its answer is **constrained** to the candidate list (it can never introduce text);
   * ``none`` — nothing selected: the UI shows the candidates as "closest approved translations".

The gate never changes the four-state verdict of the quote (I7 stays), never generates text, never
judges. ``translation_text`` and ``arabic_text`` are upstream strings byte-for-byte.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.links import hadeethenc_url, quran_url
from app.retrieve.translations import Candidate, TranslationIndex
from app.schemas import EnglishCandidate
from app.store import Record, Store

log = logging.getLogger(__name__)

RULE_MIN_TOP1 = 0.90  # «every query term present about once in an average document» (ENGLISH_GATE §3.3)
RULE_MIN_GAP = 0.30  # clear winner; below this the model (if any) or the user decides
DEFAULT_K = 5


class EnglishPicker(abc.ABC):
    """Optional model-backed chooser. Returns the index of the matching candidate or ``None`` (refuse)."""

    name: str = "abstract"

    @abc.abstractmethod
    async def pick(self, quote: str, candidates: list[EnglishCandidate]) -> int | None: ...


@dataclass(slots=True)
class EnglishGateResult:
    candidates: list[EnglishCandidate]
    picker: str  # rule | model | none


class EnglishGate:
    def __init__(
        self,
        store: Store,
        index: TranslationIndex | None,
        picker: EnglishPicker | None = None,
        *,
        hadeethenc_link_only: bool = True,
    ) -> None:
        self.store = store
        self.index = index
        self.picker = picker
        self.hadeethenc_link_only = hadeethenc_link_only  # owner Q2: HadeethEnc body is linked, not embedded

    @classmethod
    def from_path(
        cls,
        store: Store,
        path: Path,
        picker: EnglishPicker | None = None,
        *,
        hadeethenc_link_only: bool = True,
    ) -> EnglishGate:
        if not path.exists():
            log.info("english gate: %s absent — gate disabled (run corpus/fetch_translations.py)", path)
            return cls(store, None, picker, hadeethenc_link_only=hadeethenc_link_only)
        try:
            return cls(store, TranslationIndex.load(path), picker, hadeethenc_link_only=hadeethenc_link_only)
        except (OSError, ValueError) as exc:
            log.warning("english gate: cannot load %s (%s) — gate disabled", path, exc)
            return cls(store, None, picker, hadeethenc_link_only=hadeethenc_link_only)

    @property
    def enabled(self) -> bool:
        return self.index is not None

    # ------------------------------------------------------------------ public

    def candidates(self, text: str, k: int = DEFAULT_K) -> list[EnglishCandidate]:
        if self.index is None:
            return []
        out: list[EnglishCandidate] = []
        for c in self.index.candidates(text, k):
            rec = self._record_for(c)
            if rec is None:
                continue  # never show a translation we cannot anchor to byte-exact Arabic
            out.append(self._to_model(c, rec))
        return out

    async def run(
        self, text: str, k: int = DEFAULT_K, *, picker: EnglishPicker | None = None
    ) -> EnglishGateResult:
        """``picker`` overrides the gate's default picker for this call (BYOK, E-051)."""
        cands = self.candidates(text, k)
        if not cands:
            return EnglishGateResult([], "none")
        idx = self._rule_pick(cands)
        how = "rule" if idx is not None else "none"
        picker = picker or self.picker
        if idx is None and picker is not None:
            try:
                got = await picker.pick(text, cands)
            except Exception as exc:
                log.warning("english picker %s failed: %s", picker.name, exc.__class__.__name__)
                got = None
            if got is not None and 0 <= got < len(cands):
                idx, how = got, "model"
        if idx is not None:
            cands[idx] = cands[idx].model_copy(update={"selected": True})
        return EnglishGateResult(cands, how)

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _rule_pick(cands: list[EnglishCandidate]) -> int | None:
        top = cands[0].score
        second = cands[1].score if len(cands) > 1 else 0.0
        if top >= RULE_MIN_TOP1 and (top - second) >= RULE_MIN_GAP:
            return 0
        return None

    def _record_for(self, c: Candidate) -> Record | None:
        try:
            if c.kind == "quran":
                s, a = c.ref.split(":")
                return self.store.lookup("tanzil", surah=int(s), ayah=int(a))
            return self.store.lookup("hadeethenc", id=int(c.ref))
        except (KeyError, ValueError):
            return None

    def _to_model(self, c: Candidate, rec: Record) -> EnglishCandidate:
        ref: dict[str, Any] = rec.ref
        if rec.corpus == "tanzil":
            name_ar, name_en = self.store.surah_names.get(rec.surah, (str(rec.surah), str(rec.surah)))
            label_ar = f"سورة {name_ar} ({rec.surah}:{rec.ayah})"
            label_en = f"Surah {name_en} ({rec.surah}:{rec.ayah})"
            url = quran_url(rec.surah, rec.ayah)
            arabic = rec.display
        else:
            label_ar = f"الموسوعة الحديثية — رقم {rec.henc_id}"
            label_en = f"HadeethEnc — #{rec.henc_id}"
            url = hadeethenc_url(rec.link, rec.henc_id)
            arabic = "" if self.hadeethenc_link_only else rec.display
        return EnglishCandidate(
            kind="quran" if rec.corpus == "tanzil" else "hadith",
            ref=ref,
            ref_label_ar=label_ar,
            ref_label_en=label_en,
            arabic_text=arabic,
            translation_text=c.translation_text,
            translation_source=c.source_key,
            score=c.score,
            source_url=url,
        )
