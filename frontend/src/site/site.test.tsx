// eslint-disable-next-line -- vitest runs in node; fs/path are available there
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import ar from "../../../messages/ar.json";
import type { CheckResponse } from "../api";
import { EXAMPLES } from "../Check";
import hero from "../__generated__/hero.json";
import trust from "../__generated__/trust.json";
import { LensDemo, pieces } from "./LensDemo";
import { routeOf } from "./router";
import { SERVICES } from "./services";
import { SITE } from "./strings";
import { useReveal } from "./hooks";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "../../..");
const HERO = hero as unknown as { text: string; response: CheckResponse };

beforeEach(() => {
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("reduce"), addEventListener: () => undefined, removeEventListener: () => undefined }));
});

describe("site strings", () => {
  it("ar and en have identical key sets", () => {
    expect(Object.keys(SITE.ar).sort()).toEqual(Object.keys(SITE.en).sort());
  });
  it("never define their own state labels (the four states come from messages/*.json only)", () => {
    const keys = Object.keys(SITE.ar);
    for (const s of ["found", "partial_match", "needs_review", "not_found"]) expect(keys).not.toContain(`label_${s}`);
    // where a page quotes a state by name inside prose, it must be the exact catalogue label
    for (const v of Object.values(SITE.ar)) for (const m of v.matchAll(/«([^»]+)»/g)) if (/وُجد|مراجعة|مصادرنا/.test(m[1]!)) expect(Object.values(ar.labels)).toContain(m[1]);
  });
  it("carry no judgment vocabulary", () => {
    const forbidden = /محرّف|محرف|مكذوب|موضوع|ضعيف|لا أصل له|fabricated|forged|\bweak\b|\bfake\b|authentic/i;
    for (const lang of ["ar", "en"] as const) for (const [k, v] of Object.entries(SITE[lang])) expect([k, forbidden.test(v)]).toEqual([k, false]);
  });
  it("contain no Quranic ornament brackets — religious text never lives in UI code", () => {
    for (const v of Object.values(SITE.ar)) expect(/[﴿﴾]/.test(v)).toBe(false);
  });
});

describe("generated data (no hand-typed religious text, no invented numbers)", () => {
  it("every trust number is present verbatim on its cited report line", () => {
    for (const it of (trust as { items: { value: string; source: string; line: number; key: string }[] }).items) {
      const line = readFileSync(resolve(ROOT, it.source), "utf-8").split("\n")[it.line - 1] ?? "";
      expect([it.key, line.includes(it.value)]).toEqual([it.key, true]);
    }
  });
  it("examples and the hero post carry their provenance in the repo's cases", () => {
    expect(EXAMPLES.length).toBeGreaterThan(3);
    for (const e of EXAMPLES) expect(e.provenance).toMatch(/eval\/cases\.yaml|smoke|A-016/);
  });
  it("the hero response is internally consistent: spans slice the post, quoted_text matches", () => {
    for (const q of HERO.response.quotes) expect(HERO.text.slice(q.span.start, q.span.end)).toBe(q.quoted_text);
    const states = new Set(HERO.response.quotes.map((q) => q.status));
    expect(states).toEqual(new Set(["found", "partial_match", "needs_review", "not_found"]));
  });
});

describe("LensDemo", () => {
  it("pieces() keeps the post byte-identical", () => {
    const ps = pieces(HERO.text, HERO.response.quotes);
    const flat = ps.map((p) => (p.kind === "text" ? p.text : p.parts.map((x) => x.text).join(""))).join("");
    expect(flat).toBe(HERO.text);
  });
  it("renders the post exactly and every source word is a verbatim slice of the API's source_text", () => {
    const { container } = render(<LensDemo lang="ar" />);
    const post = screen.getByTestId("lens-post");
    const clone = post.cloneNode(true) as HTMLElement;
    clone.querySelectorAll(".lens-diff__src").forEach((e) => e.remove());
    expect(clone.textContent).toBe(HERO.text);
    const sources = HERO.response.quotes.flatMap((q) => q.matches.map((m) => m.source_text));
    const words = Array.from(container.querySelectorAll(".lens-diff__word")).map((e) => e.textContent ?? "");
    expect(words.length).toBeGreaterThan(0);
    for (const w of words) expect(sources.some((s) => s.includes(w))).toBe(true);
  });
  it("never applies transforms/letter-spacing to text (motion is around the text)", () => {
    const css = readFileSync(resolve(HERE, "lux.css"), "utf-8").replace(/\/\*[\s\S]*?\*\//g, "");
    for (const sel of [".lens-post", ".lens-q", ".lens-diff__word", ".lens-diff__mine"]) {
      const start = css.search(new RegExp(`(^|\\n)${sel.replace(".", "\\.")} \\{`));
      expect([sel, start >= 0]).toEqual([sel, true]);
      const block = css.slice(start).split("{")[1]?.split("}")[0] ?? "";
      const ls = /letter-spacing:\s*([^;]+)/.exec(block)?.[1]?.replace("!important", "").trim();
      expect([sel, /transform|scale|skew/.test(block), ls === undefined || ls === "0"]).toEqual([sel, false, true]);
    }
  });
});

describe("services & routing", () => {
  it("every service is live and links to a real surface (E-048/E-049/E-052 shipped)", () => {
    for (const s of SERVICES.filter((x) => !x.live)) expect(s.href.startsWith("/check")).toBe(false);
    expect(SERVICES.filter((x) => x.live).map((x) => x.id)).toEqual(["text", "image", "english", "guard", "api", "receipt", "trust"]);
    expect(SERVICES.find((x) => x.id === "guard")?.href).toBe("/check?mode=guard");
    expect(SERVICES.find((x) => x.id === "english")?.href).toBe("/check?mode=english");
  });
  it("routes resolve", () => {
    expect(routeOf("/")).toBe("home");
    expect(routeOf("/check/")).toBe("check");
    expect(routeOf("/limits")).toBe("trust");
    expect(routeOf("/nope")).toBe("notfound");
  });
});

describe("useReveal — content below the fold can never stay hidden (E-065)", () => {
  function Probe({ tick }: { tick: number }) {
    useReveal();
    return (
      <div>
        <p data-reveal data-testid="a">above {tick}</p>
        <p data-reveal data-testid="b">below {tick}</p>
      </div>
    );
  }
  const rect = (top: number) => ({ top, bottom: top + 10, left: 0, right: 10, width: 10, height: 10, x: 0, y: top, toJSON: () => ({}) }) as DOMRect;
  class IO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  it("re-rendering after mount (Starfield/theme/lang) does not strand elements at data-in=0", () => {
    vi.stubGlobal("IntersectionObserver", IO); // never fires: worst case
    vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }));
    const spy = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      return rect(this.dataset["testid"] === "b" ? 5000 : 10);
    });
    vi.useFakeTimers();
    const { rerender } = render(<Probe tick={0} />);
    expect(screen.getByTestId("a").dataset["in"]).toBe("1");
    expect(screen.getByTestId("b").dataset["in"]).toBe("0");
    rerender(<Probe tick={1} />);
    rerender(<Probe tick={2} />);
    vi.advanceTimersByTime(4100);
    expect(screen.getByTestId("b").dataset["in"]).toBe("1");
    vi.useRealTimers();
    spy.mockRestore();
    vi.unstubAllGlobals();
  });

  it("unmount reveals everything", () => {
    vi.stubGlobal("IntersectionObserver", IO);
    vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }));
    const spy = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(rect(5000));
    const { unmount, container } = render(<Probe tick={0} />);
    const b = container.querySelector('[data-testid="b"]') as HTMLElement;
    expect(b.dataset["in"]).toBe("0");
    unmount();
    expect(b.dataset["in"]).toBe("1");
    spy.mockRestore();
    vi.unstubAllGlobals();
  });
});
