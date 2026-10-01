import { useCallback, useEffect, useRef, useState } from "react";
import { BasiraError, checkImage, health, type CheckResponse, type Lang } from "./api";
import { Icon, LogoMark, type BasiraIconName } from "./brand";
import { ProgressiveStatus } from "./components/ProgressiveStatus";
import { ResultsView } from "./components/ResultsView";
import { SourcesFooter } from "./components/SourcesFooter";
import { MAX_CHARS, msg, ui } from "./i18n";
import { useProgressiveCheck } from "./useProgressiveCheck";

type HealthState = "ok" | "loading" | "down";
type Theme = "light" | "dark";

function useHealth(): [HealthState, Record<string, string> | null] {
  const [state, setState] = useState<HealthState>("loading");
  const [corpus, setCorpus] = useState<Record<string, string> | null>(null);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const h = await health();
        if (!alive) return;
        if (h.corpus_loaded) {
          setState("ok");
          setCorpus(h.corpus);
          return;
        }
        setState("loading");
      } catch {
        if (alive) setState("down");
      }
      timer = setTimeout(poll, 3000);
    };
    void poll();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, []);
  return [state, corpus];
}

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("basira.theme");
    if (saved === "light" || saved === "dark") return saved;
    const mq = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    return mq?.matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.dataset["theme"] = theme;
    localStorage.setItem("basira.theme", theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

export function buildReport(r: CheckResponse, lang: Lang): string {
  const lines = [`${ui(lang, "app_name")} — ${new Date().toISOString()}`, `request_id: ${r.request_id}`];
  if (r.determinism_hash) lines.push(`${ui(lang, "report_hash")}: ${r.determinism_hash}`);
  lines.push("");
  for (const q of r.quotes) {
    lines.push(`[${msg(lang, "labels", q.status)}] «${q.quoted_text}»`);
    for (const m of q.matches) lines.push(`  → ${lang === "ar" ? m.ref_label_ar : m.ref_label_en} — ${m.source_url}`);
    lines.push("");
  }
  lines.push(msg(lang, "fixed", "footer"));
  return lines.join("\n");
}

/** Example inputs — every one is verified live against the API in docs/manual-test (T-series).
 *  The texts are user-style inputs, not corpus text; the UI never shows corpus text here. */
const EXAMPLES: { key: string; icon: BasiraIconName; text: string }[] = [
  { key: "example_quran_ok", icon: "quran", text: "قال تعالى: ﴿إِنَّ مَعَ الْعُسْرِ يُسْرًا﴾" },
  { key: "example_quran_typo", icon: "diff-words", text: "قال تعالى: ﴿إن الله علي كل شيء قدير﴾" },
  { key: "example_hadith", icon: "hadith", text: "قال رسول الله ﷺ: «إنما الأعمال بالنيات» رواه البخاري" },
  {
    key: "example_mixed",
    icon: "paste-text",
    text: "قرأت اليوم: قال تعالى: ﴿وَقُل رَّبِّ زِدْنِي عِلْمًا﴾، وقال ﷺ: «طلب العلم فريضة على كل مسلم»، وقال تعالى: ﴿فاذكروني أذكركم﴾.",
  },
];

const PILLARS: { key: string; icon: BasiraIconName }[] = [
  { key: "pillar_byte_exact", icon: "byte-exact" },
  { key: "pillar_no_generation", icon: "no-generation" },
  { key: "pillar_no_judgment", icon: "no-judgment" },
  { key: "pillar_privacy", icon: "privacy-nostore" },
  { key: "pillar_deterministic", icon: "deterministic" },
];

export default function Check({ lang, onLang }: { lang: Lang; onLang: (l: Lang) => void }) {
  const [text, setText] = useState("");
  const [imageBusy, setImageBusy] = useState(false);
  const [checkedText, setCheckedText] = useState("");
  const [imageError, setImageError] = useState<string | null>(null);
  const [copied, setCopied] = useState<"report" | "share" | null>(null);
  const [printDate, setPrintDate] = useState("");
  const [sharedIn, setSharedIn] = useState(false);
  const [healthState, corpus] = useHealth();
  const [theme, toggleTheme] = useTheme();
  const abort = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const announced = useRef<"" | "rules" | "full">("");
  const [announce, setAnnounce] = useState("");

  const errorText = useCallback(
    (e: unknown) => {
      if (e instanceof BasiraError) {
        const b = e.body?.error;
        return b ? (lang === "ar" ? b.message_ar : b.message_en) : msg(lang, "errors", "internal");
      }
      return ui(lang, "error_network");
    },
    [lang],
  );
  const { state, run, reset, retry, setSingle } = useProgressiveCheck(lang, errorText);
  const result = state.result;
  const busy = imageBusy || state.phase === "rules" || state.phase === "full";
  const error = imageError ?? state.error;

  // E-046: a share link carries the TEXT in the URL fragment (never sent to the server). Intake only:
  // the user reviews and presses Check themselves — nothing runs because of a foreign URL.
  useEffect(() => {
    const h = window.location.hash;
    if (!h.startsWith("#t")) return;
    void import("./share").then(async ({ decodeShare }) => {
      const p = await decodeShare(h, MAX_CHARS);
      history.replaceState(null, "", window.location.pathname + window.location.search);
      if (!p) return;
      setText(p.text);
      setSharedIn(true);
      textareaRef.current?.focus();
    });
  }, []);

  // exactly two polite announcements per check: preliminary, final
  useEffect(() => {
    if (!result) {
      announced.current = "";
      return;
    }
    const n = result.quotes.length;
    if (state.isFinal && announced.current !== "full") {
      announced.current = "full";
      setAnnounce(ui(lang, "announce_final", { n }));
    } else if (!state.isFinal && announced.current === "") {
      announced.current = "rules";
      setAnnounce(ui(lang, "announce_preliminary", { n }));
    }
  }, [result, state.isFinal, lang]);

  // move focus to the results once per check (on whichever response paints first)
  const runNo = useRef(0);
  const focusedRun = useRef(0);
  useEffect(() => {
    if (!result || focusedRun.current === runNo.current) return;
    focusedRun.current = runNo.current;
    setTimeout(() => resultsRef.current?.focus(), 0);
  }, [result]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    abort.current?.abort();
    setImageError(null);
    setSharedIn(false);
    runNo.current += 1;
    setCheckedText(text);
    void run(text);
  };
  const onFile = (f: File | undefined) => {
    if (!f) return;
    reset();
    abort.current?.abort();
    const ac = new AbortController();
    abort.current = ac;
    setImageBusy(true);
    setImageError(null);
    setCheckedText("");
    runNo.current += 1;
    void checkImage(f, lang, ac.signal)
      .then((r) => {
        setCheckedText(r.ocr_text ?? "");
        setSingle(r);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setImageError(errorText(e));
      })
      .finally(() => setImageBusy(false));
  };
  const flash = (what: "report" | "share") => {
    setCopied(what);
    setTimeout(() => setCopied(null), 1500);
  };
  const onCopy = async () => {
    if (!result || !state.isFinal) return;
    await navigator.clipboard.writeText(buildReport(result, lang));
    flash("report");
  };
  const onShare = async () => {
    if (!state.isFinal || !checkedText) return;
    const { encodeShare } = await import("./share");
    const url = `${window.location.origin}${window.location.pathname}${await encodeShare({ text: checkedText, lang })}`;
    await navigator.clipboard.writeText(url);
    flash("share");
  };
  const onPrint = () => {
    setPrintDate(new Date().toISOString().slice(0, 10));
    // let React commit the header before the print dialog snapshots the page
    setTimeout(() => window.print(), 0);
  };
  const clearAll = () => {
    abort.current?.abort();
    reset();
    setText("");
    setCheckedText("");
    setImageError(null);
    setSharedIn(false);
  };
  const pickExample = (t: string) => {
    setText(t);
    reset();
    setImageError(null);
    textareaRef.current?.focus();
  };

  const n = result?.quotes.length ?? 0;
  const nf = new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en");
  const ready = healthState === "ok";
  const isFinal = state.isFinal;

  return (
    <div className="app">
      <a href="#results" className="skip-link">
        {ui(lang, "skip_to_results")}
      </a>

      <header className="topbar">
        <div className="container container--wide topbar__inner">
          <a className="brand" href="/">
            {/* decorative: the visible wordmark next to it is the link's accessible name */}
            <LogoMark size={40} title="" />
            <span className="brand__name">
              <strong>{ui(lang, "app_name")}</strong>
              <span lang="en">Basira</span>
            </span>
          </a>
          <div className="topbar__actions">
            <span className="health" data-state={healthState} aria-live="polite">
              <span className="health__label">
                {ui(lang, healthState === "ok" ? "status_ok" : healthState === "loading" ? "status_loading" : "status_down")}
              </span>
            </span>
            <button type="button" className="btn btn--ghost btn--icon" onClick={toggleTheme} aria-label={ui(lang, "theme_toggle")} aria-pressed={theme === "dark"}>
              <Icon name="theme" />
            </button>
            <button type="button" className="btn btn--ghost btn--sm btn--lang" lang={lang === "ar" ? "en" : "ar"} onClick={() => onLang(lang === "ar" ? "en" : "ar")}>
              <Icon name="language" size={18} />
              <span className="lang__label">{ui(lang, "lang_switch")}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="container">
        {!result && (
          <section className="hero" aria-labelledby="hero-h">
            <h1 id="hero-h">{ui(lang, "hero_title")}</h1>
            <p>{ui(lang, "hero_sub")}</p>
            <ul className="pillars">
              {PILLARS.map((p) => (
                <li key={p.key}>
                  <Icon name={p.icon} size={16} />
                  {ui(lang, p.key)}
                </li>
              ))}
            </ul>
          </section>
        )}

        <form className="card composer" onSubmit={onSubmit}>
          <div className="composer__label">
            <label htmlFor="text">{ui(lang, "input_label")}</label>
            <small>
              <kbd>Ctrl</kbd> + <kbd>↵</kbd> {ui(lang, "shortcut_hint")}
            </small>
          </div>
          <textarea
            id="text"
            ref={textareaRef}
            className="input"
            dir="auto"
            lang="ar"
            value={text}
            maxLength={MAX_CHARS}
            placeholder={ui(lang, "input_placeholder")}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === "Enter") onSubmit(e);
            }}
            aria-describedby="chars"
          />
          <div className="composer__row">
            <span id="chars" className="composer__meta">
              {ui(lang, "chars", { n: nf.format(text.length), max: nf.format(MAX_CHARS) })}
            </span>
            <div className="composer__actions">
              <label className="btn btn--ghost file-btn">
                <Icon name="upload-image" size={18} />
                {ui(lang, "upload_image")}
                <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => onFile(e.target.files?.[0])} disabled={busy || !ready} />
              </label>
              <button type="button" className="btn btn--ghost" onClick={clearAll} disabled={imageBusy || (!text && !result)}>
                <Icon name="clear" size={18} />
                {ui(lang, "clear")}
              </button>
              <button type="submit" className="btn btn--primary" disabled={busy || !text.trim() || !ready}>
                <Icon name={busy ? "spinner" : "check-run"} size={18} />
                {busy ? ui(lang, "checking") : ui(lang, "check")}
              </button>
            </div>
          </div>
        </form>

        {!result && !text && (
          <section className="examples" aria-labelledby="ex-h">
            <h2 id="ex-h" className="examples__title">
              {ui(lang, "examples_title")}
            </h2>
            <ul className="examples__list">
              {EXAMPLES.map((ex) => (
                <li key={ex.key}>
                  <button type="button" className="example" onClick={() => pickExample(ex.text)}>
                    <Icon name={ex.icon} size={20} />
                    <span className="example__text">
                      <small>{ui(lang, ex.key)}</small>
                      <span dir="rtl" lang="ar">
                        {ex.text}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {sharedIn && !result && (
          <div className="banner banner--info" role="status" dir="auto">
            <Icon name="info" size={18} />
            <span>{ui(lang, "shared_banner")}</span>
          </div>
        )}

        {error && (
          <div className="banner banner--error" role="alert" dir="auto">
            <Icon name="warning" size={18} />
            <span>{error}</span>
          </div>
        )}

        <ProgressiveStatus phase={state.phase} lang={lang} totalMs={result?.timings_ms.total} hash={result?.determinism_hash} onRetry={retry} />
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {announce}
        </div>

        <div id="results" ref={resultsRef} tabIndex={-1} className="results">
          {result && (
            <>
              <div className="summary">
                <span className="summary__stats">
                  <span>{n === 0 ? ui(lang, "no_quotes_title") : ui(lang, n === 1 ? "summary" : "summary_plural", { n: nf.format(n) })}</span>
                  <span>·</span>
                  <span>{ui(lang, "processing_time", { ms: nf.format(result.timings_ms.total) })}</span>
                </span>
                {n > 0 && (
                  <span className="summary__actions" title={isFinal ? undefined : ui(lang, "actions_wait_final")}>
                    <button type="button" className="btn btn--ghost btn--sm" onClick={() => void onCopy()} disabled={!isFinal}>
                      <Icon name={copied === "report" ? "state-found" : "copy"} size={16} />
                      {copied === "report" ? ui(lang, "copied") : ui(lang, "copy_report")}
                    </button>
                    <button type="button" className="btn btn--ghost btn--sm" onClick={() => void onShare()} disabled={!isFinal || !checkedText} title={ui(lang, "share_hint")}>
                      <Icon name={copied === "share" ? "state-found" : "source-link"} size={16} />
                      {copied === "share" ? ui(lang, "share_copied") : ui(lang, "share_link")}
                    </button>
                    <button type="button" className="btn btn--ghost btn--sm" onClick={onPrint} disabled={!isFinal}>
                      <Icon name="byte-exact" size={16} />
                      {ui(lang, "save_pdf")}
                    </button>
                  </span>
                )}
              </div>
              {(result.flags.refusal || result.flags.chain_message || result.flags.pii_suspected || result.extraction_degraded) && (
                <div className="banner banner--warn banner--stack" role="note">
                  {result.flags.refusal && <span dir="auto">{msg(lang, "notice", "refusal")}</span>}
                  {result.flags.chain_message && <span dir="auto">{msg(lang, "notice", "chain_message")}</span>}
                  {result.flags.pii_suspected && <span dir="auto">{msg(lang, "notice", "pii_suspected")}</span>}
                  {result.extraction_degraded && <span dir="auto">{msg(lang, "notice", "extraction_degraded")}</span>}
                </div>
              )}
              {result.ocr_text && (
                <section className="card card--pad ocr" aria-label={ui(lang, "ocr_title")}>
                  <h3>
                    <Icon name="ocr-scan" size={16} />
                    {ui(lang, "ocr_title")}
                  </h3>
                  <p className="diff-text" dir="auto" data-testid="ocr-text">
                    {result.ocr_text}
                  </p>
                </section>
              )}
              {n === 0 && isFinal && (
                // never say "no quotation" while the full stage may still add some
                <div className="banner banner--info" dir="auto">
                  <Icon name="info" size={18} />
                  <span>{msg(lang, "notice", "no_quotes")}</span>
                </div>
              )}
              {n > 0 && <ResultsView text={result.ocr_text ?? checkedText} result={result} lang={lang} changed={state.changed} ruleSpans={state.ruleSpans} />}
            </>
          )}
        </div>
      </main>

      {result && isFinal && (
        <div className="print-only print-header" aria-hidden="true">
          <h1>{ui(lang, "report_title")}</h1>
          <dl>
            <dt>{ui(lang, "report_date")}</dt>
            <dd>{printDate}</dd>
            <dt>{ui(lang, "report_request")}</dt>
            <dd>{result.request_id}</dd>
            <dt>{ui(lang, "report_corpus")}</dt>
            <dd>
              {Object.entries(result.corpus)
                .map(([k, v]) => `${k} ${v}`)
                .join(" · ")}
            </dd>
            {result.determinism_hash && (
              <>
                <dt>{ui(lang, "report_hash")}</dt>
                <dd>{result.determinism_hash}</dd>
              </>
            )}
          </dl>
        </div>
      )}
      <p className="print-only print-footer" aria-hidden="true">
        {msg(lang, "fixed", "footer")}
      </p>

      <SourcesFooter lang={lang} corpus={corpus} />
    </div>
  );
}
