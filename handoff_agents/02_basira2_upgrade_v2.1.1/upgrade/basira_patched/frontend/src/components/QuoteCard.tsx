import type { DiffOp, Lang, Match, QuoteResult } from "../api";
import { has, msg, ui } from "../i18n";
import { AyahText } from "./AyahText";
import { DiffView, Highlighted, ranges } from "./DiffView";
import { HarakatView } from "./HarakatView";
import { StatusBadge } from "./StatusBadge";

const BOOK_NAMES: Record<string, { ar: string; en: string }> = {
  "sahih_al-bukhari": { ar: "صحيح البخاري", en: "Sahih al-Bukhari" },
  sahih_muslim: { ar: "صحيح مسلم", en: "Sahih Muslim" },
  "sunan_abu-dawud": { ar: "سنن أبي داود", en: "Sunan Abu Dawud" },
  "sunan_al-tirmidhi": { ar: "سنن الترمذي", en: "Jami' al-Tirmidhi" },
  "sunan_al-nasai": { ar: "سنن النسائي", en: "Sunan al-Nasa'i" },
  "sunan_ibn-maja": { ar: "سنن ابن ماجه", en: "Sunan Ibn Majah" },
  maliks_muwataa: { ar: "موطأ مالك", en: "Muwatta Malik" },
  musnad_ahmad: { ar: "مسند أحمد", en: "Musnad Ahmad" },
  "sunan_al-darimi": { ar: "سنن الدارمي", en: "Sunan al-Darimi" },
};

function refLabel(m: Match, lang: Lang): string {
  return lang === "ar" ? m.ref_label_ar : m.ref_label_en;
}

function sourceName(m: Match, lang: Lang): string {
  if (m.corpus === "tanzil") return msg(lang, "labels", "source_quran");
  if (m.corpus === "hadeethenc") return ui(lang, "grade_source");
  const b = BOOK_NAMES[String(m.ref["book"])];
  return b ? b[lang] : String(m.ref["book"]);
}

/** Variables for message templates come ONLY from matcher/corpus fields. */
function statusVars(q: QuoteResult, lang: Lang): Record<string, string | number> {
  const m = q.matches[0];
  return {
    source_name: m ? sourceName(m, lang) : "",
    ref: m ? refLabel(m, lang) : "",
    count: q.total_positions,
    shown: q.matches.length,
    total: q.total_positions,
    n: q.quoted_text.trim().split(/\s+/).length,
  };
}

function noticeVars(key: string, q: QuoteResult, lang: Lang): Record<string, string | number> {
  const m = q.matches[0];
  const v: Record<string, string | number> = { ...statusVars(q, lang) };
  if (key === "claimed_source_mismatch") {
    const books = (q.claimed_source?.parsed as { books?: string[] } | undefined)?.books ?? [];
    v["found_in"] = m ? sourceName(m, lang) : "";
    v["claimed"] = books.map((b) => BOOK_NAMES[b]?.[lang] ?? b).join(lang === "ar" ? " و" : " & ") || (q.claimed_source?.raw ?? "");
  }
  if (key === "claimed_ayah_mismatch") {
    const p = q.claimed_source?.parsed as { surah?: number; ayah?: number; ayah_to?: number | null } | undefined;
    v["found_ref"] = m ? refLabel(m, lang) : "";
    v["claimed_ref"] = q.claimed_source?.raw ?? (p?.surah !== undefined ? `${p.surah}:${p.ayah}${p.ayah_to ? "-" + p.ayah_to : ""}` : "");
  }
  if (key === "arabic_text_at_ref") {
    const p = q.claimed_source?.parsed as { surah?: number; ayah?: number } | undefined;
    v["ref"] = p?.surah !== undefined ? `${p.surah}:${p.ayah}` : "";
  }
  if (key === "grade_line" && m?.grade) {
    v["grade_source"] = ui(lang, "grade_source");
    v["version"] = m.grade.version;
    v["grade_text"] = m.grade.text;
    v["takhrij"] = m.grade.takhrij;
  }
  if (key === "ohd_numbering" && m) v["num"] = String(m.ref["num"] ?? "");
  if (key === "spliced_quote") v["n"] = q.splice_parts?.length ?? 0;
  if (key === "harakat_conflict") v["n"] = q.matches.reduce((acc, mm) => acc + (mm.harakat_conflicts?.length ?? 0), 0);
  return v;
}

/** Safety-relevant notices stay visible even when the rest is folded. */
const ALWAYS_VISIBLE = new Set(["spliced_quote", "harakat_conflict", "claimed_source_mismatch", "claimed_ayah_mismatch", "attribution_quran_not_hadith", "attribution_hadith_not_quran", "image_unconfirmed"]);

function MatchView({ m, q, lang, compact }: { m: Match; q: QuoteResult; lang: Lang; compact: boolean }) {
  const hasDiff = m.diff.some((o) => o.op !== "equal");
  const showDiff = m.source_text.length > 0 && (q.status !== "found" || hasDiff);
  const isQuran = m.corpus === "tanzil";
  return (
    <article className="match">
      <div className="match-ref">
        <span dir="auto">{refLabel(m, lang)}</span>
        <span className="tier">{m.collection_tier}</span>
      </div>
      {m.source_text.length > 0 &&
        (showDiff && !compact ? (
          <DiffView quote={q.quoted_text} source={m.source_text} sourceRange={m.source_text_range} diff={m.diff} lang={lang} />
        ) : (
          /* compact (mobile / first screen): one column — the user's text is already visible above
             with its own diff marks; show the source with the match highlighted, never cut in DOM. */
          <AyahText source={m.source_text} marks={ranges(m.diff, "source")} matchRange={m.source_text_range} lang={lang} isQuran={isQuran} />
        ))}
      <HarakatView m={m} quote={q.quoted_text} lang={lang} />
      {m.grade && (
        <p className="grade" dir="auto">
          {msg(lang, "notice", "grade_line", noticeVars("grade_line", q, lang))}
        </p>
      )}
      <Links links={m.links} lang={lang} compact={compact} />
    </article>
  );
}

function Links({ links, lang, compact }: { links: { name: string; url: string }[]; lang: Lang; compact: boolean }) {
  if (links.length === 0) return null;
  const [first, ...rest] = links;
  const A = (l: { name: string; url: string }) => (
    <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer">
      {l.name}
    </a>
  );
  if (!compact || rest.length === 0)
    return (
      <div className="links" aria-label={ui(lang, "links")}>
        {links.map(A)}
      </div>
    );
  return (
    <div className="links" aria-label={ui(lang, "links")}>
      {A(first!)}
      <details className="fold">
        <summary>{ui(lang, "details_more_links")}</summary>
        <div className="links">{rest.map(A)}</div>
      </details>
    </div>
  );
}

export function QuoteCard({
  q,
  lang,
  compact = false,
  updated = false,
  addedByLlm = false,
  onFocusChange,
}: {
  q: QuoteResult;
  lang: Lang;
  /** mobile / one-screen layout: fold notices, extra positions, extra links; single-column source */
  compact?: boolean;
  /** status changed between preliminary and final result (brief tag) */
  updated?: boolean;
  /** span came from the implicit-analysis stage (not from deterministic rules) */
  addedByLlm?: boolean;
  onFocusChange?: (id: string | null) => void;
}) {
  const all = q.notice_keys.filter((k) => k !== "grade_line" && has(lang, "notice", k));
  const pinned = all.filter((k) => ALWAYS_VISIBLE.has(k));
  const foldable = compact ? all.filter((k) => !ALWAYS_VISIBLE.has(k)) : [];
  const shown = compact ? pinned : all;
  const [m0, ...more] = q.matches;
  const quoteMarks: [number, number][] = m0 ? ranges(m0.diff as DiffOp[], "quote") : [];
  const repeats = q.repeated_spans?.length ?? 0;
  return (
    <section
      id={q.id}
      tabIndex={-1}
      className="card quote-card"
      data-status={q.status}
      data-compact={compact ? "" : undefined}
      aria-labelledby={`${q.id}-h`}
      onFocus={() => onFocusChange?.(q.id)}
      onBlur={() => onFocusChange?.(null)}
    >
      <div className="quote-head">
        <StatusBadge status={q.status} lang={lang} />
        <span className="kind" title={q.kind}>
          {q.review_reason ? `${ui(lang, "review_reason")}: ${ui(lang, `reason_${q.review_reason}`)}` : compact ? "" : q.kind}
          {updated && <span className="tag tag-updated">{ui(lang, "updated_tag")}</span>}
          {addedByLlm && <span className="tag tag-llm">{ui(lang, "added_by_llm")}</span>}
          {repeats > 0 && (
            <span className="tag tag-repeat" title={msg(lang, "notice", "repeated_in_text")}>
              ×{repeats + 1}
            </span>
          )}
        </span>
      </div>
      <h3 id={`${q.id}-h`} className="sr-only">
        {msg(lang, "labels", q.status)}
      </h3>
      <p className={"quoted arabic" + (compact ? " clamp-3" : "")} dir="auto" data-testid="quoted-text">
        «<Highlighted text={q.quoted_text} marks={quoteMarks} cls="d-quote" />»
      </p>
      <p className="message" dir="auto">
        {msg(lang, "status", q.message_key, statusVars(q, lang))}
      </p>
      {shown.length > 0 && (
        <ul className="notices">
          {shown.map((k) => (
            <li key={k} dir="auto">
              {msg(lang, "notice", k, noticeVars(k, q, lang))}
            </li>
          ))}
        </ul>
      )}
      {foldable.length > 0 && (
        <details className="fold">
          <summary>{ui(lang, "details_notices", { n: foldable.length })}</summary>
          <ul className="notices">
            {foldable.map((k) => (
              <li key={k} dir="auto">
                {msg(lang, "notice", k, noticeVars(k, q, lang))}
              </li>
            ))}
          </ul>
        </details>
      )}
      {(q.splice_parts?.length ?? 0) > 0 && (
        <ul className="splice" data-testid="splice-parts">
          {q.splice_parts!.map((p, i) => (
            <li key={i} dir="auto">
              <span className="arabic" lang="ar">«{q.quoted_text.slice(p.chars[0], p.chars[1])}»</span> — {lang === "ar" ? p.ref_label_ar : p.ref_label_en}
            </li>
          ))}
        </ul>
      )}
      {m0 && <MatchView m={m0} q={q} lang={lang} compact={compact} />}
      {more.length > 0 &&
        (compact ? (
          <details className="fold">
            <summary>{ui(lang, "details_more_positions", { n: more.length })}</summary>
            {more.map((m, i) => (
              <MatchView key={`${m.corpus}-${JSON.stringify(m.ref)}-${i}`} m={m} q={q} lang={lang} compact={compact} />
            ))}
          </details>
        ) : (
          more.map((m, i) => <MatchView key={`${m.corpus}-${JSON.stringify(m.ref)}-${i}`} m={m} q={q} lang={lang} compact={compact} />)
        ))}
      {q.external_search_links.length > 0 && <Links links={q.external_search_links} lang={lang} compact={compact} />}
    </section>
  );
}
