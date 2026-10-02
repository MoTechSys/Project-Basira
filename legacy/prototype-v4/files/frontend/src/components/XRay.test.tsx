import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CheckResponse, QuoteResult } from "../api";
import fixture from "../__fixtures__/check_response.json";
import { letterRanges } from "../lib/ranges";
import { pieces } from "../lib/xray";
import { Highlighted } from "./DiffView";
import { QuoteCard } from "./QuoteCard";
import { XRay } from "./XRay";

const RESP = fixture as unknown as CheckResponse;
const TEXT = "قال تعالى: ﴿إن الله علي كل شيء قدير﴾ وقال ﷺ «إنما الأعمال بالنيات» رواه البخاري";

function q(id: string, start: number, end: number, extra: QuoteResult["segments"] = []): QuoteResult {
  return { ...RESP.quotes[0]!, id, span: { start, end }, segments: [{ type: "Ayah", start, end }, ...(extra ?? [])] };
}

describe("XRay.pieces", () => {
  it("covers the text exactly once, in order, with no overlap", () => {
    const qs = [q("a", 12, 35), q("b", 47, 67, [{ type: "claimed_source", start: 69, end: 79 }])];
    const ps = pieces(TEXT.length, qs);
    expect(ps[0]!.start).toBe(0);
    expect(ps[ps.length - 1]!.end).toBe(TEXT.length);
    for (let i = 1; i < ps.length; i++) expect(ps[i]!.start).toBe(ps[i - 1]!.end);
    expect(ps.map((p) => TEXT.slice(p.start, p.end)).join("")).toBe(TEXT);
    expect(ps.filter((p) => p.role === "quote").map((p) => p.q)).toEqual([0, 1]);
    expect(ps.find((p) => p.role === "claimed_source")).toMatchObject({ start: 69, end: 79, q: 1 });
  });

  it("an annotation never paints over a quote body (quote wins, annotation is clipped)", () => {
    const qs = [q("a", 10, 20, [{ type: "claimed_source", start: 15, end: 30 }])];
    const ps = pieces(40, qs);
    expect(ps.find((p) => p.role === "claimed_source")).toMatchObject({ start: 20, end: 30 });
  });

  it("clamps out-of-range offsets defensively", () => {
    const ps = pieces(10, [q("a", 5, 99)]);
    expect(ps[ps.length - 1]!.end).toBe(10);
  });
});

describe("XRay view", () => {
  it("renders the user's text byte-exact and links each quote to its card", () => {
    const qs = [q("qa", 12, 35)];
    render(<XRay text={TEXT} quotes={qs} lang="ar" />);
    const p = screen.getByTestId("xray-text");
    // only the superscript index is added; everything else is the user's text unchanged
    const clone = p.cloneNode(true) as HTMLElement;
    clone.querySelectorAll("sup").forEach((s) => s.remove());
    expect(clone.textContent).toBe(TEXT);
    const a = p.querySelector("a.xray__q")!;
    expect(a.getAttribute("href")).toBe("#qa");
    expect(a.getAttribute("data-status")).toBe(qs[0]!.status);
    fireEvent.click(a); // no card in DOM → falls back to the anchor without throwing
  });

  it("renders nothing without quotes", () => {
    const { container } = render(<XRay text={TEXT} quotes={[]} lang="ar" />);
    expect(container.innerHTML).toBe("");
  });
});

describe("letter-level highlight", () => {
  it("nests the differing letter inside the word mark and keeps textContent byte-exact", () => {
    const text = "إن الله علي كل";
    const { container } = render(
      <p>
        <Highlighted text={text} marks={[[8, 11]]} cls="d-quote" inner={letterRanges([{ op: "replace", quote_range: [2, 3], source_range: [2, 3], quote_chars: [8, 11], source_chars: [0, 0], quote_letters: [[10, 11]] }], "quote")} />
      </p>,
    );
    expect(container.textContent).toBe(text);
    const word = container.querySelector("mark.d-quote")!;
    expect(word.textContent).toBe("علي");
    expect(word.querySelector("mark.d-letter")!.textContent).toBe("ي");
  });

  it("respects the display offset for windowed sources", () => {
    const { container } = render(<Highlighted text="abcdef" marks={[[12, 15]]} cls="d-source" offset={10} inner={[[13, 14]]} />);
    expect(container.querySelector("mark.d-source")!.textContent).toBe("cde");
    expect(container.querySelector("mark.d-letter")!.textContent).toBe("d");
  });
});

describe("compact card", () => {
  it("shows the first position open and collapses the others", () => {
    const qr = RESP.quotes[0]!;
    expect(qr.matches.length).toBeGreaterThan(1);
    const { container } = render(<QuoteCard q={qr} lang="ar" n={1} />);
    const details = container.querySelector("details.more")!;
    expect(details).not.toBeNull();
    expect(details.hasAttribute("open")).toBe(false);
    expect(details.querySelectorAll("article.match")).toHaveLength(qr.matches.length - 1);
    expect(container.querySelector("section.quote")!.id).toBe(qr.id);
  });
});
