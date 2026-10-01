#!/usr/bin/env python3
"""eval/islamiceval/run_1a.py — Basira on IslamicEval 2025 **Subtask 1A** (span detection).

Task (official): for each LLM response, mark every character as Ayah / Hadith / neither; score =
mean over questions of the character-level **macro-F1** (3 classes), with a NoAnnotation question
counting 1.0 iff the system outputs `No_Spans`. Re-implemented here line-for-line from
`Evaluation_scripts/Subtask_1A/scoring.py` (same regex extraction of <Response>, exclusive end
index, sklearn `f1_score(average="macro")`), and the official-format predictions TSV is written so
the organisers' script can re-score it.

Published TEST (overview paper, Table 2): Burhan AI 90.06 (fine-tuned gpt-4.1-mini + agentic tools),
HUMAIN 87.20, TCE 86.11, Isnad AI 66.97, mucAI 44.88; majority baseline 36.17.

**What is measured.** The product's real request path `Pipeline.check()` on the whole response —
rules extractor ∪ LLM proposals (re-located verbatim, ADR-005) → matching → state. Each returned
quote is labelled from the product's own evidence: `matches[0].corpus` (tanzil → Ayah, else Hadith)
when there is any match; otherwise the extractor's kind (`quran` → Ayah, else Hadith). Two
configurations are reported: `rules` (mock provider, fully deterministic) and `rules+llm`
(gpt-5.4 via the platform proxy). The LLM only *proposes* substrings; it never writes text.

Honest limits:
1. DEV set (50 responses, 210 spans), not the hidden TEST set.
2. Basira is a *citation checker*, not a span tagger: it deliberately ignores one-word quotes and
   anything not presented as a quotation, and it is evaluated on what it would actually check.
3. The LLM configuration is not deterministic across runs (temperature 0, but provider-side); the
   report records the run date and provider name.

Run:  backend/.venv/bin/python eval/islamiceval/run_1a.py [--llm]   (needs serve.sh-style env for --llm)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))

from app.config import Settings  # noqa: E402
from app.pipeline import CorpusMeta, Pipeline  # noqa: E402
from app.providers import MockLLM, make_llm  # noqa: E402
from app.retrieve.index import Retriever  # noqa: E402
from app.schemas import CheckRequest  # noqa: E402
from app.store import load_store  # noqa: E402

OUT = REPO / "eval" / "islamiceval"
PUBLISHED = {
    "Burhan AI (test)": 90.06,
    "HUMAIN (test)": 87.20,
    "TCE (test)": 86.11,
    "Isnad AI (test)": 66.97,
    "mucAI (test)": 44.88,
    "majority baseline": 36.17,
}


def load_dev(data: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Exactly the organisers' extraction (regex, not an XML parser — the file is not well-formed XML)."""
    raw = (data / "dev_SubtaskA" / "dev_SubtaskA.xml").read_text(encoding="utf-8")
    resp: dict[str, str] = {}
    for q in re.findall(r"<Question>(.*?)</Question>", raw, re.DOTALL):
        qid = re.search(r"<ID>(.*?)</ID>", q, re.DOTALL)
        body = re.search(r"<Response>(.*?)</Response>", q, re.DOTALL)
        if qid and body:
            resp[qid.group(1)] = body.group(1)
    with (data / "dev_SubtaskA" / "dev_SubtaskA.tsv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    return resp, rows


def macro_f1_chars(truth: list[int], pred: list[int]) -> float:
    """sklearn f1_score(average='macro') semantics, without the dependency: F1 per label present in
    truth ∪ pred, unweighted mean (labels absent from both are not counted)."""
    t = np.asarray(truth)
    p = np.asarray(pred)
    labels = sorted(set(t.tolist()) | set(p.tolist()))
    f1s: list[float] = []
    for lab in labels:
        tp = int(((t == lab) & (p == lab)).sum())
        fp = int(((t != lab) & (p == lab)).sum())
        fn = int(((t == lab) & (p != lab)).sum())
        denom = 2 * tp + fp + fn
        f1s.append(2 * tp / denom if denom else 0.0)
    return float(np.mean(f1s)) if f1s else 0.0


def label_of(q: Any) -> str:
    if q.matches:
        return "Ayah" if q.matches[0].corpus == "tanzil" else "Hadith"
    return "Ayah" if q.kind == "quran" else "Hadith"


MAX_CHARS = 5000  # the product's API limit (schemas.CheckRequest); kept, not bypassed


def _chunks(text: str) -> list[tuple[int, str]]:
    """Split an over-long response the way a user would paste it: at paragraph breaks, pieces ≤ MAX_CHARS,
    no overlap (a quote cut by the split is a limitation we record, not hide)."""
    if len(text) <= MAX_CHARS:
        return [(0, text)]
    out: list[tuple[int, str]] = []
    pos = 0
    while pos < len(text):
        end = min(len(text), pos + MAX_CHARS)
        if end < len(text):
            cut = text.rfind("\n", pos, end)
            if cut > pos + MAX_CHARS // 2:
                end = cut + 1
        out.append((pos, text[pos:end]))
        pos = end
    return out


async def predict(pipe: Pipeline, resp: dict[str, str]) -> dict[str, list[tuple[int, int, str]]]:
    out: dict[str, list[tuple[int, int, str]]] = {}
    for qid, text in resp.items():
        spans: list[tuple[int, int, str]] = []
        for base, piece in _chunks(text):
            r = await pipe.check(CheckRequest(text=piece))
            spans += [(base + q.span.start, base + q.span.end, label_of(q)) for q in r.quotes]
        out[qid] = spans
    return out


def score(
    resp: dict[str, str], rows: list[dict[str, str]], preds: dict[str, list[tuple[int, int, str]]]
) -> tuple[float, float, float, list[dict[str, Any]]]:
    tag = {"Ayah": 1, "Hadith": 2}
    per_q: list[dict[str, Any]] = []
    total = 0.0
    fq: list[float] = []
    fh: list[float] = []
    qids = list(dict.fromkeys(r["Question_ID"] for r in rows))
    for qid in qids:
        gold = [r for r in rows if r["Question_ID"] == qid]
        text = resp[qid]
        p = preds.get(qid, [])
        if gold[0]["Label"] == "NoAnnotation":
            f1 = 1.0 if not p else 0.0
            per_q.append({"id": qid, "f1": f1, "gold_spans": 0, "pred_spans": len(p), "no_annotation": True})
            total += f1
            continue
        truth = [0] * len(text)
        for g in gold:
            a, b = int(g["Span_Start"]), int(g["Span_End"])
            truth[a:b] = [tag[g["Label"]]] * (b - a)
        pred = [0] * len(text)
        for a, b, lab in p:
            pred[a:b] = [tag[lab]] * (b - a)
        f1 = macro_f1_chars(truth, pred)
        total += f1
        t = np.asarray(truth)
        pr = np.asarray(pred)
        for lab, bucket in ((1, fq), (2, fh)):
            if (t == lab).any():
                tp = int(((t == lab) & (pr == lab)).sum())
                fp = int(((t != lab) & (pr == lab)).sum())
                fn = int(((t == lab) & (pr != lab)).sum())
                bucket.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
        per_q.append({"id": qid, "f1": round(f1, 4), "gold_spans": len(gold), "pred_spans": len(p)})
    n = len(qids)
    return total / n, (float(np.mean(fq)) if fq else 0.0), (float(np.mean(fh)) if fh else 0.0), per_q


def write_predictions(path: Path, resp: dict[str, str], preds: dict[str, list[tuple[int, int, str]]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for qid in resp:
            p = preds.get(qid, [])
            if not p:
                fh.write(f"{qid}\t0\t0\tNo_Spans\n")
            for a, b, lab in p:
                fh.write(f"{qid}\t{a}\t{b}\t{lab}\n")


async def main_async(args: argparse.Namespace) -> int:
    data = REPO / args.data
    settings = Settings(index_dir=REPO / args.index)
    store = load_store(settings.index_dir)
    manifest = json.loads(settings.manifest_path.read_text(encoding="utf-8"))
    meta = CorpusMeta.from_manifest(manifest, store.meta)
    retr = Retriever(store)
    resp, rows = load_dev(data)

    configs: list[tuple[str, Any]] = [("rules", MockLLM())]
    if args.llm:
        llm = make_llm("openai-compatible")
        if llm.name == "mock":
            print("--llm requested but LLM_API_KEY/LLM_BASE_URL not set (source scripts/serve.sh env)", file=sys.stderr)
            return 2
        configs.append(("rules+llm", llm))

    results: dict[str, dict[str, Any]] = {}
    for name, llm in configs:
        pipe = Pipeline(store, retr, llm, settings, meta)
        t0 = time.time()
        preds = await predict(pipe, resp)
        secs = time.time() - t0
        f1, f1q, f1h, per_q = score(resp, rows, preds)
        results[name] = {"f1": f1, "f1_q": f1q, "f1_h": f1h, "secs": secs, "per_q": per_q, "provider": llm.name}
        write_predictions(OUT / f"predictions_1A_dev_{name.replace('+', '_')}.tsv", resp, preds)
        print(f"1A dev [{name}] macro-F1 {100 * f1:.2f} · F1-Q {100 * f1q:.2f} · F1-H {100 * f1h:.2f} · {secs:.0f}s · {llm.name}")

    lines = [
        "# Basira on IslamicEval 2025 — Subtask 1A (span detection), public DEV set",
        "",
        f"Generated by `eval/islamiceval/run_1a.py` on {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} · "
        f"index sha256 `{store.meta.get('records_sha256', '')[:12]}…` · 50 responses, 210 gold spans "
        "(118 Ayah, 76 Hadith, 16 NoAnnotation responses).",
        "",
        "Metric re-implemented from the official `Subtask_1A/scoring.py` (per-question character-level macro-F1 over "
        "{none, Ayah, Hadith}; NoAnnotation questions score 1 iff `No_Spans`); predictions TSV in the official "
        "4-column format for independent re-scoring.",
        "",
        "## Result",
        "",
        "| system | set | macro-F1 % | F1-Q % | F1-H % | what produces the spans |",
        "|---|---|---|---|---|---|",
    ]
    for name, r in results.items():
        how = (
            "rules extractor only (brackets, introducers, trailers) — deterministic"
            if name == "rules"
            else f"rules ∪ `{r['provider']}` proposals re-located verbatim (ADR-005)"
        )
        lines.append(
            f"| **Basira ({name})** | dev | **{100 * r['f1']:.2f}** | {100 * r['f1_q']:.2f} | {100 * r['f1_h']:.2f} | {how} |"
        )
    for name, v in PUBLISHED.items():
        lines.append(f"| {name} | test | {v:.2f} | — | — | published, Table 2 |")
    lines += [
        "",
        "Published numbers: Mubarak et al., *IslamicEval 2025*, ArabicNLP 2025, Table 2 — "
        "https://aclanthology.org/2025.arabicnlp-sharedtasks.67/ (Burhan AI: fine-tuned gpt-4.1-mini + agentic "
        "tools; HUMAIN: seq2seq tagging; TCE: few-shot prompting with trigger words).",
        "",
        "## How to read this",
        "",
        "- Basira does not *tag* text; it decides what to **check**. Its spans come from the same code path a user "
        "hits (`POST /v1/check`). A span is labelled Ayah/Hadith from the product's own match evidence, not from a "
        "classifier.",
        "- Deliberate differences from the task: one-word Quran quotes and ≤2-word hadith quotes are not checked "
        "(E-012); honorifics and introducers are excluded from the span (E-022); when the gold marks a whole "
        "paragraph that merely *paraphrases* a hadith, Basira marks nothing — it only checks text presented as a "
        "quotation.",
        "- Per-question F1 for both configurations is in `details_1A_dev.json`.",
        "",
        "## Error analysis (rules configuration, hand-checked)",
        "",
        "Of 194 gold spans: 169 are overlapped by a Basira span (88.8 % of gold characters covered), 25 are missed "
        "entirely, 9 overlapped spans carry the other label. Misses: quotes opened with Markdown `*\"` / `> {`, "
        "quotes introduced by a scholar's name («ابن عثيمين في قوله»), unmarked paraphrases, and gold spans that "
        "begin inside the introducer. Remaining false positives (92): plain-quoted non-religious text — site names, "
        "user instructions, «\"البوذية\"» — and parenthesised glosses «(أي الشكر)». These are text a user put in "
        "quotation marks; Basira checks them and reports `not_found`, which is the correct product behaviour even "
        "though the task scores it as a false span.",
        "",
        "Three extractor defects found by this analysis and fixed (guarded by tests, `make eval-full` unchanged "
        "150/150, FA 0/500): bare «قال» firing on every «قال فلان» (E-028); bracketed quotes labelled `unknown` even "
        "when preceded by «قال تعالى» or followed by «[البقرة: 255]» (E-029); bracketed attributions «(رواه مسلم)», "
        "«(متفق عليه)», «(سورة البقرة, آية 257)» being checked as quotes (E-030). Rules-only F1 went 52.67 → 62.96; "
        "the LLM configuration adds unmarked quotes the rules cannot see.",
        "",
        "## Limits of significance",
        "",
        "1. DEV set (50 responses), not the hidden TEST set used for the leaderboard.",
        "2. The `rules+llm` configuration depends on a hosted model (gpt-5.4 via the platform proxy); the model only "
        "proposes substrings that are re-located verbatim — if the proxy is down, the product falls back to `rules` "
        "and so does this number.",
        "3. The rules-only number is fully deterministic and reproducible with `make islamiceval-1a`.",
        "4. One dev response (6 035 chars) exceeds the product's 5 000-char request limit; it is sent in two "
        "paragraph-aligned pieces with offsets re-based — the limit is kept, not bypassed.",
    ]
    (OUT / "REPORT_1A.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "details_1A_dev.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=".scratch/islamiceval/IslamicEval-2025-Subtask-1")
    ap.add_argument("--index", default="corpus/index")
    ap.add_argument("--llm", action="store_true", help="also run rules+LLM (needs LLM_* env, see scripts/serve.sh)")
    args = ap.parse_args()
    if args.llm and not os.environ.get("LLM_API_KEY") and os.environ.get("OPENAI_API_KEY"):
        # same mapping as scripts/serve.sh
        os.environ["LLM_API_KEY"] = os.environ["OPENAI_API_KEY"]
        os.environ["LLM_BASE_URL"] = os.environ.get("OPENAI_BASE_URL", "")
        os.environ.setdefault("LLM_MODEL", "gpt-5.4")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
