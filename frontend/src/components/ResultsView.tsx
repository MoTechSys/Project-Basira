/** Results workspace: the user's text with in-place highlights + a details panel.
 *  Desktop (≥ 960px): two columns, panel sticky. Mobile: highlights first, the selected quote's card
 *  slides up as a bottom sheet (role="dialog", Escape closes, focus moves in and back). */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CheckResponse, Lang, QuoteResult, Status } from "../api";
import { Icon, type BasiraIconName } from "../brand";
import { msg, ui } from "../i18n";
import { AnnotatedText } from "./AnnotatedText";
import { QuoteCard } from "./QuoteCard";

const ORDER: Status[] = ["needs_review", "partial_match", "not_found", "found"];
const ICON: Record<Status, BasiraIconName> = {
  found: "state-found",
  partial_match: "state-partial",
  needs_review: "state-review",
  not_found: "state-notfound",
};

function useIsDesktop(): boolean {
  const [d, setD] = useState(() => (typeof window.matchMedia === "function" ? window.matchMedia("(min-width: 960px)").matches : true));
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(min-width: 960px)");
    const on = (e: MediaQueryListEvent) => setD(e.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return d;
}

export function ResultsView({ text, result, lang }: { text: string; result: CheckResponse; lang: Lang }) {
  const quotes = result.quotes;
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState<Status | null>(null);
  const isDesktop = useIsDesktop();
  const sheetRef = useRef<HTMLDivElement>(null);
  const lastTrigger = useRef<HTMLElement | null>(null);
  const nf = new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en");

  const counts = useMemo(() => {
    const c: Record<Status, number> = { found: 0, partial_match: 0, needs_review: 0, not_found: 0 };
    for (const q of quotes) c[q.status]++;
    return c;
  }, [quotes]);

  // the first "attention" quote is pre-selected on desktop so the panel is never empty
  useEffect(() => {
    if (!isDesktop) return;
    if (selected && quotes.some((q) => q.id === selected)) return;
    const first = ORDER.map((s) => quotes.find((q) => q.status === s)).find(Boolean) ?? quotes[0];
    setSelected(first?.id ?? null);
  }, [quotes, isDesktop, selected]);

  const select = useCallback((id: string) => {
    lastTrigger.current = document.activeElement as HTMLElement | null;
    setSelected(id);
  }, []);
  const close = useCallback(() => {
    setSelected(null);
    lastTrigger.current?.focus();
  }, []);

  // bottom sheet: focus + Escape + body scroll lock
  useEffect(() => {
    if (isDesktop || !selected) return;
    const el = sheetRef.current;
    el?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener("keydown", onKey);
    };
  }, [isDesktop, selected, close]);

  const visible = filter ? quotes.filter((q) => q.status === filter) : quotes;
  // Spans are offsets into `text`; if none fits (defensive — e.g. a provider returned text that was
  // re-flowed) we never hide results: fall back to the plain card list.
  const placeable = quotes.some((q) => q.span.start < text.length && q.span.end > q.span.start);
  const current: QuoteResult | undefined = quotes.find((q) => q.id === selected);
  const idx = current ? quotes.indexOf(current) : -1;
  const go = (d: 1 | -1) => {
    const next = quotes[(idx + d + quotes.length) % quotes.length];
    if (next) setSelected(next.id);
  };

  if (!placeable) {
    return (
      <div className="results-list">
        {quotes.map((q) => (
          <QuoteCard key={q.id} q={q} lang={lang} />
        ))}
      </div>
    );
  }

  return (
    <div className="workspace" data-mode={isDesktop ? "split" : "stack"}>
      {/* status strip — doubles as filter and as an at-a-glance verdict */}
      <ul className="strip" aria-label={ui(lang, "strip_label")}>
        {ORDER.map((s) =>
          counts[s] ? (
            <li key={s}>
              <button type="button" className="chip" data-status={s} aria-pressed={filter === s} onClick={() => setFilter(filter === s ? null : s)}>
                <Icon name={ICON[s]} size={16} />
                <span>{msg(lang, "labels", s)}</span>
                <b>{nf.format(counts[s])}</b>
              </button>
            </li>
          ) : null,
        )}
      </ul>

      <div className="workspace__grid">
        <section className="card card--pad annotated-wrap" aria-labelledby="ann-h">
          <h3 id="ann-h" className="annotated__title">
            <Icon name="paste-text" size={16} />
            {ui(lang, "annotated_title")}
            <small>{ui(lang, "annotated_hint")}</small>
          </h3>
          <AnnotatedText text={text} quotes={visible} selected={selected} onSelect={select} lang={lang} />
          <ul className="legend" aria-hidden="true">
            {ORDER.filter((s) => counts[s]).map((s) => (
              <li key={s} data-status={s}>
                {msg(lang, "labels", s)}
              </li>
            ))}
          </ul>
        </section>

        {isDesktop ? (
          <aside className="panel" aria-label={ui(lang, "panel_label")}>
            {current ? (
              <>
                <div className="panel__nav">
                  <span>
                    {ui(lang, "panel_counter", { i: nf.format(idx + 1), n: nf.format(quotes.length) })}
                  </span>
                  <span className="panel__arrows">
                    <button type="button" className="btn btn--ghost btn--icon btn--sm" onClick={() => go(-1)} aria-label={ui(lang, "prev")}>
                      <Icon name="arrow-start" size={18} />
                    </button>
                    <button type="button" className="btn btn--ghost btn--icon btn--sm" onClick={() => go(1)} aria-label={ui(lang, "next")}>
                      <Icon name="arrow-start" size={18} className="flip-x" />
                    </button>
                  </span>
                </div>
                <QuoteCard key={current.id} q={current} lang={lang} />
              </>
            ) : (
              <p className="panel__empty">{ui(lang, "panel_empty")}</p>
            )}
          </aside>
        ) : (
          current && (
            <div className="sheet-backdrop" onClick={close}>
              <div
                ref={sheetRef}
                className="sheet"
                role="dialog"
                aria-modal="true"
                aria-label={ui(lang, "panel_label")}
                tabIndex={-1}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="sheet__bar">
                  <span className="sheet__grip" aria-hidden="true" />
                  <div className="panel__nav">
                    <span>{ui(lang, "panel_counter", { i: nf.format(idx + 1), n: nf.format(quotes.length) })}</span>
                    <span className="panel__arrows">
                      <button type="button" className="btn btn--ghost btn--icon btn--sm" onClick={() => go(-1)} aria-label={ui(lang, "prev")}>
                        <Icon name="arrow-start" size={18} />
                      </button>
                      <button type="button" className="btn btn--ghost btn--icon btn--sm" onClick={() => go(1)} aria-label={ui(lang, "next")}>
                        <Icon name="arrow-start" size={18} className="flip-x" />
                      </button>
                      <button type="button" className="btn btn--ghost btn--icon btn--sm" onClick={close} aria-label={ui(lang, "close")}>
                        <Icon name="close" size={18} />
                      </button>
                    </span>
                  </div>
                </div>
                <div className="sheet__body">
                  <QuoteCard key={current.id} q={current} lang={lang} />
                </div>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
