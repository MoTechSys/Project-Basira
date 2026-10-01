import type { Lang, Match, QuoteResult } from "../api";
import { Icon } from "../brand";
import { has, msg, ui } from "../i18n";
import { DiffView } from "./DiffView";
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
  return v;
}

function MatchView({ m, q, lang }: { m: Match; q: QuoteResult; lang: Lang }) {
  const showDiff = m.source_text.length > 0 && (q.status !== "found" || m.diff.length > 0);
  return (
    <article className="match">
      <div className="match__ref">
        <span dir="auto" style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
          <Icon name={m.corpus === "tanzil" ? "quran" : "hadith"} size={20} />
          {refLabel(m, lang)}
        </span>
        <span className="tier">{ui(lang, `tier_${m.collection_tier}`)}</span>
      </div>
      {m.source_text.length > 0 &&
        (showDiff ? (
          <DiffView quote={q.quoted_text} source={m.source_text} sourceRange={m.source_text_range} diff={m.diff} lang={lang} />
        ) : (
          <p className="diff-text source-text" dir="rtl" lang="ar" data-testid="source-text">
            {m.source_text}
          </p>
        ))}
      {m.grade && (
        <p className="grade" dir="auto">
          {msg(lang, "notice", "grade_line", noticeVars("grade_line", q, lang))}
        </p>
      )}
      <div className="links" aria-label={ui(lang, "links")}>
        {m.links.map((l) => (
          <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer">
            <Icon name="source-link" size={16} />
            {l.name}
          </a>
        ))}
      </div>
    </article>
  );
}

export function QuoteCard({ q, lang }: { q: QuoteResult; lang: Lang }) {
  const notices = q.notice_keys.filter((k) => k !== "grade_line" && has(lang, "notice", k));
  return (
    <section className="card quote" data-status={q.status} aria-labelledby={`${q.id}-h`}>
      <div className="quote__head">
        <StatusBadge status={q.status} lang={lang} />
        <span className="kind">
          <Icon name={q.kind === "quran" ? "quran" : "hadith"} size={16} />
          {ui(lang, `kind_${q.kind}`)}
          {q.review_reason ? ` · ${ui(lang, "review_reason")}: ${ui(lang, `reason_${q.review_reason}`)}` : ""}
        </span>
      </div>
      <div className="quote__body">
        <h3 id={`${q.id}-h`} className="sr-only">
          {msg(lang, "labels", q.status)}
        </h3>
        <p className="quoted" dir="auto" data-testid="quoted-text">
          «{q.quoted_text}»
        </p>
        <p className="message" dir="auto">
          {msg(lang, "status", q.message_key, statusVars(q, lang))}
        </p>
        {notices.length > 0 && (
          <ul className="notices">
            {notices.map((k) => (
              <li key={k} dir="auto">
                <Icon name="info" size={16} />
                <span>{msg(lang, "notice", k, noticeVars(k, q, lang))}</span>
              </li>
            ))}
          </ul>
        )}
        {q.matches.map((m, i) => (
          <MatchView key={`${m.corpus}-${JSON.stringify(m.ref)}-${i}`} m={m} q={q} lang={lang} />
        ))}
        {q.external_search_links.length > 0 && (
          <div className="links">
            {q.external_search_links.map((l) => (
              <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer">
                <Icon name="search-external" size={16} />
                {l.name}
              </a>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
