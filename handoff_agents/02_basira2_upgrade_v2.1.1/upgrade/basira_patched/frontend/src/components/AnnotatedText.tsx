/** The user's text with every detected quote rendered as an inline, focusable, colour-coded link
 *  to its result card (UX spec §1-B). The text itself is emitted verbatim: `text.slice()` only,
 *  no trimming, no normalisation, `white-space: pre-wrap` preserves the author's line breaks.
 *
 *  Why <a> and not <mark>/<button>: an inline anchor keeps selection/copy natural, is reachable by
 *  Tab, is announced by screen readers as "link, quote 1 of 3, found", and the hash jump lands on
 *  the card (which has tabIndex=-1 + scroll-margin). Colour is never the only channel: status is in
 *  the accessible name and as an underline (box-shadow) that survives monochrome printing. */

import type { Lang, QuoteResult, Status } from "../api";
import { msg, ui } from "../i18n";

const STRONG_RTL = /[\u0590-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
const STRONG_LTR = /[A-Za-z\u00C0-\u024F]/;

/** Direction from the first strong character (what `dir="auto"` does for a single text node). */
export function baseDirection(text: string): "rtl" | "ltr" {
  for (const ch of text) {
    if (STRONG_RTL.test(ch)) return "rtl";
    if (STRONG_LTR.test(ch)) return "ltr";
  }
  return "rtl";
}

export interface Segment {
  text: string;
  quote: QuoteResult | null;
  index: number; // 1-based quote ordinal, 0 for plain text
  repeated?: boolean; // a later occurrence of an already-reported quote
}

/** Split the text into plain / quoted segments. Spans are trusted to be non-overlapping (the
 *  backend merges overlaps); a malformed overlap is skipped rather than drawn, never re-sliced. */
export function segment(text: string, quotes: QuoteResult[]): Segment[] {
  const marks: { start: number; end: number; q: QuoteResult; index: number; repeated: boolean }[] = [];
  quotes.forEach((q, i) => {
    marks.push({ start: q.span.start, end: q.span.end, q, index: i + 1, repeated: false });
    for (const r of q.repeated_spans ?? []) marks.push({ start: r.start, end: r.end, q, index: i + 1, repeated: true });
  });
  marks.sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let cursor = 0;
  for (const m of marks) {
    if (m.start < cursor || m.end > text.length || m.end <= m.start) continue; // overlap/garbage → skip
    if (m.start > cursor) out.push({ text: text.slice(cursor, m.start), quote: null, index: 0 });
    out.push({ text: text.slice(m.start, m.end), quote: m.q, index: m.index, repeated: m.repeated });
    cursor = m.end;
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor), quote: null, index: 0 });
  return out;
}

function label(lang: Lang, index: number, total: number, status: Status, repeated: boolean): string {
  const base = ui(lang, "quote_n_of_m", { n: String(index), m: String(total) }) + "، " + msg(lang, "labels", status);
  return repeated ? `${base} — ${ui(lang, "repeated_occurrence")}` : base;
}

export function AnnotatedText({
  text,
  quotes,
  lang,
  activeId,
  onActivate,
}: {
  text: string;
  quotes: QuoteResult[];
  lang: Lang;
  /** id of the card currently focused/hovered → its highlight gets the `data-active` ring */
  activeId?: string | null;
  onActivate?: (id: string) => void;
}) {
  const segs = segment(text, quotes);
  const total = quotes.length;
  return (
    <div
      className="annotated arabic"
      id="annotated"
      dir={baseDirection(text)}
      lang={baseDirection(text) === "rtl" ? "ar" : "en"}
      role="region"
      aria-label={ui(lang, "annotated_title")}
      tabIndex={-1}
      data-testid="annotated-text"
    >
      {/* No heading INSIDE: the container's textContent must equal the user's text (copy = verbatim). */}
      {segs.map((s, i) =>
        s.quote ? (
          <a
            key={`${s.quote.id}-${i}`}
            className="hl"
            href={`#${s.quote.id}`}
            data-status={s.quote.status}
            data-active={activeId === s.quote.id ? "" : undefined}
            data-repeated={s.repeated ? "" : undefined}
            aria-label={label(lang, s.index, total, s.quote.status, s.repeated ?? false)}
            onClick={(e) => {
              // Let the hash update (deep-linkable), but move focus to the card ourselves because
              // Safari does not scroll inside an overflow container on hash change.
              e.preventDefault();
              history.replaceState(null, "", `#${s.quote!.id}`);
              const card = document.getElementById(s.quote!.id);
              card?.scrollIntoView({ block: "nearest", behavior: "smooth" });
              (card as HTMLElement | null)?.focus({ preventScroll: true });
              onActivate?.(s.quote!.id);
            }}
          >
            {s.text}
          </a>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </div>
  );
}
