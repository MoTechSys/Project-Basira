/** «الأشعة» — the user's whole text, once, with every detected quotation marked in place by its status.
 *
 *  Why: a da'i checks a *post*, not a list of snippets. Seeing the post itself light up (green / amber /
 *  violet / grey) answers "is this post safe to forward?" in one glance, before reading any card.
 *
 *  Integrity rules:
 *  - only the USER's text is rendered here (never corpus text); nothing is rewritten — <mark>/<a> wrappers only;
 *  - colors carry no judgment on the text: they mirror the four matcher states, each with a text label for
 *    screen readers and color-blind users (WCAG 1.4.1), and a link to the full card;
 *  - attribution ("رواه البخاري") and isnad segments get a neutral underline, never a status color.
 */

import type { Lang, QuoteResult, Status } from "../api";
import { msg, ui } from "../i18n";
import { pieces } from "../lib/xray";

const ORDER: Status[] = ["found", "partial_match", "needs_review", "not_found"];

export function XRay({ text, quotes, lang }: { text: string; quotes: QuoteResult[]; lang: Lang }) {
  if (!text || quotes.length === 0) return null;
  const ps = pieces(text.length, quotes);
  const counts = ORDER.map((s) => [s, quotes.filter((q) => q.status === s).length] as const).filter(([, n]) => n > 0);
  return (
    <section className="card card--pad xray" aria-labelledby="xray-h">
      <div className="xray__head">
        <h2 id="xray-h">{ui(lang, "xray_title")}</h2>
        <ul className="xray__legend" aria-label={ui(lang, "xray_legend")}>
          {counts.map(([s, n]) => (
            <li key={s} data-status={s}>
              <span className="xray__dot" aria-hidden="true" />
              {msg(lang, "labels", s)} <b>{n}</b>
            </li>
          ))}
        </ul>
      </div>
      <p className="xray__text" dir="auto" lang="ar" data-testid="xray-text">
        {ps.map((p) => {
          const s = text.slice(p.start, p.end);
          if (p.role === "plain") return s;
          const q = quotes[p.q]!;
          if (p.role !== "quote") {
            return (
              <span key={`${p.start}`} className={`xray__ann xray__ann--${p.role}`}>
                {s}
              </span>
            );
          }
          return (
            <a
              key={`${p.start}`}
              href={`#${q.id}`}
              className="xray__q"
              data-status={q.status}
              aria-label={`${msg(lang, "labels", q.status)}: ${s}`}
              onClick={(e) => {
                const el = document.getElementById(q.id);
                if (!el) return;
                e.preventDefault();
                el.scrollIntoView({ behavior: "smooth", block: "start" });
                el.focus({ preventScroll: true });
              }}
            >
              {s}
              <sup className="xray__n" aria-hidden="true">
                {p.q + 1}
              </sup>
            </a>
          );
        })}
      </p>
      <p className="xray__hint">{ui(lang, "xray_hint")}</p>
    </section>
  );
}
