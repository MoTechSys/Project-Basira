/** Pure range helpers for diff highlighting (no React). */

import type { DiffOp } from "../api";

export type Range = [number, number];

/** Letter-level ranges, already absolute offsets, sorted. */
export function letterRanges(ops: DiffOp[], side: "quote" | "source"): Range[] {
  const out: Range[] = [];
  for (const o of ops) {
    const ls = side === "quote" ? o.quote_letters : o.source_letters;
    for (const r of ls ?? []) if (r[1] > r[0]) out.push([r[0], r[1]]);
  }
  return out.sort((a, b) => a[0] - b[0]);
}
