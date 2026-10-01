/** Side-by-side highlight of the user's quote and the VERBATIM source text.
 *  The source string is rendered exactly as received (textContent === corpus field); only <mark> wrappers
 *  are added around character ranges supplied by the backend diff. Nothing is re-ordered or normalized. */

import type { DiffOp, Lang } from "../api";
import { Icon } from "../brand";
import { ui } from "../i18n";

type Range = [number, number];

function ranges(ops: DiffOp[], side: "quote" | "source"): Range[] {
  const out: Range[] = [];
  for (const o of ops) {
    if (o.op === "equal") continue;
    const r = side === "quote" ? o.quote_chars : o.source_chars;
    if (r[0] < 0 || r[1] <= r[0]) continue;
    out.push([r[0], r[1]]);
  }
  out.sort((a, b) => a[0] - b[0]);
  // merge overlaps
  const merged: Range[] = [];
  for (const r of out) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  return merged;
}

export function Highlighted({ text, marks, cls, offset = 0 }: { text: string; marks: Range[]; cls: string; offset?: number }) {
  const parts: React.ReactNode[] = [];
  let i = 0;
  for (const [a0, b0] of marks) {
    const a = Math.max(0, a0 - offset);
    const b = Math.min(text.length, b0 - offset);
    if (b <= i) continue;
    if (a > i) parts.push(text.slice(i, a));
    parts.push(
      <mark key={`${a}-${b}`} className={cls}>
        {text.slice(a, b)}
      </mark>,
    );
    i = b;
  }
  if (i < text.length) parts.push(text.slice(i));
  return <>{parts}</>;
}

export function DiffView({
  quote,
  source,
  sourceRange,
  diff,
  lang,
}: {
  quote: string;
  source: string;
  sourceRange: [number, number] | null;
  diff: DiffOp[];
  lang: Lang;
}) {
  // Show the matched window of a long hadith with some context; show whole ayat.
  let shown = source;
  let offset = 0;
  if (sourceRange && source.length > 400) {
    const pad = 120;
    offset = Math.max(0, sourceRange[0] - pad);
    const end = Math.min(source.length, sourceRange[1] + pad);
    shown = source.slice(offset, end);
  }
  return (
    <div className="diff">
      <section className="diff-pane" aria-label={ui(lang, "your_text")}>
        <h4>
          <Icon name="paste-text" size={14} />
          {ui(lang, "your_text")} <span style={{ fontWeight: 400 }}>— {ui(lang, "your_text_hint")}</span>
        </h4>
        <p className="diff-text" dir="auto">
          <Highlighted text={quote} marks={ranges(diff, "quote")} cls="d-quote" />
        </p>
      </section>
      <section className="diff-pane diff-pane--source" aria-label={ui(lang, "source_text")}>
        <h4>
          <Icon name="byte-exact" size={14} />
          {ui(lang, "source_text")} <span style={{ fontWeight: 400 }}>— {ui(lang, "source_text_hint")}</span>
        </h4>
        <p className="diff-text source-text" dir="rtl" lang="ar" data-testid="source-text">
          {offset > 0 ? "… " : ""}
          <Highlighted text={shown} marks={ranges(diff, "source")} cls="d-source" offset={offset} />
          {offset + shown.length < source.length ? " …" : ""}
        </p>
      </section>
      {diff.some((o) => o.op !== "equal") && (
        <p className="diff-legend">
          <Icon name="diff-words" size={16} />
          {ui(lang, "diff_legend")}
        </p>
      )}
    </div>
  );
}
