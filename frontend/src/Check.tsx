import { useCallback, useEffect, useRef, useState } from "react";
import { BasiraError, check, checkImage, health, type CheckResponse, type Lang } from "./api";
import { QuoteCard } from "./components/QuoteCard";
import { SourcesFooter } from "./components/SourcesFooter";
import { MAX_CHARS, msg, ui } from "./i18n";

type HealthState = "ok" | "loading" | "down";

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

export default function Check({ lang, onLang }: { lang: Lang; onLang: (l: Lang) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [healthState, corpus] = useHealth();
  const abort = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

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

  const n = result?.quotes.length ?? 0;
  const nf = new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en");

  return (
    <div className="app">
      <a href="#results" className="skip-link">
        {ui(lang, "skip_to_results")}
      </a>
      <header className="header">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            ب
          </div>
          <div>
            <h1>{ui(lang, "app_name")}</h1>
            <p>{ui(lang, "tagline")}</p>
          </div>
        </div>
        <div className="header-actions">
          <span className="health" data-state={healthState} aria-live="polite">
            {ui(lang, healthState === "ok" ? "status_ok" : healthState === "loading" ? "status_loading" : "status_down")}
          </span>
          <button type="button" className="btn btn-ghost btn-sm" lang={lang === "ar" ? "en" : "ar"} onClick={() => onLang(lang === "ar" ? "en" : "ar")}>
            {ui(lang, "lang_switch")}
          </button>
        </div>
      </header>

      <main>
        <form className="card input-card" onSubmit={onSubmit}>
          <label htmlFor="text">{ui(lang, "input_label")}</label>
          <textarea
            id="text"
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
          <div className="input-row">
            <span id="chars" className="meta">
              {ui(lang, "chars", { n: nf.format(text.length), max: nf.format(MAX_CHARS) })}
            </span>
            <div className="actions">
              <label className="btn btn-ghost file-btn">
                {ui(lang, "upload_image")}
                <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => onFile(e.target.files?.[0])} disabled={busy || healthState !== "ok"} />
              </label>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  setText("");
                  setResult(null);
                  setError(null);
                }}
                disabled={busy || (!text && !result)}
              >
                {ui(lang, "clear")}
              </button>
              <button type="submit" className="btn" disabled={busy || !text.trim() || healthState !== "ok"}>
                {busy ? ui(lang, "checking") : ui(lang, "check")}
              </button>
            </div>
          </div>
        </form>

        {error && (
          <div className="banner banner-error" role="alert" dir="auto">
            {error}
          </div>
        )}

        <div id="results" ref={resultsRef} tabIndex={-1} className="results" aria-live="polite">
          {result && (
            <>
              <div className="summary">
                <span>
                  {n === 0 ? ui(lang, "no_quotes_title") : ui(lang, n === 1 ? "summary" : "summary_plural", { n: nf.format(n) })} · {ui(lang, "processing_time", { ms: nf.format(result.timings_ms.total) })}
                </span>
                {n > 0 && (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => void onCopy()}>
                    {copied ? ui(lang, "copied") : ui(lang, "copy_report")}
                  </button>
                )}
              </div>
              {(result.flags.refusal || result.flags.chain_message || result.flags.pii_suspected || result.extraction_degraded) && (
                <div className="banner banner-warn flags" role="note">
                  {result.flags.refusal && <span dir="auto">{msg(lang, "notice", "refusal")}</span>}
                  {result.flags.chain_message && <span dir="auto">{msg(lang, "notice", "chain_message")}</span>}
                  {result.flags.pii_suspected && <span dir="auto">{msg(lang, "notice", "pii_suspected")}</span>}
                  {result.extraction_degraded && <span dir="auto">{msg(lang, "notice", "extraction_degraded")}</span>}
                </div>
              )}
              {n === 0 && (
                <div className="banner banner-info" dir="auto">
                  {msg(lang, "notice", "no_quotes")}
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
