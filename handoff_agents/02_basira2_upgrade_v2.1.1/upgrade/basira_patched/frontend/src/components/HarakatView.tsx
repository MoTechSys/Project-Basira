/** E-037 — show WHERE a vowel mark in the user's quote contradicts the Mushaf.
 *
 *  Two lines, both verbatim: the user's quote and the vocalized Mushaf window (Tanzil Simple,
 *  Ḥafṣ). The conflicting letter (+ its marks) is wrapped in <mark class="d-haraka"> on both lines,
 *  with an accessible name that spells the marks («ضمة ← فتحة»). Font size is bumped so the marks
 *  are legible — the whole point is the tiny glyph above/below the letter.
 *
 *  Nothing is re-ordered or normalised: slices only, same guarantee as DiffView. */

import type { HarakatConflict, Lang, Match } from "../api";
import { ui } from "../i18n";
import { Highlighted } from "./DiffView";

const marksLabel = (lang: Lang, marks: string[]): string => marks.map((m) => ui(lang, `mark_${m}`)).join(" + ");

export function HarakatView({ m, quote, lang }: { m: Match; quote: string; lang: Lang }) {
  const conflicts = m.harakat_conflicts ?? [];
  if (m.harakat_verdict !== "conflict" || conflicts.length === 0 || !m.harakat_reference) return null;
  const ref = m.harakat_reference;
  const rng = m.harakat_reference_range ?? [0, ref.length];
  const qMarks: [number, number][] = conflicts.map((c) => c.quote_chars);
  const rMarks: [number, number][] = conflicts.map((c) => c.reference_chars);
  return (
    <section className="harakat" aria-label={ui(lang, "harakat_title")} data-testid="harakat-view">
      <h4>{ui(lang, "harakat_title")}</h4>
      <div className="harakat-row">
        <span className="harakat-label">{ui(lang, "harakat_yours")}</span>
        <p className="diff-text arabic harakat-text" dir="rtl" lang="ar" data-testid="harakat-quote">
          <Highlighted text={quote} marks={qMarks} cls="d-haraka" />
        </p>
      </div>
      <div className="harakat-row">
        <span className="harakat-label">{ui(lang, "harakat_mushaf")}</span>
        <p className="diff-text arabic harakat-text" dir="rtl" lang="ar" data-testid="harakat-ref">
          <Highlighted text={ref.slice(rng[0], rng[1])} marks={rMarks} cls="d-haraka" offset={rng[0]} />
        </p>
      </div>
      <ul className="harakat-list">
        {conflicts.map((c: HarakatConflict, i) => (
          <li key={i} dir="auto">
            <span className="arabic" lang="ar">
              {quote.slice(c.quote_chars[0], c.quote_chars[1])}
            </span>
            {" — "}
            <span>{marksLabel(lang, c.quote_marks)}</span>
            {" ← "}
            <span className="arabic" lang="ar">
              {ref.slice(c.reference_chars[0], c.reference_chars[1])}
            </span>{" "}
            <span>{marksLabel(lang, c.reference_marks)}</span>
          </li>
        ))}
      </ul>
      <p className="diff-legend">{ui(lang, "harakat_legend")}</p>
    </section>
  );
}
