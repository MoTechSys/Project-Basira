import { useCallback, useEffect, useRef, useState } from "react";
import { BasiraError, checkImage, health, type CheckResponse, type Lang } from "./api";
import { AnnotatedText } from "./components/AnnotatedText";
import { ProgressiveStatus } from "./components/ProgressiveStatus";
import { QuoteCard } from "./components/QuoteCard";
import { SourcesFooter } from "./components/SourcesFooter";
import { MAX_CHARS, msg, ui } from "./i18n";
import { decodeShare, encodeShare } from "./share";
import { useProgressiveCheck } from "./useProgressiveCheck";

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

/** matchMedia hook without a library; SSR-safe default = compact (mobile-first). */
function useCompact(): boolean {
  const [compact, setCompact] = useState(() => (typeof matchMedia === "function" ? !matchMedia("(min-width: 960px)").matches : true));
  useEffect(() => {
    if (typeof matchMedia !== "function") return;
    const mq = matchMedia("(min-width: 960px)");
    const on = () => setCompact(!mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return compact;
}

export function buildReport(r: CheckResponse, lang: Lang): string {
  const lines = [`${ui(lang, "app_name")} — ${new Date().toISOString()}`, `request_id: ${r.request_id}`];
  if (r.determinism_hash) lines.push(`determinism_hash: ${r.determinism_hash}`);
  lines.push("");
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
  const [checkedText, setCheckedText] = useState<string | null>(null); // text the current result belongs to
  const [editing, setEditing] = useState(true);
  const [copied, setCopied] = useState<"" | "report" | "link">("");
  const [sharedBanner, setSharedBanner] = useState(false);
  const [imageResult, setImageResult] = useState<CheckResponse | null>(null);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [healthState, corpus] = useHealth();
  const compact = useCompact();
  const resultsRef = useRef<HTMLDivElement>(null);
  const liveRef = useRef<HTMLDivElement>(null);
  const imgAbort = useRef<AbortController | null>(null);

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
  const prog = useProgressiveCheck(lang, errorText);

  // Result in play: progressive (text) or image. Image checks are single-shot (OCR is the slow part).
  const result = imageResult ?? prog.state.result;
  const isFinal = imageResult ? true : prog.state.isFinal;
  const busy = imageBusy || prog.state.phase === "rules";
  const error = imageError ?? prog.state.error;

  // --- share link intake: show the text, never auto-check (spec §5-B)
  useEffect(() => {
    if (!location.hash.startsWith("#t")) return;
    void decodeShare(location.hash, MAX_CHARS).then((p) => {
      if (!p) return;
      setText(p.text);
      setSharedBanner(true);
      if (p.lang !== lang) onLang(p.lang);
      history.replaceState(null, "", location.pathname + location.search);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- live-region announcements: exactly one per phase change that matters
  useEffect(() => {
    const n = result?.quotes.length ?? 0;
    const nf = new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en");
    const el = liveRef.current;
    if (!el) return;
    if (prog.state.phase === "full" && result) el.textContent = `${ui(lang, "preliminary_note")} ${nf.format(n)}`;
    if ((prog.state.phase === "final" || prog.state.phase === "final_degraded") && result) {
      el.textContent = `${ui(lang, "final_note", { ms: nf.format(result.timings_ms.total) })} · ${nf.format(n)}`;
      setTimeout(() => resultsRef.current?.focus(), 0);
    }
  }, [prog.state.phase, result, lang]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setImageResult(null);
    setImageError(null);
    setSharedBanner(false);
    setCheckedText(text);
    setEditing(false);
    void prog.run(text);
  };
  const onFile = async (f: File | undefined) => {
    if (!f) return;
    prog.reset();
    imgAbort.current?.abort();
    const ac = new AbortController();
    imgAbort.current = ac;
    setImageBusy(true);
    setImageError(null);
    try {
      const r = await checkImage(f, lang, ac.signal);
      setImageResult(r);
      setCheckedText(r.ocr_text ?? "");
      setEditing(false);
      setTimeout(() => resultsRef.current?.focus(), 0);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setImageError(errorText(e));
    } finally {
      setImageBusy(false);
    }
  };
  const onClear = () => {
    prog.reset();
    imgAbort.current?.abort();
    setText("");
    setCheckedText(null);
    setImageResult(null);
    setImageError(null);
    setEditing(true);
    setSharedBanner(false);
  };
  const onEdit = () => {
    // Editing invalidates the result: drop it rather than show stale highlights (spec §1-A pitfall 7).
    prog.reset();
    setImageResult(null);
    setEditing(true);
    setTimeout(() => document.getElementById("text")?.focus(), 0);
  };
  const flash = (what: "report" | "link") => {
    setCopied(what);
    setTimeout(() => setCopied(""), 1500);
  };
  const onCopy = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(buildReport(result, lang));
    flash("report");
  };
  const onShare = async () => {
    const t = checkedText ?? text;
    if (!t.trim()) return;
    const hash = await encodeShare({ text: t, lang });
    await navigator.clipboard.writeText(`${location.origin}${location.pathname}${hash}`);
    flash("link");
  };

  const n = result?.quotes.length ?? 0;
  const nf = new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en");
  const ruleSpans = prog.state.ruleSpans;
  const showAnnotated = !editing && result !== null && checkedText !== null && n > 0;

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

      {/* print-only report header (print.css shows it) */}
      {result && (
        <div className="print-header" aria-hidden="true">
          <h1>{ui(lang, "report_title")}</h1>
          <dl>
            <dt>{ui(lang, "report_date")}</dt>
            <dd>{new Date().toISOString()}</dd>
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

      <main className={showAnnotated ? "results-grid" : undefined}>
        <div>
          <form className="card input-card" onSubmit={onSubmit}>
            <label htmlFor="text" style={showAnnotated ? { marginBlockEnd: 8 } : undefined}>
              {ui(lang, "input_label")}
            </label>
            {sharedBanner && (
              <div className="banner banner-info" role="status" dir="auto">
                {ui(lang, "shared_banner")}
              </div>
            )}
            {showAnnotated ? (
              <>
                <AnnotatedText text={checkedText!} quotes={result!.quotes} lang={lang} activeId={activeId} onActivate={setActiveId} />
                <div className="annotated-bar">
                  <button type="button" className="btn btn-ghost btn-sm" onClick={onEdit}>
                    {ui(lang, "edit_text")}
                  </button>
                  <div className="legend" aria-hidden="true">
                    <span data-status="found">{ui(lang, "legend_found")}</span>
                    <span data-status="partial_match">{ui(lang, "legend_partial")}</span>
                    <span data-status="needs_review">{ui(lang, "legend_review")}</span>
                    <span data-status="not_found">{ui(lang, "legend_notfound")}</span>
                  </div>
                </div>
              </>
            ) : (
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
            )}
            <div className="input-row">
              <span id="chars" className="meta">
                {ui(lang, "chars", { n: nf.format((showAnnotated ? checkedText! : text).length), max: nf.format(MAX_CHARS) })}
              </span>
              <div className="actions">
                <label className="btn btn-ghost file-btn">
                  {ui(lang, "upload_image")}
                  <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => void onFile(e.target.files?.[0])} disabled={busy || healthState !== "ok"} />
                </label>
                <button type="button" className="btn btn-ghost" onClick={onClear} disabled={busy || (!text && !result)}>
                  {ui(lang, "clear")}
                </button>
                <button type="submit" className="btn" disabled={busy || !text.trim() || healthState !== "ok" || !editing}>
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
          <ProgressiveStatus phase={imageResult ? "idle" : prog.state.phase} lang={lang} totalMs={result?.timings_ms.total} hash={result?.determinism_hash} onRetry={prog.retry} />
          <div ref={liveRef} className="sr-only" aria-live="polite" aria-atomic="true" />
        </div>

        <div id="results" ref={resultsRef} tabIndex={-1} className={"results results-col" + (isFinal ? " results-swap" : "")}>
          {result && (
            <>
              <div className="summary">
                <span>
                  {n === 0 ? ui(lang, "no_quotes_title") : ui(lang, n === 1 ? "summary" : "summary_plural", { n: nf.format(n) })} · {ui(lang, "processing_time", { ms: nf.format(result.timings_ms.total) })}
                </span>
                {n > 0 && (
                  <span className="actions">
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => void onCopy()} disabled={!isFinal} title={!isFinal ? ui(lang, "preliminary_note") : undefined}>
                      {copied === "report" ? ui(lang, "copied") : ui(lang, "copy_report")}
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => void onShare()} disabled={!isFinal} title={ui(lang, "share_hint")}>
                      {copied === "link" ? ui(lang, "share_copied") : ui(lang, "share_link")}
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => window.print()} disabled={!isFinal}>
                      {ui(lang, "save_pdf")}
                    </button>
                  </span>
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
              {result.ocr_text && (
                <section className="card" aria-label={ui(lang, "ocr_title")}>
                  <h3 style={{ margin: "0 0 6px", fontSize: 14, color: "var(--ink-soft)" }}>{ui(lang, "ocr_title")}</h3>
                  <p className="diff-text arabic" dir="auto" data-testid="ocr-text" style={{ margin: 0 }}>
                    {result.ocr_text}
                  </p>
                </section>
              )}
              {n === 0 && (
                <div className="banner banner-info" dir="auto">
                  {msg(lang, "notice", "no_quotes")}
                </div>
              )}
              {result.quotes.map((q) => (
                <QuoteCard
                  key={q.id}
                  q={q}
                  lang={lang}
                  compact={compact}
                  updated={prog.state.changed.has(q.id)}
                  addedByLlm={isFinal && !imageResult && ruleSpans.size > 0 && !ruleSpans.has(`${q.span.start}-${q.span.end}`)}
                  onFocusChange={setActiveId}
                />
              ))}
              {showAnnotated && (
                <a href="#annotated" className="btn btn-ghost btn-sm back-to-text">
                  {ui(lang, "back_to_text")}
                </a>
              )}
            </>
          )}
        </div>
      </main>

      <p className="print-footer" aria-hidden="true">
        {msg(lang, "fixed", "footer")}
      </p>
      <SourcesFooter lang={lang} corpus={corpus} />
    </div>
  );
}
