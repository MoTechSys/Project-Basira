/** Pure layout for the X-ray view (no React). */

import type { QuoteResult } from "../api";

export interface Piece {
  start: number;
  end: number;
  /** quote index in `quotes`, or -1 for plain text */
  q: number;
  /** "quote" body, attribution/isnad annotation, or plain */
  role: "quote" | "claimed_source" | "isnad" | "plain";
}

/** Pure, O(n log n): flattens quote spans + typed segments into non-overlapping ordered pieces covering
 *  [0, text.length). Quote bodies win over annotations; earlier quotes win ties (spans never overlap
 *  after backend merge, this is defensive). Exported for tests. */
export function pieces(textLength: number, quotes: QuoteResult[]): Piece[] {
  type Iv = { start: number; end: number; q: number; role: Piece["role"]; rank: number };
  const ivs: Iv[] = [];
  quotes.forEach((q, i) => {
    const body = q.segments?.find((s) => s.type === "Ayah" || s.type === "matn");
    const a = body?.start ?? q.span.start;
    const b = body?.end ?? q.span.end;
    if (b > a) ivs.push({ start: a, end: b, q: i, role: "quote", rank: 0 });
    for (const s of q.segments ?? []) {
      if (s.type === "claimed_source" || s.type === "isnad") {
        if (s.end > s.start) ivs.push({ start: s.start, end: s.end, q: i, role: s.type, rank: 1 });
      }
    }
  });
  ivs.sort((x, y) => x.rank - y.rank || x.start - y.start || x.q - y.q);
  // paint into an ownership array of interval boundaries (sweep, no per-char allocation)
  const taken: Iv[] = [];
  const overlaps = (a: number, b: number) => taken.some((t) => t.start < b && a < t.end);
  for (const iv of ivs) {
    const a = Math.max(0, iv.start);
    const b = Math.min(textLength, iv.end);
    if (b <= a) continue;
    if (!overlaps(a, b)) {
      taken.push({ ...iv, start: a, end: b });
      continue;
    }
    // annotation partially covered: keep the uncovered sub-ranges only
    if (iv.rank === 0) continue;
    let cur = a;
    const cuts = taken.filter((t) => t.start < b && a < t.end).sort((x, y) => x.start - y.start);
    for (const c of cuts) {
      if (c.start > cur) taken.push({ ...iv, start: cur, end: c.start });
      cur = Math.max(cur, c.end);
    }
    if (cur < b) taken.push({ ...iv, start: cur, end: b });
  }
  taken.sort((x, y) => x.start - y.start);
  const out: Piece[] = [];
  let i = 0;
  for (const t of taken) {
    if (t.start > i) out.push({ start: i, end: t.start, q: -1, role: "plain" });
    out.push({ start: t.start, end: t.end, q: t.q, role: t.role });
    i = t.end;
  }
  if (i < textLength) out.push({ start: i, end: textLength, q: -1, role: "plain" });
  return out;
}
