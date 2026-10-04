/** «العدسة» — the home-page hook. A real post and the REAL engine response for it (recorded verbatim by
 *  scripts/gen_examples.py --record, or fetched live with the «run live» button).
 *
 *  Choreography (≈4 s): the post is visible at once (LCP) → a lens ring travels to each quotation → the
 *  quotation lights up in its state colour → for a differing word, the source word appears in a frame
 *  above it → the result rail fills in.
 *
 *  Red lines enforced here:
 *  - Every Arabic religious string on screen is either the user-style post (from eval/smoke cases) or a
 *    corpus field from the API response (`source_text` slices). Nothing typed by hand.
 *  - Motion is AROUND the text: the lens is a ring that moves; letters are never scaled, stretched,
 *    split, skewed or transformed. Text only changes opacity / background tint. No red anywhere.
 *  - Reduced motion: no travelling lens, everything shown lit immediately. */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { check, type CheckResponse, type Lang, type QuoteResult, type Status } from "../api";
import { Icon, type BasiraIconName } from "../brand";
import { msg, ui } from "../i18n";
import hero from "../__generated__/hero.json";
import { useReducedMotion } from "./hooks";
import { A } from "./Shell";
import { numfmt, t } from "./strings";

const HERO = hero as unknown as { text: string; response: CheckResponse; recorded_at: string };

const ICON: Record<Status, BasiraIconName> = {
  found: "state-found",
  partial_match: "state-partial",
  needs_review: "state-review",
  not_found: "state-notfound",
};

interface Diff {
  start: number; // absolute offsets in the post text
  end: number;
  source: string; // verbatim corpus slice (source_text.slice(source_chars))
}
type Piece = { kind: "text"; text: string; key: string } | { kind: "quote"; key: string; q: QuoteResult; parts: { text: string; diff: Diff | null; key: string }[] };

function diffsOf(q: QuoteResult): Diff[] {
  const m = q.matches[0];
  if (!m) return [];
  const out: Diff[] = [];
  for (const o of m.diff) {
    if (o.op !== "replace") continue;
    const [a, b] = o.quote_chars;
    const [sa, sb] = o.source_chars;
    if (b <= a || sb <= sa) continue;
    out.push({ start: q.span.start + a, end: q.span.start + b, source: m.source_text.slice(sa, sb) });
  }
  return out;
}

/** Split the post into plain runs and quote runs; inside a quote, isolate the differing words. textContent === input. */
export function pieces(text: string, quotes: QuoteResult[]): Piece[] {
  const qs = [...quotes].sort((a, b) => a.span.start - b.span.start);
  const out: Piece[] = [];
  let i = 0;
  let k = 0;
  for (const q of qs) {
    const s = Math.max(i, q.span.start);
    const e = Math.min(text.length, q.span.end);
    if (e <= s) continue;
    if (s > i) out.push({ kind: "text", text: text.slice(i, s), key: `t${k++}` });
    const parts: { text: string; diff: Diff | null; key: string }[] = [];
    let j = s;
    for (const d of diffsOf(q).filter((d) => d.start >= s && d.end <= e).sort((a, b) => a.start - b.start)) {
      if (d.start < j) continue;
      if (d.start > j) parts.push({ text: text.slice(j, d.start), diff: null, key: `p${k++}` });
      parts.push({ text: text.slice(d.start, d.end), diff: d, key: `d${k++}` });
      j = d.end;
    }
    if (j < e) parts.push({ text: text.slice(j, e), diff: null, key: `p${k++}` });
    out.push({ kind: "quote", key: q.id, q, parts });
    i = e;
  }
  if (i < text.length) out.push({ kind: "text", text: text.slice(i), key: `t${k++}` });
  return out;
}

function refOf(q: QuoteResult, lang: Lang): string {
  const m = q.matches[0];
  if (!m) return "";
  return lang === "ar" ? m.ref_label_ar : m.ref_label_en;
}

export function LensDemo({ lang }: { lang: Lang }) {
  const reduced = useReducedMotion();
  const [data, setData] = useState<{ text: string; response: CheckResponse; live: boolean }>({ text: HERO.text, response: HERO.response, live: false });
  const [lit, setLit] = useState<number>(reduced ? 99 : -1); // how many quotes have been revealed
  const [lens, setLens] = useState<{ x: number; y: number; r: number; on: boolean }>({ x: 0, y: 0, r: 40, on: false });
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  const quoteEls = useRef<Map<string, HTMLElement>>(new Map());
  const order = useMemo(() => [...data.response.quotes].sort((a, b) => a.span.start - b.span.start), [data]);
  const ps = useMemo(() => pieces(data.text, data.response.quotes), [data]);
  const nf = numfmt(lang);

  const place = useCallback((idx: number) => {
    const q = order[idx];
    const host = stage.current;
    const el = q ? quoteEls.current.get(q.id) : undefined;
    if (!host || !el) return;
    const hb = host.getBoundingClientRect();
    const rects = Array.from(el.getClientRects());
    const r = rects[rects.length - 1] ?? el.getBoundingClientRect();
    const first = rects[0] ?? r;
    const cx = (first.left + first.right) / 2 - hb.left;
    const cy = (first.top + first.bottom) / 2 - hb.top;
    setLens({ x: cx, y: cy, r: Math.max(34, Math.min(90, first.height * 1.15)), on: true });
  }, [order]);

  // choreography
  useEffect(() => {
    if (reduced) {
      setLit(99);
      setLens((l) => ({ ...l, on: false }));
      return;
    }
    setLit(-1);
    const timers: ReturnType<typeof setTimeout>[] = [];
    const STEP = 950;
    const START = 650;
    order.forEach((_, i) => {
      timers.push(setTimeout(() => place(i), START + i * STEP));
      timers.push(setTimeout(() => setLit(i + 1), START + i * STEP + 420));
    });
    timers.push(setTimeout(() => setLens((l) => ({ ...l, on: false })), START + order.length * STEP + 300));
    return () => timers.forEach(clearTimeout);
  }, [order, place, reduced, run]);

  // keep the lens on its quote when the layout changes (resize / font swap)
  useLayoutEffect(() => {
    if (!lens.on) return;
    const on = () => place(Math.max(0, lit - 1));
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, [lens.on, lit, place]);

  const runLive = async () => {
    setBusy(true);
    try {
      const r = await check(data.text, lang);
      setData({ text: data.text, response: r, live: true });
      setRun((n) => n + 1);
    } catch {
      /* the recorded response stays on screen; the engine dot in the header shows availability */
    } finally {
      setBusy(false);
    }
  };

  const idxOf = (q: QuoteResult) => order.findIndex((x) => x.id === q.id);
  const tm = data.response.timings_ms;
  const done = lit >= order.length;

  return (
    <figure className="lens-demo" aria-label={t(lang, "demo_label")} data-done={done || undefined}>
      <div className="lens-demo__chrome" aria-hidden="true">
        <span />
        <span />
        <span />
        <b>{t(lang, "demo_post_title")}</b>
      </div>

      <div className="lens-stage" ref={stage}>
        <p className="lens-post" dir="rtl" lang="ar" data-testid="lens-post">
          {ps.map((p) =>
            p.kind === "text" ? (
              <span key={p.key}>{p.text}</span>
            ) : (
              <span
                key={p.key}
                ref={(el) => {
                  if (el) quoteEls.current.set(p.q.id, el);
                }}
                className="lens-q"
                data-status={p.q.status}
                data-lit={idxOf(p.q) < lit || undefined}
              >
                {p.parts.map((part) =>
                  part.diff ? (
                    <span key={part.key} className="lens-diff">
                      <span className="lens-diff__src" aria-hidden={idxOf(p.q) < lit ? undefined : true}>
                        <span className="sr-only">{t(lang, "demo_source_word")}: </span>
                        <span className="lens-diff__word" lang="ar">{part.diff.source}</span>
                      </span>
                      <mark className="lens-diff__mine">{part.text}</mark>
                    </span>
                  ) : (
                    <span key={part.key}>{part.text}</span>
                  ),
                )}
              </span>
            ),
          )}
        </p>
        <span
          className="lens-ring"
          aria-hidden="true"
          data-on={lens.on || undefined}
          style={{ transform: `translate3d(${lens.x}px, ${lens.y}px, 0)`, "--r": `${lens.r}px` } as React.CSSProperties}
        >
          <i />
        </span>
      </div>

      <div className="lens-pipe" aria-hidden={!done || undefined}>
        <span className="lens-pipe__step" data-on={lit >= 0 || undefined}>
          <span className="lens-pipe__dot lens-pipe__dot--ai" />
          <span>{t(lang, "demo_ai")}</span>
          <b>{t(lang, "demo_ms", { ms: nf.format(tm.extract) })}</b>
        </span>
        <span className="lens-pipe__line" data-on={lit >= 1 || undefined} />
        <span className="lens-pipe__step" data-on={done || undefined}>
          <span className="lens-pipe__dot lens-pipe__dot--engine" />
          <span>{t(lang, "demo_engine")}</span>
          <b>{t(lang, "demo_ms", { ms: nf.format(tm.match + tm.retrieve) })}</b>
        </span>
      </div>

      <ol className="lens-rail">
        {order.map((q, i) => (
          <li key={q.id} data-status={q.status} data-in={i < lit || undefined} style={{ "--i": i } as React.CSSProperties}>
            <span className="lens-rail__badge">
              <Icon name={ICON[q.status]} size={18} />
              {msg(lang, "labels", q.status)}
            </span>
            <span className="lens-rail__ref" dir="auto">
              {refOf(q, lang) || ui(lang, `kind_${q.kind}`)}
            </span>
          </li>
        ))}
      </ol>

      <figcaption className="lens-demo__foot">
        <span className="lens-demo__cap">
          <Icon name={data.live ? "health" : "byte-exact"} size={16} />
          {t(lang, data.live ? "demo_caption_live" : "demo_caption_recorded")}
        </span>
        <span className="lens-demo__actions">
          {!reduced && (
            <button type="button" className="chip-btn" onClick={() => setRun((n) => n + 1)}>
              <Icon name="deterministic" size={16} />
              {t(lang, "demo_replay")}
            </button>
          )}
          <button type="button" className="chip-btn" onClick={() => void runLive()} disabled={busy}>
            <Icon name={busy ? "spinner" : "check-run"} size={16} />
            {t(lang, busy ? "demo_running" : "demo_run_live")}
          </button>
          <A to="/check?example=example_mixed" className="chip-btn chip-btn--accent">
            {t(lang, "demo_open")}
          </A>
        </span>
      </figcaption>
    </figure>
  );
}
