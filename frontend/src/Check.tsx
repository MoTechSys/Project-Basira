/** مساحة التحقق — the workspace. Same engine contract as before (E-042 results workspace is reused as-is);
 *  new: mode tabs (text, image, English, Guard — all on the live engine; E-048/E-049/E-052), generated examples
 *  (from eval/cases.yaml + smoke), and a «what happened» strip that makes the AI's role and the engine's
 *  role visible for every real response. */

import { useCallback, useEffect, useRef, useState } from "react";
import { BasiraError, check, checkImage, guard, receipt, receiptUrl, type CheckResponse, type GuardResponse, type Lang, type Receipt } from "./api";
import { Icon, type BasiraIconName } from "./brand";
import { ResultsView } from "./components/ResultsView";
import { MAX_CHARS, msg, ui } from "./i18n";
import examples from "./__generated__/examples.json";
import { useHealth } from "./site/hooks";
import { numfmt, t, type SiteKey } from "./site/strings";

type Mode = "text" | "image" | "english" | "guard";
const MODES: { id: Mode; key: SiteKey; icon: BasiraIconName; live: boolean }[] = [
  { id: "text", key: "mode_text", icon: "paste-text", live: true },
  { id: "image", key: "mode_image", icon: "ocr-scan", live: true },
  { id: "english", key: "mode_en", icon: "language", live: true },
  { id: "guard", key: "mode_guard", icon: "shield-verify", live: true },
];

export const EXAMPLES = (examples as { items: { key: string; icon: BasiraIconName; text: string; provenance: string }[] }).items;

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

function Pipeline({ r, lang, text }: { r: CheckResponse; lang: Lang; text: string }) {
  const nf = numfmt(lang);
  const ai = r.extraction_provider.startsWith("mock") ? null : r.extraction_provider.split(":").pop();
  return (
    <section className="pipe" aria-labelledby="pipe-h">
      <h2 id="pipe-h" className="pipe__title">{t(lang, "pipe_title")}</h2>
      <ol className="pipe__steps">
        <li data-kind="ai">
          <span className="pipe__dot" aria-hidden="true" />
          <span className="pipe__name">{t(lang, "pipe_ai")}</span>
          <span className="pipe__desc">
            {r.extraction_degraded || !ai ? t(lang, "pipe_degraded") : t(lang, "pipe_ai_d")}
            {ai && <code dir="ltr">{ai}</code>}
          </span>
          <b dir="ltr">{nf.format(r.timings_ms.extract)} ms</b>
        </li>
        <li data-kind="engine">
          <span className="pipe__dot" aria-hidden="true" />
          <span className="pipe__name">{t(lang, "pipe_engine")}</span>
          <span className="pipe__desc">{t(lang, "pipe_engine_d")}</span>
          <b dir="ltr">{nf.format(r.timings_ms.match + r.timings_ms.retrieve)} ms</b>
        </li>
        <li data-kind="validator">
          <span className="pipe__dot" aria-hidden="true" />
          <span className="pipe__name">{t(lang, "pipe_validator")}</span>
          <span className="pipe__desc">{t(lang, "pipe_validator_d", { n: nf.format(r.validator_rejections) })}</span>
        </li>
      </ol>
      <p className="pipe__corpus">
        <span>{t(lang, "pipe_corpus")}:</span>
        {Object.entries(r.corpus).map(([k, v]) => (
          <code key={k} dir="ltr">
            {k} {v}
          </code>
        ))}
      </p>
      <ReceiptBox lang={lang} text={text} />
    </section>
  );
}


function ReceiptBox({ lang, text }: { lang: Lang; text: string }) {
  const [rc, setRc] = useState<Receipt | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState(false);
  useEffect(() => {
    setRc(null);
    setErr(false);
  }, [text]);
  if (!text.trim()) return null;
  const make = async () => {
    setBusy(true);
    setErr(false);
    try {
      setRc(await receipt(text, lang));
    } catch {
      setErr(true);
    } finally {
      setBusy(false);
    }
  };
  const copy = async () => {
    if (!rc) return;
    await navigator.clipboard.writeText(receiptUrl(rc));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="pipe__receipt" data-testid="receipt-box">
      {!rc && (
        <button type="button" className="btn-ghost-lux" onClick={() => void make()} disabled={busy}>
          <Icon name="share-link" size={16} />
          {busy ? t(lang, "receipt_making") : t(lang, "receipt_make")}
        </button>
      )}
      {err && <span className="set-fail">{ui(lang, "error_network")}</span>}
      {rc && (
        <>
          <span dir="auto">
            {t(lang, "receipt_ready", { id: rc.receipt_id })}
          </span>
          <button type="button" className="btn-ghost-lux" onClick={() => void copy()}>
            <Icon name={copied ? "state-found" : "copy"} size={16} />
            {copied ? t(lang, "receipt_copied") : t(lang, "receipt_copy")}
          </button>
          <a className="btn-ghost-lux" href={receiptUrl(rc)} target="_blank" rel="noopener noreferrer">
            <Icon name="source-link" size={16} />
            {t(lang, "receipt_open")}
          </a>
        </>
      )}
    </div>
  );
}

function GuardPanel({ g, lang }: { g: GuardResponse; lang: Lang }) {
  const nf = numfmt(lang);
  const tone = g.verdict === "clear" ? "found" : g.verdict === "flagged" ? "needs_review" : "not_found";
  return (
    <section className="card card--pad guard-panel" data-verdict={g.verdict} aria-live="polite" data-testid="guard-panel">
      <h3 className={`state-${tone === "found" ? "found" : tone === "needs_review" ? "review" : "notfound"}`}>
        <Icon name={tone === "found" ? "state-found" : tone === "needs_review" ? "state-partial" : "state-notfound"} size={18} />
        {t(lang, g.verdict === "clear" ? "guard_clear" : g.verdict === "flagged" ? "guard_flagged" : "guard_none")}
      </h3>
      <p dir="auto">{lang === "ar" ? g.summary_ar : g.summary_en}</p>
      {g.quotes.length > 0 && (
        <ol className="guard-list">
          {g.quotes.map((q) => (
            <li key={q.id} data-flagged={g.flagged_quote_ids.includes(q.id) || undefined}>
              <span className={`badge state-${q.status === "found" ? "found" : q.status === "partial_match" ? "partial" : q.status === "needs_review" ? "review" : "notfound"}`}>
                {msg(lang, "labels", q.status)}
              </span>{" "}
              <span dir="auto">«{q.quoted_text}»</span>
            </li>
          ))}
        </ol>
      )}
      <p className="pipe__corpus">
        <span>{t(lang, "pipe_corpus")}:</span>
        {Object.entries(g.corpus).map(([k, v]) => (
          <code key={k} dir="ltr">
            {k} {v}
          </code>
        ))}
        <code dir="ltr">{nf.format(g.counts.quotes)} · {g.determinism_hash.slice(0, 12)}…</code>
      </p>
    </section>
  );
}

function initialMode(): Mode {
  const m = new URLSearchParams(location.search).get("mode");
  return m === "image" || m === "english" || m === "guard" ? m : "text";
}
/** Text to pre-fill from the URL. `?text=` (deep link from the Telegram bot, E-063) wins over `?example=`.
 *  Pre-fill only — the user presses the button; nothing is checked on page load. Capped at MAX_CHARS. */
export function initialTextFrom(search: string): string {
  const p = new URLSearchParams(search);
  const t = p.get("text");
  if (t !== null) return t.slice(0, MAX_CHARS);
  const k = p.get("example");
  return EXAMPLES.find((e) => e.key === k)?.text ?? "";
}
function initialText(): string {
  return initialTextFrom(location.search);
}

export default function Check({ lang }: { lang: Lang; onLang?: (l: Lang) => void }) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [text, setText] = useState(initialText);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CheckResponse | null>(null);
  const [guardResult, setGuardResult] = useState<GuardResponse | null>(null);
  const [checkedText, setCheckedText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [drag, setDrag] = useState(false);
  const { state: healthState } = useHealth();
  const abort = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  // Set when a check finishes; consumed by the effect below once React has painted the results.
  const revealPending = useRef(false);
  const errorRef = useRef<HTMLDivElement>(null);

  /** Bring the results into view after a check (E-UX-01).
   *  Why an effect and not `setTimeout(focus, 0)`: the timeout fired before React committed the
   *  results, so `#results` was still empty (0px tall, measured) and `focus()` silently failed —
   *  on phones the result rendered below the fold and nothing told the user it had arrived.
   *  Runs after commit, so the node has its content. `preventScroll` + an explicit scroll lets the
   *  sticky top bar be compensated by CSS `scroll-margin-top`; reduced-motion users get no animation. */
  useEffect(() => {
    if (!revealPending.current || (!result && !guardResult && !error)) return;
    revealPending.current = false;
    // an error has no results region content: reveal the alert banner instead
    const el = result || guardResult ? resultsRef.current : errorRef.current;
    if (!el) return;
    el.focus({ preventScroll: true });
    const reduce = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView?.({ block: "start", behavior: reduce ? "auto" : "smooth" });
  }, [result, guardResult, error]);

  useEffect(() => {
    const u = new URL(location.href);
    if (mode === "text") u.searchParams.delete("mode");
    else u.searchParams.set("mode", mode);
    u.searchParams.delete("example");
    u.searchParams.delete("text"); // consumed into the composer; a reload must not resurrect it over the user's edits
    history.replaceState(null, "", u.pathname + u.search);
  }, [mode]);

  const run = useCallback(
    async (fn: (signal: AbortSignal) => Promise<CheckResponse>) => {
      abort.current?.abort();
      const ac = new AbortController();
      abort.current = ac;
      setBusy(true);
      setError(null);
      // E-UX-03: a new check invalidates the previous report — never show an error above stale results.
      setResult(null);
      try {
        const r = await fn(ac.signal);
        revealPending.current = true;
        setResult(r);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        if (e instanceof BasiraError) {
          const b = e.body?.error;
          setError(b ? (lang === "ar" ? b.message_ar : b.message_en) : msg(lang, "errors", "internal"));
        } else {
          setError(ui(lang, "error_network"));
        }
        revealPending.current = true;
      } finally {
        setBusy(false);
      }
    },
    [lang],
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setCheckedText(text);
    if (mode === "guard") {
      abort.current?.abort();
      const ac = new AbortController();
      abort.current = ac;
      setBusy(true);
      setError(null);
      setResult(null);
      void guard(text, lang, ac.signal)
        .then((g) => {
          revealPending.current = true;
          setGuardResult(g);
        })
        .catch((err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          if (err instanceof BasiraError) {
            const b = err.body?.error;
            setError(b ? (lang === "ar" ? b.message_ar : b.message_en) : msg(lang, "errors", "internal"));
          } else setError(ui(lang, "error_network"));
        })
        .finally(() => setBusy(false));
      return;
    }
    setGuardResult(null);
    void run((signal) => check(text, lang, signal));
  };
  const onFile = (f: File | undefined) => {
    if (!f) return;
    setCheckedText("");
    void run((signal) => checkImage(f, lang, signal));
  };
  const onCopy = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(buildReport(result, lang));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const pickExample = (s: string) => {
    setMode("text");
    setText(s);
    setResult(null);
    setError(null);
    textareaRef.current?.focus();
  };

  const n = result?.quotes.length ?? 0;
  const nf = numfmt(lang);
  const ready = healthState === "ok";

  return (
    <main id="main" className="page page--check">
      <header className="page-head page-head--tight">
        <div className="wrap">
          <h1>{t(lang, "check_title")}</h1>
          <p>{t(lang, "check_sub")}</p>
        </div>
      </header>

      <div className="wrap ws">
        <div className="ws-modes" role="tablist" aria-label={t(lang, "modes_label")}>
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              role="tab"
              id={`tab-${m.id}`}
              aria-selected={mode === m.id}
              aria-controls="ws-panel"
              className="ws-mode"
              onClick={() => setMode(m.id)}
            >
              <Icon name={m.icon} size={18} />
              <span>{t(lang, m.key)}</span>
            </button>
          ))}
        </div>

        <div id="ws-panel" role="tabpanel" aria-labelledby={`tab-${mode}`} className="ws-panel">
          {(mode === "text" || mode === "english" || mode === "guard") && (
            <form className="composer-lux" onSubmit={onSubmit}>
              {mode !== "text" && (
                <p className="ws-hint" dir="auto">
                  <Icon name={mode === "english" ? "language" : "shield-verify"} size={16} />
                  {t(lang, mode === "english" ? "en_hint" : "guard_hint")}
                </p>
              )}
              <div className="composer-lux__label">
                <label htmlFor="text">{ui(lang, "input_label")}</label>
                <span className="health health--inline" data-state={healthState} aria-live="polite">
                  <span className="health__label">
                    {ui(lang, healthState === "ok" ? "status_ok" : healthState === "loading" ? "status_loading" : "status_down")}
                  </span>
                </span>
              </div>
              <textarea
                id="text"
                ref={textareaRef}
                className="composer-lux__input"
                dir="auto"
                lang={mode === "english" ? "en" : "ar"}
                value={text}
                maxLength={MAX_CHARS}
                placeholder={ui(lang, "input_placeholder")}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") onSubmit(e);
                }}
                aria-describedby="chars input-hint"
              />
              <p id="input-hint" className="composer-lux__hint">
                {ui(lang, "input_hint")}
              </p>
              <div className="composer-lux__row">
                <span id="chars" className="composer-lux__meta">
                  {ui(lang, "chars", { n: nf.format(text.length), max: nf.format(MAX_CHARS) })}
                  <span className="hide-sm">
                    {" · "}
                    <kbd>Ctrl</kbd> + <kbd>↵</kbd> {ui(lang, "shortcut_hint")}
                  </span>
                </span>
                <div className="composer-lux__actions">
                  <button
                    type="button"
                    className="btn-ghost-lux"
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
                  <button type="submit" className="btn-lux" disabled={busy || !text.trim() || !ready}>
                    <Icon name={busy ? "spinner" : "check-run"} size={18} />
                    {busy ? ui(lang, "checking") : mode === "guard" ? t(lang, "guard_run") : ui(lang, "check")}
                  </button>
                </div>
              </div>
              {busy && <div className="scanline" aria-hidden="true" />}
            </form>
          )}

          {mode === "image" && (
            <div
              className="drop"
              data-drag={drag || undefined}
              onDragOver={(e) => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDrag(false);
                onFile(e.dataTransfer.files[0]);
              }}
            >
              <Icon name="upload-image" size={40} />
              <p>{t(lang, "svc_image_d")}</p>
              <label className="btn-lux file-lux">
                <Icon name={busy ? "spinner" : "upload-image"} size={18} />
                {busy ? ui(lang, "checking") : ui(lang, "upload_image").replace(/^(أو|or)\s+/, "")}
                <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => onFile(e.target.files?.[0])} disabled={busy || !ready} />
              </label>
              <span className="health health--inline" data-state={healthState} aria-live="polite">
                <span className="health__label">
                  {ui(lang, healthState === "ok" ? "status_ok" : healthState === "loading" ? "status_loading" : "status_down")}
                </span>
              </span>
              {busy && <div className="scanline" aria-hidden="true" />}
            </div>
          )}

        </div>

        {mode === "text" && !result && !text && (
          <section className="ws-examples" aria-labelledby="ex-h">
            <h2 id="ex-h">{ui(lang, "examples_title")}</h2>
            <ul>
              {EXAMPLES.map((ex) => (
                <li key={ex.key}>
                  <button type="button" className="ex-card" onClick={() => pickExample(ex.text)}>
                    <Icon name={ex.icon} size={20} />
                    <span className="ex-card__text">
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
          <div ref={errorRef} tabIndex={-1} className="banner banner--error reveal-target" role="alert" dir="auto">
            <Icon name="warning" size={18} />
            <span>{error}</span>
          </div>
        )}

        <div id="results" ref={resultsRef} tabIndex={-1} className="results reveal-target" aria-live="polite" aria-busy={busy}>
          {guardResult && mode === "guard" && <GuardPanel g={guardResult} lang={lang} />}
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
              {n > 0 && <ResultsView text={result.ocr_text ?? checkedText} result={result} lang={lang} />}
              <Pipeline r={result} lang={lang} text={result.ocr_text ?? checkedText} />
            </>
          )}
        </div>

        <aside className="ws-notes" aria-label={t(lang, "nav_trust")}>
          <p dir="auto">
            <Icon name="no-generation" size={18} />
            <span>{msg(lang, "fixed", "transparency_notice")}</span>
          </p>
          <p dir="auto">
            <Icon name="privacy-nostore" size={18} />
            <span>{msg(lang, "fixed", "privacy_notice")}</span>
          </p>
        </aside>
      </div>
    </main>
  );
}
