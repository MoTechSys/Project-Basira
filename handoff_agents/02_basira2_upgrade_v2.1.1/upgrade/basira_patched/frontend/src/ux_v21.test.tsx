/** v2.1 UX layer: annotated text, progressive two-request flow, compact card, share link. */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ar from "../../messages/ar.json";
import type { CheckResponse, QuoteResult, SourceInfo } from "./api";
import Check from "./Check";
import { AnnotatedText, baseDirection, segment } from "./components/AnnotatedText";
import { AyahText, WORDS_FULL } from "./components/AyahText";
import { QuoteCard } from "./components/QuoteCard";
import { UI } from "./i18n";
import { decodeShare, encodeShare, fitsQr } from "./share";
import fixture from "./__fixtures__/check_response.json";
import sourcesFixture from "./__fixtures__/sources.json";

const RESP = fixture as unknown as CheckResponse;
const SOURCES = sourcesFixture as unknown as SourceInfo[];
// The fixture text the spans refer to (quotes[0] = 11..34, quotes[1] = 45..65).
const TEXT = "قال رسول: " + RESP.quotes[0]!.quoted_text + " وقال أيضا: " + RESP.quotes[1]!.quoted_text + " انتهى";

beforeEach(() => {
  vi.stubGlobal("localStorage", { getItem: () => null, setItem: () => undefined });
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());

function respFor(text: string, stage: "rules" | "full", extra: Partial<CheckResponse> = {}): CheckResponse {
  const q0 = { ...RESP.quotes[0]!, span: { start: text.indexOf(RESP.quotes[0]!.quoted_text), end: text.indexOf(RESP.quotes[0]!.quoted_text) + RESP.quotes[0]!.quoted_text.length } };
  const q1 = { ...RESP.quotes[1]!, span: { start: text.indexOf(RESP.quotes[1]!.quoted_text), end: text.indexOf(RESP.quotes[1]!.quoted_text) + RESP.quotes[1]!.quoted_text.length } };
  return {
    ...RESP,
    extraction_stage: stage,
    extraction_provider: stage === "rules" ? "rules" : "mock",
    quotes: stage === "rules" ? [q0] : [q0, q1], // the LLM "adds" the second quote
    determinism_hash: stage === "rules" ? "aaaaaaaa11111111" : "bbbbbbbb22222222",
    ...extra,
  };
}

/** fetch mock that resolves the two stages independently (so we can control order). */
function mockProgressive(text: string, opts: { fullDelayMs?: number; fullStatus?: number; rulesFail?: boolean } = {}) {
  const calls: string[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/health")) return new Response(JSON.stringify({ status: "ok", corpus_loaded: true, corpus: RESP.corpus, counts: {}, rss_mb: 1, build_sha: "t" }), { status: 200 });
    if (url.endsWith("/v1/sources")) return new Response(JSON.stringify(SOURCES), { status: 200 });
    if (url.endsWith("/v1/check")) {
      const body = JSON.parse(String(init?.body)) as { options: { stage: "rules" | "full" } };
      calls.push(body.options.stage);
      if (body.options.stage === "rules") {
        if (opts.rulesFail) return new Response("{}", { status: 500 });
        return new Response(JSON.stringify(respFor(text, "rules")), { status: 200 });
      }
      await new Promise((r) => setTimeout(r, opts.fullDelayMs ?? 30));
      if (opts.fullStatus && opts.fullStatus !== 200)
        return new Response(JSON.stringify({ error: { code: "internal", message_ar: ar.errors.internal, message_en: "x" } }), { status: opts.fullStatus });
      return new Response(JSON.stringify(respFor(text, "full")), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fn);
  return { fn, calls };
}

describe("AnnotatedText", () => {
  it("re-emits the user's text byte-exact and wraps each span in a status link", () => {
    const quotes = respFor(TEXT, "full").quotes;
    const segs = segment(TEXT, quotes);
    expect(segs.map((s) => s.text).join("")).toBe(TEXT);
    render(<AnnotatedText text={TEXT} quotes={quotes} lang="ar" />);
    const region = screen.getByTestId("annotated-text");
    expect(region.textContent).toBe(TEXT);
    const links = within(region).getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", `#${quotes[0]!.id}`);
    expect(links[0]).toHaveAttribute("data-status", quotes[0]!.status);
    expect(links[0]!.getAttribute("aria-label")).toContain(ar.labels[quotes[0]!.status as keyof typeof ar.labels]);
    expect(links[0]!.getAttribute("aria-label")).toContain("1");
    expect(region).toHaveAttribute("dir", "rtl");
  });

  it("skips overlapping/garbage spans instead of re-slicing, and draws repeated spans", () => {
    const q = respFor(TEXT, "full").quotes[0]!;
    const bad: QuoteResult = { ...q, id: "bad", span: { start: q.span.start + 3, end: q.span.end + 3 } };
    const rep: QuoteResult = { ...q, repeated_spans: [{ start: TEXT.length - 5, end: TEXT.length }] };
    const segs = segment(TEXT, [rep, bad]);
    expect(segs.map((s) => s.text).join("")).toBe(TEXT);
    expect(segs.filter((s) => s.quote && !s.repeated)).toHaveLength(1);
    expect(segs.filter((s) => s.repeated)).toHaveLength(1);
  });

  it("direction follows the first strong character", () => {
    expect(baseDirection("The Prophet said: إنما الأعمال")).toBe("ltr");
    expect(baseDirection("  123 ﴿قل هو الله أحد﴾")).toBe("rtl");
    expect(baseDirection("")).toBe("rtl");
  });
});

describe("AyahText — long sources are never cut in the DOM", () => {
  const long = Array.from({ length: WORDS_FULL + 15 }, (_, i) => `كلمة${i}`).join(" ");
  it("clamps visually but keeps the full text and states the word count", () => {
    render(<AyahText source={long} marks={[]} matchRange={[0, 10]} lang="ar" isQuran />);
    expect(screen.getByTestId("source-text").textContent).toBe(long);
    expect(screen.getByText(/40/)).toBeInTheDocument(); // "(40 كلمة)"
    expect(screen.getByRole("button", { name: UI.ar["show_full_ayah"]! })).toHaveAttribute("aria-expanded", "false");
  });
  it("far match → window with explicit word counters, full text still present for AT/copy", async () => {
    const pos = long.indexOf("كلمة38");
    render(<AyahText source={long} marks={[]} matchRange={[pos, pos + 6]} lang="ar" isQuran />);
    expect(screen.getByTestId("source-text-full").textContent).toBe(long);
    const before = screen.getByText(/قبلها/);
    expect(before.tagName).toBe("BUTTON");
    expect(before.textContent).toMatch(/\d+/);
    expect(document.body.textContent).not.toMatch(/(^|\s)…(\s|$)/); // no bare ellipsis
    await userEvent.setup().click(before);
    expect(screen.getByTestId("source-text").textContent).toBe(long);
  });
  it("short sources render plainly", () => {
    render(<AyahText source="قل هو الله أحد" marks={[]} matchRange={null} lang="ar" isQuran />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("QuoteCard compact", () => {
  it("folds non-safety notices and extra positions behind <details>, keeps mismatch visible", () => {
    const q = { ...RESP.quotes[1]!, notice_keys: [...RESP.quotes[1]!.notice_keys, "ohd_numbering"] };
    render(<QuoteCard q={q} lang="ar" compact />);
    const card = screen.getByRole("region", { hidden: true }) ?? document.querySelector(".quote-card");
    expect(card).toHaveAttribute("data-compact");
    expect(screen.getByText(new RegExp(ar.notice.claimed_source_mismatch.split("{")[0]!.trim().slice(0, 8)))).toBeInTheDocument();
    expect(document.querySelectorAll("details.fold").length).toBeGreaterThan(0);
  });
  it("shows the repeat multiplier and the 'updated' tag", () => {
    const q = { ...RESP.quotes[0]!, repeated_spans: [{ start: 0, end: 1 }, { start: 2, end: 3 }] };
    render(<QuoteCard q={q} lang="ar" updated />);
    expect(screen.getByText("×3")).toBeInTheDocument();
    expect(screen.getByText(UI.ar["updated_tag"]!)).toBeInTheDocument();
  });
});

describe("Check — progressive flow", () => {
  it("fires rules+full in parallel, shows preliminary, then the final REPLACES it", async () => {
    const { calls } = mockProgressive(TEXT, { fullDelayMs: 80 });
    const user = userEvent.setup();
    render(<Check lang="ar" onLang={() => undefined} />);
    await screen.findByText(UI.ar["status_ok"]!);
    await user.click(screen.getByLabelText(UI.ar["input_label"]!));
    await user.paste(TEXT);
    await user.click(screen.getByRole("button", { name: UI.ar["check"]! }));

    // both requests left at once
    await waitFor(() => expect(calls.sort()).toEqual(["full", "rules"]));
    // preliminary: 1 card, actions disabled, note says preliminary
    await screen.findByText(UI.ar["preliminary_note"]!);
    expect(screen.getAllByTestId("quoted-text")).toHaveLength(1);
    expect(screen.getByRole("button", { name: UI.ar["copy_report"]! })).toBeDisabled();
    expect(screen.getByRole("button", { name: UI.ar["share_link"]! })).toBeDisabled();
    // the input is replaced by the annotated text
    expect(screen.getByTestId("annotated-text").textContent).toBe(TEXT);

    // final: 2 cards, hash shown, actions enabled, second card tagged as LLM-added
    await screen.findAllByText(/bbbbbbbb/);
    expect(screen.getAllByTestId("quoted-text")).toHaveLength(2);
    expect(screen.getByRole("button", { name: UI.ar["copy_report"]! })).toBeEnabled();
    expect(screen.getByText(UI.ar["added_by_llm"]!)).toBeInTheDocument();
    expect(within(screen.getByTestId("annotated-text")).getAllByRole("link")).toHaveLength(2);
  });

  it("keeps the preliminary result and offers retry when the full stage fails", async () => {
    mockProgressive(TEXT, { fullStatus: 500 });
    const user = userEvent.setup();
    render(<Check lang="ar" onLang={() => undefined} />);
    await screen.findByText(UI.ar["status_ok"]!);
    await user.click(screen.getByLabelText(UI.ar["input_label"]!));
    await user.paste(TEXT);
    await user.click(screen.getByRole("button", { name: UI.ar["check"]! }));
    await screen.findByText(new RegExp(UI.ar["failed_after_rules_note"]!.slice(0, 12)));
    expect(screen.getAllByTestId("quoted-text")).toHaveLength(1);
    expect(screen.getByRole("button", { name: UI.ar["retry"]! })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull(); // not an error — a labelled partial state
  });

  it("'edit text' drops the result and returns to the textarea (no stale highlights)", async () => {
    mockProgressive(TEXT, { fullDelayMs: 5 });
    const user = userEvent.setup();
    render(<Check lang="ar" onLang={() => undefined} />);
    await screen.findByText(UI.ar["status_ok"]!);
    await user.click(screen.getByLabelText(UI.ar["input_label"]!));
    await user.paste(TEXT);
    await user.click(screen.getByRole("button", { name: UI.ar["check"]! }));
    await screen.findAllByText(/bbbbbbbb/);
    await user.click(screen.getByRole("button", { name: UI.ar["edit_text"]! }));
    expect(screen.queryByTestId("annotated-text")).toBeNull();
    expect(screen.queryAllByTestId("quoted-text")).toHaveLength(0);
    expect((screen.getByLabelText(UI.ar["input_label"]!) as HTMLTextAreaElement).value).toBe(TEXT);
  });

  it("a share hash pre-fills the text with a banner and does NOT auto-check", async () => {
    const hash = await encodeShare({ text: TEXT, lang: "ar" });
    history.replaceState(null, "", "/" + hash);
    const { calls } = mockProgressive(TEXT);
    render(<Check lang="ar" onLang={() => undefined} />);
    await screen.findByText(UI.ar["shared_banner"]!);
    expect((screen.getByLabelText(UI.ar["input_label"]!) as HTMLTextAreaElement).value).toBe(TEXT);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(calls).toHaveLength(0);
    expect(location.hash).toBe("");
  });
});

describe("share link", () => {
  it("round-trips Arabic text through deflate-raw + base64url and never reaches the server", async () => {
    const hash = await encodeShare({ text: TEXT, lang: "ar" });
    expect(hash.startsWith("#t=")).toBe(true);
    expect(hash).toContain("&l=ar&v=1");
    const back = await decodeShare(hash, 5000);
    expect(back).toEqual({ text: TEXT, lang: "ar" });
  });
  it("rejects garbage, over-length and empty payloads with null (never throws)", async () => {
    expect(await decodeShare("#t=%%%", 5000)).toBeNull();
    expect(await decodeShare("#x=1", 5000)).toBeNull();
    expect(await decodeShare("", 5000)).toBeNull();
    const big = await encodeShare({ text: "ا".repeat(6000), lang: "ar" });
    expect(await decodeShare(big, 5000)).toBeNull();
  });
  it("5,000 Arabic chars fit a URL comfortably; QR gate works", async () => {
    const prose = Array.from({ length: 900 }, (_, i) => `كلمة${i % 97}مختلفة`).join(" ").slice(0, 5000);
    const hash = await encodeShare({ text: prose, lang: "ar" });
    expect(hash.length).toBeLessThan(8000);
    expect(fitsQr("https://x.y/" + "a".repeat(2000))).toBe(true);
    expect(fitsQr("https://x.y/" + "a".repeat(2400))).toBe(false);
  });
});

describe("HarakatView (E-037) — real response fixture for 35:28 with swapped case endings", () => {
  it("renders both lines verbatim and marks exactly the conflicting letters", async () => {
    const mod = await import("./__fixtures__/check_response_harakat.json");
    const resp = (mod.default ?? mod) as unknown as CheckResponse;
    const q = resp.quotes[0]!;
    const m = q.matches[0]!;
    expect(q.status).toBe("found"); // I14: status unchanged
    expect(m.harakat_verdict).toBe("conflict");
    render(<QuoteCard q={q} lang="ar" />);
    const view = screen.getByTestId("harakat-view");
    const yours = within(view).getByTestId("harakat-quote");
    const ref = within(view).getByTestId("harakat-ref");
    expect(yours.textContent).toBe(q.quoted_text);
    const rng = m.harakat_reference_range!;
    expect(ref.textContent).toBe(m.harakat_reference!.slice(rng[0], rng[1]));
    const marked = Array.from(yours.querySelectorAll("mark.d-haraka")).map((e) => e.textContent);
    expect(marked).toEqual(["هُ", "ءَ"]);
    const markedRef = Array.from(ref.querySelectorAll("mark.d-haraka")).map((e) => e.textContent);
    expect(markedRef).toEqual(["هَ", "ءُ"]);
    // notice visible with the count filled, no raw template braces
    const li = screen.getByText(/الحروف مطابقة/);
    expect(li.textContent).not.toContain("{");
    expect(li.textContent).toContain("2");
  });
  it("is absent when the verdict is not a conflict", () => {
    render(<QuoteCard q={RESP.quotes[1]!} lang="ar" />);
    expect(screen.queryByTestId("harakat-view")).toBeNull();
  });
});
