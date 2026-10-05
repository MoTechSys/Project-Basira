#!/usr/bin/env python3
"""eval/islamiceval/run_1b.py — Basira on IslamicEval 2025 **Subtask 1B** (validation of quoted Ayah/Hadith).

External, publicly verifiable benchmark promised in the registration (slide 10). Everything here is
checked against the official repository and overview paper:

* Data: https://github.com/qcri/IslamicEval-2025-Subtask-1 (Apache-2.0), `dev_SubtaskB/` — 50 LLM
  responses, 247 expert-annotated spans (110 CorrectAyah, 70 WrongAyah, 37 CorrectHadith, 30 WrongHadith).
  Gold spans are given as character offsets into the response; Basira does NOT re-detect them here
  (that is Subtask 1A) — it only *validates* each gold span, exactly as 1B is defined.
* Metric: accuracy over {Correct, Incorrect} — identical to `Evaluation_scripts/Subtask_1B/scoring.py`
  (sklearn accuracy_score). We also report Acc-Q / Acc-H as Table 2 of the overview paper does.
* Published reference points (overview paper, Table 2, TEST set): TCE 89.82 % (best), Burhan AI 88.60 %,
  HUMAIN 86.14 %; majority baseline 70.00 %. Mubarak et al., ArabicNLP 2025, pp. 480–493,
  https://aclanthology.org/2025.arabicnlp-sharedtasks.67/
* Annotation guideline (Appendix C of the paper) that the mapping below follows:
  C1 «Any incomplete Qur'anic verse or incomplete Hadith is considered an error»;
  C2 «Incorrect diacritization is marked as an error, whereas partially correct diacritization or the
  absence of diacritics is not»; C3 «A single error … suffices to label the span as erroneous».

**What is measured.** Each gold span is pushed through the SAME stages the product uses
(`Pipeline._prepare` → `_gather_evidence` → `state.decide`), with the span's gold kind (Ayah / Hadith)
as the extractor's kind and `marked=True` (the task hands us the boundaries). No LLM is involved, so
the number is fully reproducible (`make islamiceval`).

**Mapping Basira → task label (documented, not tuned):**
* `found` whose winning corpus agrees with the claimed kind (Ayah → Quran, Hadith → hadith) → **Correct**.
* `found` in the *other* corpus (an ayah presented as a hadith, or vice-versa) → **Incorrect** — the
  gold treats a Qur'anic verse introduced as «وفي حديث النبي ﷺ» as a WrongHadith; Basira surfaces the
  same fact as the `quran_wins` notice, which the UI shows to the user.
* everything else (`partial_match`, `needs_review`, `not_found`) → **Incorrect**.
  `partial_match` (hadith wording variants) is deliberately NOT mapped to Correct: Basira's contract is
  that only a byte-faithful match confirms a quote; counting variants as Correct would inflate the
  score at the expense of the product's guarantee.

**Caveats stated up front (limits of significance):**
1. Our number is on the public DEV set (the hidden test set is not available); the published numbers
   are on TEST. Comparable in task definition, not the same examples.
2. Basira's corpus is Tanzil (identical Quran source to the task) + Open-Hadith-Data 9 books +
   HadeethEnc; the task's hadith reference is "the six books" from a different CSV. A hadith correct
   in OHD but absent from the task's reference (or vice-versa) is a legitimate disagreement, not a
   bug — the report lists every such case.
3. Completeness (C1) is where Basira and the gold disagree most: Basira confirms a verbatim
   *fragment* of an ayah or hadith (it is faithful text) and tells the user it is a fragment; the task
   labels an incomplete ayah as an error. Each such case is listed under "false confirmations" with
   the exact expert correction so a reader can judge.

Run:  backend/.venv/bin/python eval/islamiceval/run_1b.py [--data .scratch/islamiceval/IslamicEval-2025-Subtask-1]
Writes eval/islamiceval/REPORT_1B.md and predictions TSV in the official format.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))

from app.config import Settings  # noqa: E402
from app.extract.rules import RuleSpan  # noqa: E402
from app.pipeline import CorpusMeta, Pipeline  # noqa: E402
from app.providers import MockLLM  # noqa: E402
from app.retrieve.index import Retriever  # noqa: E402
from app.state import decide  # noqa: E402
from app.store import load_store  # noqa: E402
from eval.metrics import wilson  # noqa: E402

OUT = REPO / "eval" / "islamiceval"
PUBLISHED = {"TCE (best, test)": 89.82, "Burhan AI (test)": 88.60, "HUMAIN (test)": 86.14, "majority baseline": 70.00}
GOLD_URL = "https://github.com/qcri/IslamicEval-2025-Subtask-1"


def load_dev(data: Path) -> tuple[dict[str, str], list[dict[str, str]], dict[str, str]]:
    raw = (data / "dev_SubtaskB" / "dev_SubtaskB.xml").read_text(encoding="utf-8")
    root = ET.fromstring("<root>" + raw + "</root>")
    resp = {q.findtext("ID") or "": q.findtext("Response") or "" for q in root.findall("Question")}
    with (data / "dev_SubtaskB" / "dev_SubtaskB.tsv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    # expert corrections live in the combined dev file (different question IDs; join on span text)
    corrections: dict[str, str] = {}
    abc = data / "dev_SubtasksABC" / "dev.tsv"
    if abc.exists():
        with abc.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
                corrections[r["Original_Span"].strip()[:60]] = r.get("Correction", "")
    return resp, rows, corrections


def basira_status(pipe: Pipeline, text: str, kind: str) -> tuple[str, str | None, str, str, list[str]]:
    """Run the product's deterministic stages on one span.

    Returns (status, review_reason, winning_corpus, top_ref, notice_keys)."""
    sp = RuleSpan(0, len(text), kind, True)
    q = pipe._prepare(text, sp)  # the product's own stages, deliberately
    if q is None:
        return "not_found", "too_short", "none", "", []
    # Same stage order as Pipeline.check() — keep in sync with backend/app/pipeline.py.
    evidence, carriers, _, rasm0_only = pipe._gather_evidence(q)
    facts = pipe._facts(q, "text", text, evidence)
    d = decide(facts, evidence, pipe.th)
    d = pipe._foreign_gate(q, d)
    d = pipe._harakat_gate(q, d, carriers)  # I11
    pipe._claimed_ref_notice(d, facts)
    pipe._quran_context_notices(d, q, carriers, rasm0_only)
    notices = list(d.notice_keys)
    top = ""
    if d.winners:
        w = d.winners[0]
        rec = pipe.store.records[w.rec_idx]
        top = str(rec.ref) + ("" if w.is_exact else f" sim={w.score:.3f}")
        c = carriers.get(w.rec_idx)
        if c is not None and rec.corpus == "tanzil":
            from app.match.exact import records_covering  # noqa: PLC0415

            n = len(q.tokens) if w.is_exact else getattr(c, "win_len", len(q.tokens))
            covered = records_covering(pipe.store, c.gpos, n)
            if len(covered) > 1:
                top += f" → {covered[-1].ref}"
    return d.status, d.review_reason, d.corpus_scope, top, notices


def map_label(status: str, scope: str, gold_kind: str) -> str:
    if status != "found":
        return "Incorrect"
    wants = "quran" if gold_kind == "quran" else "hadith"
    return "Correct" if scope == wants else "Incorrect"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=".scratch/islamiceval/IslamicEval-2025-Subtask-1")
    ap.add_argument("--index", default="corpus/index")
    args = ap.parse_args()
    data = REPO / args.data
    settings = Settings(index_dir=REPO / args.index)
    store = load_store(settings.index_dir)
    manifest = json.loads(settings.manifest_path.read_text(encoding="utf-8"))
    pipe = Pipeline(store, Retriever(store), MockLLM(), settings, CorpusMeta.from_manifest(manifest, store.meta))
    resp, rows, corrections = load_dev(data)

    t0 = time.time()
    preds: list[tuple[str, str]] = []
    details: list[dict[str, Any]] = []
    for r in rows:
        text = resp[r["Question_ID"]][int(r["Span_Start"]) : int(r["Span_End"])]
        gold_kind = "quran" if r["Label"].endswith("Ayah") else "hadith_matn"
        gold = "Correct" if r["Label"].startswith("Correct") else "Incorrect"
        status, reason, scope, top, notices = basira_status(pipe, text, gold_kind)
        pred = map_label(status, scope, gold_kind)
        sid = f"{r['Question_ID']}_{r['Annotation_ID']}"
        preds.append((sid, pred))
        details.append(
            {
                "id": sid,
                "gold_label": r["Label"],
                "gold": gold,
                "pred": pred,
                "basira_status": status,
                "reason": reason,
                "scope": scope,
                "notices": notices,
                "top": top,
                "n_tokens": len(text.split()),
                "text": text[:90],
                "expert_correction": corrections.get(r["Original_Span"].strip()[:60], "")[:160],
            }
        )
    secs = time.time() - t0

    def acc(sel: list[dict[str, Any]]) -> tuple[int, int]:
        return sum(d["gold"] == d["pred"] for d in sel), len(sel)

    k, n = acc(details)
    kq, nq = acc([d for d in details if str(d["gold_label"]).endswith("Ayah")])
    kh, nh = acc([d for d in details if str(d["gold_label"]).endswith("Hadith")])
    lo, hi = wilson(k, n)
    conf = Counter((d["gold"], d["pred"]) for d in details)
    fp = [d for d in details if d["gold"] == "Incorrect" and d["pred"] == "Correct"]  # the dangerous direction
    fn = [d for d in details if d["gold"] == "Correct" and d["pred"] == "Incorrect"]
    fn_status = Counter(str(d["basira_status"]) + (f"/{d['reason']}" if d["reason"] else "") for d in fn)
    # Wrong spans Basira caught AND for which it also points at the intended source (useful to a user)
    caught_with_pointer = sum(
        1 for d in details if d["gold"] == "Incorrect" and d["pred"] == "Incorrect" and d["top"]
    )
    n_wrong = sum(1 for d in details if d["gold"] == "Incorrect")

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "predictions_1B_dev.tsv").open("w", encoding="utf-8") as fh:
        for sid, p in preds:
            fh.write(f"{sid}\t{p}\n")
    (OUT / "details_1B_dev.json").write_text(json.dumps(details, ensure_ascii=False, indent=1), encoding="utf-8")

    def row(d: dict[str, Any]) -> str:
        corr = f" · expert correction: «{d['expert_correction']}…»" if d["expert_correction"] else ""
        notes = f" · notices {d['notices']}" if d["notices"] else ""
        return (
            f"- `{d['id']}` {d['gold_label']} · Basira `{d['basira_status']}`"
            f"{'/' + str(d['reason']) if d['reason'] else ''}{notes} · top {d['top']} · «{d['text']}…»{corr}"
        )

    lines = [
        "# Basira on IslamicEval 2025 — Subtask 1B (validation), public DEV set",
        "",
        f"Generated by `eval/islamiceval/run_1b.py` on {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} · "
        f"index sha256 `{store.meta.get('records_sha256', '')[:12]}…` · {secs:.1f} s for {n} spans "
        "(deterministic core only — the product's own stages, no LLM).",
        "",
        "## Result",
        "",
        "| system | set | Acc % | Acc-Q % | Acc-H % | n |",
        "|---|---|---|---|---|---|",
        f"| **Basira (deterministic core)** | dev | **{100 * k / n:.2f}** (95 % CI {100 * lo:.1f}–{100 * hi:.1f}) "
        f"| {100 * kq / nq:.2f} | {100 * kh / nh:.2f} | {n} ({nq} Ayah / {nh} Hadith) |",
    ]
    for name, v in PUBLISHED.items():
        lines.append(f"| {name} | test | {v:.2f} | — | — | published, Table 2 |")
    lines += [
        "",
        "Published numbers: Mubarak et al., *IslamicEval 2025*, ArabicNLP 2025, Table 2 — "
        "https://aclanthology.org/2025.arabicnlp-sharedtasks.67/ . Metric identical to the official "
        f"`Subtask_1B/scoring.py` (accuracy over Correct/Incorrect). Data: {GOLD_URL} (Apache-2.0).",
        "",
        "## Confusion (gold → pred)",
        "",
        "| gold \\ pred | Correct | Incorrect |",
        "|---|---|---|",
        f"| Correct | {conf[('Correct', 'Correct')]} | {conf[('Correct', 'Incorrect')]} |",
        f"| Incorrect | {conf[('Incorrect', 'Correct')]} | {conf[('Incorrect', 'Incorrect')]} |",
        "",
        f"**Dangerous direction** (gold Incorrect, Basira said Correct): **{len(fp)}** of {n_wrong} wrong spans. "
        "This is the number that matters for a citation checker; every case is listed below with the expert's "
        "correction so the reader can judge.",
        "",
        f"Of the {n_wrong} wrong spans, Basira flagged {n_wrong - len(fp)} and for {caught_with_pointer} of them it "
        "also shows the closest Mushaf/hadith text with the differing words highlighted (the task's Subtask 1C "
        "'correction' — Basira never writes the correction itself; it points to the verbatim source).",
        "",
        f"Missed-Correct ({len(fn)}) by Basira status: " + ", ".join(f"`{s}`: {c}" for s, c in fn_status.most_common()),
        "",
        "## False confirmations (gold Incorrect → Basira Correct)",
        "",
    ]
    lines += [row(d) for d in fp] or ["none"]
    lines += ["", "## Missed confirmations (gold Correct → Basira Incorrect)", ""]
    lines += [row(d) for d in fn] or ["none"]
    lines += [
        "",
        "## Case analysis",
        "",
        "Counts in this section are computed from the run above; the named examples were checked by hand against "
        "the task's own reference files.",
        "",
        f"**False confirmations ({len(fp)}).** Byte-faithful text that the expert nevertheless labelled wrong:",
        "- `B-Q28_9` (11:41–43): a complete run of consecutive ayat, verbatim, with «،» between ayat instead of "
        "verse numbers. Diffing the span against the expert's own correction (after removing the «(41)» markers) "
        "gives zero token differences in both tiers. We believe the gold is in error here, and say so.",
        "- `B-Q32_6`: verbatim fragment of Bukhari 52 (OHD 50) beginning mid-sentence («صلحت صلح الجسد…»); the "
        "correction only prepends «إذا». Guideline C1 counts an incomplete text as an error; Basira confirms it.",
        "",
        f"**Missed confirmations ({len(fn)}).** Why Basira did not say Correct:",
        f"- *Vocalisation* (`diacritic_unverified` ×{fn_status['needs_review/diacritic_unverified']}, "
        f"`diacritic_difference` ×{fn_status['needs_review/diacritic_difference']}): the span is vocalised and "
        "its marks either contradict the Mushaf on a letter or cannot be aligned letter by letter. By policy D-013 "
        "a written mark is part of the quotation, so Basira asks for review instead of confirming; the gold "
        "ignores marks. This is the cost of the harakat gate (B01) and the main reason this number fell from the "
        "pre-gate run.",
        f"- *Hadith wording variants* (`partial_match` ×{fn_status['partial_match']}): a well-known riwaya whose "
        "exact wording is not in our nine books / HadeethEnc (e.g. «من صلى عليّ واحدة» vs Muslim 577 «من صلى عليّ "
        "صلاة»). Basira shows the closest text with the differing words highlighted and never confirms a variant.",
        f"- *Near-misses* (`near_miss` ×{fn_status['needs_review/near_miss']}): single-word deviations the gold "
        "tolerated — «وسلام» for «والسلام» (19:33), «والذين» for «ومن» (26:119), «جاؤوا» for «جاءوا» (24:11, a "
        "hamza-seat spelling), «ياأيها» joined (12:88). By ADR-003 a letter difference in the Mushaf text is "
        "`needs_review`, not `found`.",
        "- *Too short* (`B-Q33_5/7`, one word «وإنهما»): the product does not evaluate one-word Quran quotes (E-012).",
        "- `B-Q35_2`: gold says CorrectAyah for «خيركم خيركم لأهله…», which is a hadith (Tirmidhi); Basira finds "
        "it as a hadith → mapped Incorrect because the claimed kind disagrees. Gold label error.",
        "- `B-Q47_4`: long Bukhari narration (3612) with several wording differences from OHD's text; fuzzy score "
        "below the review threshold → `not_found`.",
        "",
        "## Mapping and limits of significance",
        "",
        "1. DEV set (public), not the hidden TEST set used for the published leaderboard; same task definition, "
        "different examples.",
        "2. Mapping: `found` in the corpus matching the claimed kind → Correct; `found` in the other corpus "
        "(ayah presented as hadith) → Incorrect; `partial_match` / `needs_review` / `not_found` → Incorrect. "
        "Hadith wording variants are *not* counted as Correct even where the gold accepts them — Basira only "
        "confirms byte-faithful text.",
        "3. Hadith reference differs: task = six books CSV; Basira = Open-Hadith-Data nine books + HadeethEnc. "
        "Disagreements on hadith can be reference coverage, not matching quality.",
        "4. Completeness: the guideline treats an incomplete ayah as an error; Basira confirms a verbatim fragment "
        "and labels it as a fragment.",
        "5. No LLM involved — fully reproducible with `make islamiceval` once the data is cloned into "
        "`.scratch/islamiceval/`. The runner calls the same stages, in the same order, as `Pipeline.check()`.",
    ]
    (OUT / "REPORT_1B.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"1B dev: acc {100 * k / n:.2f}% ({k}/{n}) · Q {100 * kq / nq:.2f}% · H {100 * kh / nh:.2f}% · "
        f"false-confirm {len(fp)} · missed {len(fn)} · {secs:.1f}s"
    )
    print("missed by status:", dict(fn_status))
    return 0


if __name__ == "__main__":
    sys.exit(main())
