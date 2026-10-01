/** E-044/E-045 unit tests: final-vs-preliminary diffing, letter-level nesting, ayah never cut,
 *  long hadith window with word counters (full text in DOM), other positions collapsed. */
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CheckResponse } from "../api";
import fixture from "../__fixtures__/check_response.json";
import { diffStatuses } from "../useProgressiveCheck";
import { Highlighted, SourceText } from "./DiffView";
import { QuoteCard } from "./QuoteCard";

const RESP = fixture as unknown as CheckResponse;

describe("two-phase: diffStatuses", () => {
  it("flags only quotes whose status changed on the same span; no preliminary → empty", () => {
    const q = RESP.quotes[0]!;
    const prelim = { ...RESP, quotes: [{ ...q, status: "needs_review" as const }] };
    const final = { ...RESP, quotes: [q, { ...q, id: "q9", span: { start: 900, end: 950 } }] };
    expect([...diffStatuses(prelim, final)]).toEqual(q.status === "needs_review" ? [] : [q.id]);
    expect(diffStatuses(null, final).size).toBe(0);
  });
});

describe("letter-level highlight", () => {
  it("nests the differing letter inside the word mark and keeps textContent byte-exact", () => {
    const text = "إن الله علي كل";
    const { container } = render(
      <p>
        <Highlighted text={text} marks={[[8, 11]]} cls="d-quote" inner={[[10, 11]]} />
      </p>,
    );
    expect(container.textContent).toBe(text);
    const word = container.querySelector("mark.d-quote")!;
    expect(word.textContent).toBe("علي");
    expect(word.querySelector("mark.d-letter")!.textContent).toBe("ي");
  });
});

describe("long sources", () => {
  const long = Array.from({ length: 120 }, (_, i) => `كلمة${i}`).join(" "); // > 400 chars
  it("an ayah is never windowed, however long", () => {
    const { container } = render(<SourceText source={long} sourceRange={[600, 640]} marks={[]} inner={[]} lang="ar" whole />);
    expect(container.querySelector("[data-testid='source-text']")!.textContent).toBe(long);
    expect(container.querySelector(".word-counter")).toBeNull();
  });
  it("a long hadith shows a window with word counters and keeps the full text in the DOM", () => {
    const { container } = render(<SourceText source={long} sourceRange={[600, 640]} marks={[]} inner={[]} lang="ar" whole={false} />);
    expect(container.querySelector("[data-testid='source-text-full']")!.textContent).toBe(long);
    expect(container.querySelectorAll(".word-counter").length).toBe(2);
    expect(container.textContent).not.toMatch(/… $/); // no bare ellipsis
  });
});

describe("compact card", () => {
  it("shows the first position open and collapses the others; card is a hash target", () => {
    const qr = RESP.quotes[0]!;
    expect(qr.matches.length).toBeGreaterThan(1);
    const { container } = render(<QuoteCard q={qr} lang="ar" n={1} />);
    const details = container.querySelector("details.more")!;
    expect(details.hasAttribute("open")).toBe(false);
    expect(details.querySelectorAll("article.match")).toHaveLength(qr.matches.length - 1);
    expect(container.querySelector("section.quote")!.id).toBe(qr.id);
  });
});
