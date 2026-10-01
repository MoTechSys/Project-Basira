/** Side-by-side highlight of the user's quote and the VERBATIM source text.
 *  The source string is rendered exactly as received (textContent === corpus field); only <mark> wrappers
 *  are added around character ranges supplied by the backend diff. Nothing is re-ordered or normalized.
 *
 *  E-045 (long sources): an ayah is NEVER shown cut (`whole`). A long hadith shows a window around the
 *  match, but the full text stays in the DOM (copy + screen reader get everything) and the hidden parts
 *  are announced as explicit word counters ("… 23 words before") that expand it — never a bare "…" that
 *  could read as "the text is incomplete". Word counts are display-only; nothing is compared. */

import { useId, useState } from "react";
import type { DiffOp, Lang } from "../api";
import { Icon } from "../brand";
import { ui } from "../i18n";
import { letterRanges, type Range } from "../lib/ranges";

export function ranges(ops: DiffOp[], side: "quote" | "source"): Range[] {
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

/** Wraps char ranges in <mark>. `inner` (letter-level ranges) are nested INSIDE the word marks, so
 *  textContent stays identical to `text` (byte-exact rule) and a word mark still reads as one word. */
export function Highlighted({
  text,
  marks,
  cls,
  offset = 0,
  inner = [],
}: {
  text: string;
  marks: Range[];
  cls: string;
  offset?: number;
  inner?: Range[];
}) {
  const parts: React.ReactNode[] = [];
  let i = 0;
  const nest = (a: number, b: number): React.ReactNode[] => {
    const out: React.ReactNode[] = [];
    let j = a;
    for (const [x0, y0] of inner) {
      const x = Math.max(a, x0 - offset);
      const y = Math.min(b, y0 - offset);
      if (y <= x || y <= j) continue;
      if (x > j) out.push(text.slice(j, x));
      out.push(
        <mark key={`l${x}-${y}`} className="d-letter">
          {text.slice(Math.max(x, j), y)}
        </mark>,
      );
      j = y;
    }
    if (j < b) out.push(text.slice(j, b));
    return out;
  };
  for (const [a0, b0] of marks) {
    const a = Math.max(i, Math.max(0, a0 - offset));
    const b = Math.min(text.length, b0 - offset);
    if (b <= a) continue;
    if (a > i) parts.push(text.slice(i, a));
    parts.push(
      <mark key={`${a}-${b}`} className={cls}>
        {nest(a, b)}
      </mark>,
    );
    i = b;
  }
  if (i < text.length) parts.push(text.slice(i));
  return <>{parts}</>;
}

export const WINDOW_MIN_CHARS = 400;
const PAD = 120;
const words = (s: string): number => (s.trim() ? s.trim().split(/\s+/).length : 0);

/** The source passage. Quran (`whole`) and short texts: rendered in full. Long hadith: a window around
 *  the match with word-counter buttons; the full text is always present (`.source-full`, sr-only). */
export function SourceText({
  source,
  sourceRange,
  marks,
  inner,
  lang,
  whole,
}: {
  source: string;
  sourceRange: [number, number] | null;
  marks: Range[];
  inner: Range[];
  lang: Lang;
  whole: boolean;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const windowed = !whole && !open && sourceRange !== null && source.length > WINDOW_MIN_CHARS;
  if (!windowed) {
    return (
      <div className="source">
        <p className="diff-text source-text" dir="rtl" lang="ar" data-testid="source-text">
          <Highlighted text={source} marks={marks} cls="d-source" inner={inner} />
        </p>
        {!whole && open && (
          <button type="button" className="btn btn--ghost btn--sm" aria-expanded="true" aria-controls={id} onClick={() => setOpen(false)}>
            {ui(lang, "hide_full_source")}
          </button>
        )}
      </div>
    );
  }
  const a = Math.max(0, sourceRange[0] - PAD);
  const b = Math.min(source.length, sourceRange[1] + PAD);
  const before = words(source.slice(0, a));
  const after = words(source.slice(b));
  const nf = new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en");
  return (
    <div className="source" id={id}>
      <p className="source__note" dir="auto">
        {ui(lang, "source_full_note", { n: nf.format(words(source)) })}
      </p>
      {/* full text stays in the DOM for copy / assistive tech; visually hidden */}
      <p className="sr-only source-full" lang="ar" data-testid="source-text-full">
        {source}
      </p>
      <p className="diff-text source-text source-window" dir="rtl" lang="ar" aria-hidden="true" data-testid="source-text">
        {before > 0 && (
          <button type="button" className="word-counter" onClick={() => setOpen(true)}>
            {ui(lang, "words_before", { n: nf.format(before) })}
          </button>
        )}{" "}
        <Highlighted text={source.slice(a, b)} marks={marks} cls="d-source" offset={a} inner={inner} />{" "}
        {after > 0 && (
          <button type="button" className="word-counter" onClick={() => setOpen(true)}>
            {ui(lang, "words_after", { n: nf.format(after) })}
          </button>
        )}
      </p>
      <button type="button" className="btn btn--ghost btn--sm" aria-expanded="false" aria-controls={id} onClick={() => setOpen(true)}>
        {ui(lang, "show_full_source")}
      </button>
    </div>
  );
}

export function DiffView({
  quote,
  source,
  sourceRange,
  diff,
  lang,
  whole = false,
}: {
  quote: string;
  source: string;
  sourceRange: [number, number] | null;
  diff: DiffOp[];
  lang: Lang;
  /** never window the source (Quran: an ayah is never shown cut in the middle) */
  whole?: boolean;
}) {
  const letters = diff.some((o) => (o.quote_letters?.length ?? 0) > 0 || (o.source_letters?.length ?? 0) > 0);
  return (
    <div className="diff">
      <section className="diff-pane" aria-label={ui(lang, "your_text")}>
        <h4>
          <Icon name="paste-text" size={14} />
          {ui(lang, "your_text")} <span style={{ fontWeight: 400 }}>— {ui(lang, "your_text_hint")}</span>
        </h4>
        <p className="diff-text" dir="auto">
          <Highlighted text={quote} marks={ranges(diff, "quote")} cls="d-quote" inner={letterRanges(diff, "quote")} />
        </p>
      </section>
      <section className="diff-pane diff-pane--source" aria-label={ui(lang, "source_text")}>
        <h4>
          <Icon name="byte-exact" size={14} />
          {ui(lang, "source_text")} <span style={{ fontWeight: 400 }}>— {ui(lang, "source_text_hint")}</span>
        </h4>
        <SourceText source={source} sourceRange={sourceRange} marks={ranges(diff, "source")} inner={letterRanges(diff, "source")} lang={lang} whole={whole} />
      </section>
      {diff.some((o) => o.op !== "equal") && (
        <p className="diff-legend">
          <Icon name="diff-words" size={16} />
          {ui(lang, letters ? "diff_legend_letters" : "diff_legend")}
        </p>
      )}
    </div>
  );
}
