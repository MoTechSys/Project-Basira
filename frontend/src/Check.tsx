import { useCallback, useEffect, useRef, useState } from "react";
import { BasiraError, check, checkImage, health, type CheckResponse, type Lang } from "./api";
import { Icon, LogoMark, type BasiraIconName } from "./brand";
import { QuoteCard } from "./components/QuoteCard";
import { SourcesFooter } from "./components/SourcesFooter";
import { MAX_CHARS, msg, ui } from "./i18n";

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
  const lines = [`${ui(lang, "app_name")} — ${new Date().toISOString()}`, `request_id: ${r.request_id}`, ""];
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
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [healthState, corpus] = useHealth();
  const [theme, toggleTheme] = useTheme();
  const abort = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const run = useCallback(
    async (fn: (signal: AbortSignal) => Promise<CheckResponse>) => {
      abort.current?.abort();
      const ac = new AbortController();
      abort.current = ac;
      setBusy(true);
      setError(null);
      try {
        const r = await fn(ac.signal);
        setResult(r);
        setTimeout(() => resultsRef.current?.focus(), 0);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        if (e instanceof BasiraError) {
          const b = e.body?.error;
          setError(b ? (lang === "ar" ? b.message_ar : b.message_en) : msg(lang, "errors", "internal"));
        } else {
          setError(ui(lang, "error_network"));
        }
      } finally {
        setBusy(false);
      }
    },
    [lang],
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    void run((signal) => check(text, lang, signal));
  };
  const onFile = (f: File | undefined) => {
    if (!f) return;
    void run((signal) => checkImage(f, lang, signal));
  };
  const onCopy = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(buildReport(result, lang));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const useExample = (t: string) => {
    setText(t);
    setResult(null);
    setError(null);
    textareaRef.current?.focus();
  };

  const n = result?.quotes.length ?? 0;
  const nf = new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en");
  const ready = healthState === "ok";

  return (
    <div className="app">
      <a href="#results" className="skip-link">
        {ui(lang, "skip_to_results")}
      </a>

      <header className="topbar">
        <div className="container container--wide topbar__inner">
          <a className="brand" href="/" aria-label={ui(lang, "app_name")}>
            <LogoMark size={40} />
            <span className="brand__name">
              <strong>{ui(lang, "app_name")}</strong>
              <span lang="en">Basira</span>
            </span>
          </a>
          <div className="topbar__actions">
            <span className="health" data-state={healthState} aria-live="polite">
              {ui(lang, healthState === "ok" ? "status_ok" : healthState === "loading" ? "status_loading" : "status_down")}
            </span>
            <button type="button" className="btn btn--ghost btn--icon" onClick={toggleTheme} aria-label={ui(lang, "theme_toggle")} aria-pressed={theme === "dark"}>
              <Icon name="theme" />
            </button>
            <button type="button" className="btn btn--ghost btn--sm" lang={lang === "ar" ? "en" : "ar"} onClick={() => onLang(lang === "ar" ? "en" : "ar")}>
              <Icon name="language" size={18} />
              {ui(lang, "lang_switch")}
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
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => {
                  setText("");
                  setResult(null);
                  setError(null);
                }}
                disabled={busy || (!text && !result)}
              >
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
                  <button type="button" className="example" onClick={() => useExample(ex.text)}>
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

        {error && (
          <div className="banner banner--error" role="alert" dir="auto">
            <Icon name="warning" size={18} />
            <span>{error}</span>
          </div>
        )}

        <div id="results" ref={resultsRef} tabIndex={-1} className="results" aria-live="polite">
          {result && (
            <>
              <div className="summary">
                <span className="summary__stats">
                  <span>{n === 0 ? ui(lang, "no_quotes_title") : ui(lang, n === 1 ? "summary" : "summary_plural", { n: nf.format(n) })}</span>
                  <span>·</span>
                  <span>{ui(lang, "processing_time", { ms: nf.format(result.timings_ms.total) })}</span>
                </span>
                {n > 0 && (
                  <button type="button" className="btn btn--ghost btn--sm" onClick={() => void onCopy()}>
                    <Icon name={copied ? "state-found" : "copy"} size={16} />
                    {copied ? ui(lang, "copied") : ui(lang, "copy_report")}
                  </button>
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
              {n === 0 && (
                <div className="banner banner--info" dir="auto">
                  <Icon name="info" size={18} />
                  <span>{msg(lang, "notice", "no_quotes")}</span>
                </div>
              )}
              {result.quotes.map((q) => (
                <QuoteCard key={q.id} q={q} lang={lang} />
              ))}
            </>
          )}
        </div>
      </main>

      <SourcesFooter lang={lang} corpus={corpus} />
    </div>
  );
}
