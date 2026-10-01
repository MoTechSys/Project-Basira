/** Long source text (ayah or hadith) that must NEVER be cut in the DOM (UX spec §3).
 *  - ≤ WORDS_FULL words: rendered plainly.
 *  - longer: the FULL text is always in the DOM (copy + screen reader get everything); only the
 *    visible box is clamped, with an explicit sentence "Full ayah (N words) — beginning shown".
 *  - when the matched range starts beyond the clamp, we show a window around the match with explicit
 *    word counters ("… 23 words before") as BUTTONS — never a bare ellipsis that could read as
 *    "the ayah is incomplete".
 *  Word counts are computed on `source_text.slice()` for display only; nothing is compared/normalised. */

import { useId, useState } from "react";
import type { Lang } from "../api";
import { ui } from "../i18n";
import { Highlighted } from "./DiffView";

export const WORDS_FULL = 25;
const CLAMP_LINES = 7; // ≈ 7.5lh in CSS
const WINDOW_CHARS = 160;

const words = (s: string): number => (s.trim() ? s.trim().split(/\s+/).length : 0);

export function AyahText({
  source,
  marks,
  matchRange,
  lang,
  isQuran,
}: {
  source: string;
  marks: [number, number][];
  matchRange: [number, number] | null;
  lang: Lang;
  isQuran: boolean;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const n = words(source);
  const dir = "rtl";
  if (n <= WORDS_FULL || open) {
    return (
      <div className="ayah">
        <p className="diff-text arabic" dir={dir} lang="ar" data-testid="source-text">
          <Highlighted text={source} marks={marks} cls="d-source" />
        </p>
        {n > WORDS_FULL && (
          <button type="button" className="btn btn-ghost btn-sm" aria-expanded="true" aria-controls={id} onClick={() => setOpen(false)}>
            {ui(lang, "hide_full_ayah")}
          </button>
        )}
      </div>
    );
  }

  // Decide: clamp from the start, or window around a far match.
  const farMatch = matchRange !== null && matchRange[0] > WINDOW_CHARS * 1.5;
  if (!farMatch) {
    return (
      <div className="ayah">
        <p className="ayah-note" dir="auto">
          {ui(lang, isQuran ? "ayah_full_note" : "ayah_full_note", { n })}
        </p>
        <div id={id} className="ayah-clamp" style={{ ["--clamp-lines" as string]: CLAMP_LINES }}>
          <p className="diff-text arabic" dir={dir} lang="ar" data-testid="source-text">
            <Highlighted text={source} marks={marks} cls="d-source" />
          </p>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" aria-expanded="false" aria-controls={id} onClick={() => setOpen(true)}>
          {ui(lang, "show_full_ayah")}
        </button>
      </div>
    );
  }

  const a = Math.max(0, matchRange![0] - WINDOW_CHARS / 2);
  const b = Math.min(source.length, matchRange![1] + WINDOW_CHARS / 2);
  const before = words(source.slice(0, a));
  const after = words(source.slice(b));
  return (
    <div className="ayah">
      <p className="ayah-note" dir="auto">
        {ui(lang, "ayah_full_note", { n })}
      </p>
      {/* Full text stays in the DOM for copy/AT; visually hidden. */}
      <p className="sr-only" lang="ar" data-testid="source-text-full">
        {source}
      </p>
      <p className="diff-text arabic ayah-window" dir={dir} lang="ar" aria-hidden="true" data-testid="source-text">
        {before > 0 && (
          <button type="button" className="word-counter" onClick={() => setOpen(true)} aria-label={ui(lang, "words_before", { n: before })}>
            {ui(lang, "words_before", { n: before })}
          </button>
        )}{" "}
        <Highlighted text={source.slice(a, b)} marks={marks} cls="d-source" offset={a} />{" "}
        {after > 0 && (
          <button type="button" className="word-counter" onClick={() => setOpen(true)} aria-label={ui(lang, "words_after", { n: after })}>
            {ui(lang, "words_after", { n: after })}
          </button>
        )}
      </p>
      <button type="button" className="btn btn-ghost btn-sm" aria-expanded="false" aria-controls={id} onClick={() => setOpen(true)}>
        {ui(lang, "show_full_ayah")}
      </button>
    </div>
  );
}
