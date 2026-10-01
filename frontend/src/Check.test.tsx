import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ar from "../../messages/ar.json";
import en from "../../messages/en.json";
import type { CheckResponse, SourceInfo } from "./api";
import Check from "./Check";
import { QuoteCard } from "./components/QuoteCard";
import { UI } from "./i18n";
import fixture from "./__fixtures__/check_response.json";
import sourcesFixture from "./__fixtures__/sources.json";

const RESP = fixture as unknown as CheckResponse;
const SOURCES = sourcesFixture as unknown as SourceInfo[];

function mockFetch(resp: CheckResponse = RESP, status = 200) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/health")) return new Response(JSON.stringify({ status: "ok", corpus_loaded: true, corpus: RESP.corpus, counts: {}, rss_mb: 1, build_sha: "t" }), { status: 200 });
    if (url.endsWith("/v1/sources")) return new Response(JSON.stringify(SOURCES), { status: 200 });
    if (url.endsWith("/v1/check")) return new Response(JSON.stringify(resp), { status });
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => {
  vi.stubGlobal("localStorage", { getItem: () => null, setItem: () => undefined });
});
afterEach(() => vi.unstubAllGlobals());

describe("message catalogues", () => {
  it("ar and en have identical key sets (rule 11)", () => {
    const keys = (o: Record<string, unknown>) =>
      Object.entries(o)
        .filter(([k]) => k !== "$comment")
        .flatMap(([s, v]) => Object.keys(v as object).map((k) => `${s}.${k}`))
        .sort();
    expect(keys(ar as Record<string, unknown>)).toEqual(keys(en as Record<string, unknown>));
    expect(Object.keys(UI.ar).sort()).toEqual(Object.keys(UI.en).sort());
  });
});

describe("QuoteCard", () => {
  it("renders the source text byte-exact (rule 4) and highlights the user's typo", () => {
    const q = RESP.quotes[0]!;
    expect(q.status).toBe("needs_review");
    render(<QuoteCard q={q} lang="ar" />);
    const src = screen.getAllByTestId("source-text")[0]!;
    expect(src.textContent).toBe(q.matches[0]!.source_text);
    const marks = src.querySelectorAll("mark.d-source");
    expect(marks.length).toBeGreaterThan(0);
    const quoteMarks = document.querySelectorAll("mark.d-quote");
    expect(Array.from(quoteMarks).map((m) => m.textContent)).toContain("علي");
    expect(screen.getByRole("status").textContent).toContain(ar.labels.needs_review);
  });

  it("never renders a judgment word in our strings", () => {
    const forbidden = /محرّف|محرف|موضوع|مكذوب|لا أصل له|fabricated|forged|weak hadith|authentic hadith/i;
    for (const q of RESP.quotes) {
      const { container, unmount } = render(<QuoteCard q={q} lang="ar" />);
      // strip the user's own text and the verbatim corpus text before scanning
      container.querySelectorAll("[data-testid=quoted-text],[data-testid=source-text],.diff-text").forEach((el) => el.remove());
      expect(container.textContent ?? "").not.toMatch(forbidden);
      unmount();
    }
  });

  it("shows claimed-source mismatch notice with filled variables", () => {
    const q = RESP.quotes[1]!;
    expect(q.claimed_source_mismatch).toBe(true);
    render(<QuoteCard q={q} lang="en" />);
    const li = screen.getByText(/Sahih Muslim/);
    expect(li.textContent).not.toContain("{");
  });

  it("every external link opens safely", () => {
    render(<QuoteCard q={RESP.quotes[0]!} lang="ar" />);
    for (const a of screen.getAllByRole("link")) {
      expect(a).toHaveAttribute("target", "_blank");
      expect(a.getAttribute("rel")).toContain("noopener");
      expect(a.getAttribute("href")).toMatch(/^https:\/\//);
    }
  });
});

describe("Check page", () => {
  it("submits text and renders results, flags and fixed footer", async () => {
    const fetchMock = mockFetch();
    const user = userEvent.setup();
    render(<Check lang="ar" onLang={() => undefined} />);
    const ta = screen.getByLabelText(UI.ar["input_label"]!);
    // the fixture's spans are offsets into this exact text (captured live, docs/manual-test)
    await user.click(ta);
    await user.paste("قال تعالى: إن الله علي كل شيء قدير. وقال ﷺ: «إنما الأعمال بالنيات» رواه مسلم");
    await screen.findByText(UI.ar["status_ok"]!);
    await user.click(screen.getByRole("button", { name: UI.ar["check"]! }));
    await screen.findAllByRole("status");
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/v1/check"), expect.objectContaining({ method: "POST" }));
    expect(screen.getByRole("note").textContent).toContain(ar.notice.refusal);
    expect(screen.getByText(ar.fixed.footer)).toBeInTheDocument();
    expect(screen.getByText(ar.fixed.transparency_notice)).toBeInTheDocument();
    const results = screen.getByRole("main");
    // E-042 workspace: every quote is highlighted inside the user's own text (jsdom has no matchMedia →
    // desktop split mode → the panel shows exactly one card, the pre-selected "attention" quote)
    const annotated = within(results).getByTestId("annotated-text");
    const hls = annotated.querySelectorAll(".hl:not([data-seg='claimed_source']):not([data-seg='isnad'])");
    expect(hls).toHaveLength(2);
    expect(within(results).getAllByTestId("quoted-text")).toHaveLength(1);
  });

  it("renders the API error envelope in the UI language", async () => {
    mockFetch({ error: { code: "rate_limited", message_ar: ar.errors.rate_limited, message_en: en.errors.rate_limited } } as unknown as CheckResponse, 429);
    const user = userEvent.setup();
    render(<Check lang="en" onLang={() => undefined} />);
    await screen.findByText(UI.en["status_ok"]!);
    await user.type(screen.getByLabelText(UI.en["input_label"]!), "x");
    await user.click(screen.getByRole("button", { name: UI.en["check"]! }));
    expect((await screen.findByRole("alert")).textContent).toBe(en.errors.rate_limited);
  });

  it("disables Check until the server reports the corpus loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ status: "loading", corpus_loaded: false, corpus: {}, counts: {}, rss_mb: 1, build_sha: "t" }), { status: 503 })),
    );
    render(<Check lang="ar" onLang={() => undefined} />);
    await screen.findByText(UI.ar["status_loading"]!);
    expect(screen.getByRole("button", { name: UI.ar["check"]! })).toBeDisabled();
  });
});
