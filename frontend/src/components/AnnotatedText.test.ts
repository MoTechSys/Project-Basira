import { describe, expect, it } from "vitest";
import type { QuoteResult } from "../api";
import { buildRuns } from "./AnnotatedText";

function q(id: string, start: number, end: number, extra: Partial<QuoteResult> = {}): QuoteResult {
  return {
    id,
    span: { start, end },
    quoted_text: "",
    kind: "quran",
    language: "ar",
    source_modality: "text",
    claimed_source: null,
    claimed_source_mismatch: false,
    status: "found",
    review_reason: null,
    score: 1,
    message_key: "found",
    notice_keys: [],
    matches: [],
    total_positions: 1,
    external_search_links: [],
    ...extra,
  };
}

describe("buildRuns — in-place highlights", () => {
  const text = "ab cd ef gh ij";

  it("reproduces the input exactly (no char lost, added or moved)", () => {
    const runs = buildRuns(text, [q("1", 3, 5), q("2", 9, 11)]);
    expect(runs.map((r) => r.text).join("")).toBe(text);
    expect(runs.filter((r) => r.kind === "quote").map((r) => r.text)).toEqual(["cd", "gh"]);
  });

  it("resolves overlaps deterministically (first wins) and keeps the text intact", () => {
    const runs = buildRuns(text, [q("1", 0, 6), q("2", 3, 8)]);
    expect(runs.map((r) => r.text).join("")).toBe(text);
    const quotes = runs.filter((r) => r.kind === "quote");
    expect(quotes.map((r) => r.text)).toEqual(["ab cd ", "ef"]);
  });

  it("splits isnad / claimed_source satellites from the quoted text", () => {
    const runs = buildRuns(text, [
      q("1", 6, 8, { segments: [{ type: "matn", start: 6, end: 8 }, { type: "claimed_source", start: 12, end: 14 }, { type: "isnad", start: 0, end: 2 }] }),
    ]);
    expect(runs.map((r) => r.text).join("")).toBe(text);
    const segs = runs.filter((r) => r.kind === "quote").map((r) => (r.kind === "quote" ? [r.seg, r.text] : null));
    expect(segs).toEqual([
      ["isnad", "ab"],
      ["text", "ef"],
      ["claimed_source", "ij"],
    ]);
  });

  it("marks repeated occurrences as repeats of the same quote", () => {
    const runs = buildRuns(text, [q("1", 0, 2, { repeated_spans: [{ start: 12, end: 14 }] })]);
    const quotes = runs.filter((r) => r.kind === "quote");
    expect(quotes.map((r) => (r.kind === "quote" ? r.repeat : null))).toEqual([false, true]);
    expect(runs.map((r) => r.text).join("")).toBe(text);
  });

  it("clamps out-of-range spans instead of throwing", () => {
    const runs = buildRuns(text, [q("1", 10, 99)]);
    expect(runs.map((r) => r.text).join("")).toBe(text);
  });
});
