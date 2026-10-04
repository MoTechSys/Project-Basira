/** The user's own text with every detected quote highlighted IN PLACE (Grammarly-style).
 *
 *  Invariants:
 *  - textContent of the rendered block === the user's input, character for character. We only wrap
 *    ranges in <button>/<mark>; nothing is re-ordered, trimmed, normalised or corrected.
 *  - Ranges come from the backend (`span`, `segments`, `repeated_spans`); overlapping ranges are
 *    resolved deterministically (first quote wins) so the DOM is a flat sequence of runs.
 *  - Each quote is a real <button> (keyboard reachable, aria-pressed for the selected one) so the
 *    highlight is the primary navigation, not decoration.
 */

import { useMemo } from "react";
import type { Lang, QuoteResult, Status } from "../api";
import { msg } from "../i18n";

type Run =
  | { kind: "text"; text: string; key: string }
  | { kind: "quote"; text: string; key: string; q: QuoteResult; status: Status; repeat: boolean; seg: Seg };

/** "text" = the quoted passage itself (ayah or matn); isnad / claimed_source are its satellites. */
type Seg = "text" | "isnad" | "claimed_source" | null;

interface Mark {
  start: number;
  end: number;
  q: QuoteResult;
  repeat: boolean;
  seg: Seg;
}

export function buildRuns(text: string, quotes: QuoteResult[]): Run[] {
  const marks: Mark[] = [];
  for (const q of quotes) {
    const segs = q.segments ?? [];
    const extras = segs.filter((s) => s.type === "isnad" || s.type === "claimed_source");
    if (extras.length) {
      // matn + its isnad / claimed_source as separate, visually distinct runs
      marks.push({ start: q.span.start, end: q.span.end, q, repeat: false, seg: "text" });
      for (const s of extras) marks.push({ start: s.start, end: s.end, q, repeat: false, seg: s.type as "isnad" | "claimed_source" });
    } else {
      marks.push({ start: q.span.start, end: q.span.end, q, repeat: false, seg: null });
    }
    for (const r of q.repeated_spans ?? []) marks.push({ start: r.start, end: r.end, q, repeat: true, seg: null });
  }
  marks.sort((a, b) => a.start - b.start || b.end - a.end);
  const runs: Run[] = [];
  let i = 0;
  let n = 0;
  for (const m of marks) {
    const a = Math.max(i, m.start);
    const b = Math.min(text.length, m.end);
    if (b <= a) continue; // fully overlapped by an earlier mark
    if (a > i) runs.push({ kind: "text", text: text.slice(i, a), key: `t${n++}` });
    runs.push({ kind: "quote", text: text.slice(a, b), key: `q${n++}`, q: m.q, status: m.q.status, repeat: m.repeat, seg: m.seg });
    i = b;
  }
  if (i < text.length) runs.push({ kind: "text", text: text.slice(i), key: `t${n++}` });
  return runs;
}

export function AnnotatedText({
  text,
  quotes,
  selected,
  onSelect,
  lang,
}: {
  text: string;
  quotes: QuoteResult[];
  selected: string | null;
  onSelect: (id: string) => void;
  lang: Lang;
}) {
  const runs = useMemo(() => buildRuns(text, quotes), [text, quotes]);
  return (
    <div className="annotated" dir="auto" lang="ar" data-testid="annotated-text">
      {runs.map((r) =>
        r.kind === "text" ? (
          <span key={r.key}>{r.text}</span>
        ) : (
          <button
            key={r.key}
            type="button"
            className="hl"
            data-status={r.status}
            data-seg={r.seg ?? undefined}
            data-repeat={r.repeat || undefined}
            aria-pressed={selected === r.q.id}
            aria-label={`${msg(lang, "labels", r.status)}: ${r.text}`}
            onClick={() => onSelect(r.q.id)}
          >
            {r.text}
          </button>
        ),
      )}
    </div>
  );
}
