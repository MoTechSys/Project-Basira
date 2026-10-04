/** /settings — Genspark key (saved once on the server) + model choice (E-051).
 *
 *  Compact single column, no hero. The key is sent once to PUT /v1/models/config, verified upstream and
 *  stored server-side; the browser keeps nothing and never sends it again. Changing the model later does
 *  not require re-entering the key. Catalog numbers come from /v1/models (measured, backend-owned). */

import { useEffect, useState } from "react";
import { clearModelConfig, models, saveModelConfig, type Lang, type ModelConfigState, type ModelInfo, type SaveResult } from "../api";
import { Icon } from "../brand";
import { numfmt, t } from "./strings";

const RECOMMENDED = 3;

export default function Settings({ lang }: { lang: Lang }) {
  const nf = numfmt(lang);
  const [catalog, setCatalog] = useState<ModelInfo[]>([]);
  const [config, setConfig] = useState<ModelConfigState | null>(null);
  const [key, setKey] = useState("");
  const [model, setModel] = useState("");
  const [all, setAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SaveResult | "error" | "cleared" | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    let alive = true;
    models()
      .then((c) => {
        if (!alive) return;
        setCatalog(c.models);
        setConfig(c.config);
        setModel(c.config.model ?? c.default);
      })
      .catch(() => alive && setConfig({ configured: false, model: null, key_masked: null, provider: "" }));
    return () => {
      alive = false;
    };
  }, []);

  const configured = !!config?.configured;
  const keyOk = key.trim().length >= 16;
  const canSave = !busy && !!model && (keyOk || configured);
  const selectedIdx = catalog.findIndex((m) => m.id === model);
  const visible = all ? catalog : catalog.slice(0, Math.max(RECOMMENDED, selectedIdx + 1));

  async function onSave() {
    setBusy(true);
    setResult(null);
    try {
      const body = keyOk ? { api_key: key.trim(), model } : { model };
      const r = await saveModelConfig(body);
      setResult(r);
      setConfig(r.config);
      if (r.saved) setKey("");
    } catch {
      setResult("error");
    } finally {
      setBusy(false);
    }
  }
  async function onClear() {
    setBusy(true);
    try {
      const r = await clearModelConfig();
      setConfig(r.config);
      setResult("cleared");
      setKey("");
    } catch {
      setResult("error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="page set-page">
      <div className="wrap set-wrap">
        <h1 className="set-h1">{t(lang, "set_title")}</h1>

        {/* status line */}
        <p className="set-state" role="status" aria-live="polite">
          {config === null ? (
            "…"
          ) : configured ? (
            <>
              <span className="tag tag--live">{t(lang, "set_active")}</span> <code dir="ltr">{config.model}</code>
              <span className="set-vendor" dir="ltr">
                · {t(lang, "set_key_label")} {config.key_masked}
              </span>
            </>
          ) : (
            <span className="tag tag--soon">{t(lang, "set_not_configured")}</span>
          )}
        </p>

        {/* key */}
        <section className="set-block" aria-labelledby="sk">
          <label id="sk" htmlFor="byok-key" className="set-label">
            {t(lang, "set_key_label")}
          </label>
          <div className="set-input-row">
            <input
              id="byok-key"
              className="set-input"
              type={show ? "text" : "password"}
              autoComplete="off"
              spellCheck={false}
              dir="ltr"
              placeholder={configured ? t(lang, "set_key_keep") : "gsk-…"}
              value={key}
              onChange={(e) => {
                setKey(e.target.value);
                setResult(null);
              }}
            />
            <button type="button" className="set-icon-btn" onClick={() => setShow((v) => !v)} aria-pressed={show} aria-label={t(lang, "set_key_label")}>
              <Icon name={show ? "privacy-nostore" : "info"} size={18} />
            </button>
          </div>
          <p className="set-help">{t(lang, "set_key_help")}</p>
        </section>

        {/* model */}
        <section className="set-block" aria-labelledby="sm">
          <p id="sm" className="set-label">
            {t(lang, "set_model_label")}
          </p>
          <ul className="set-list" role="radiogroup" aria-labelledby="sm">
            {visible.map((m) => {
              const sel = m.id === model;
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={sel}
                    className="set-row"
                    data-selected={sel || undefined}
                    onClick={() => {
                      setModel(m.id);
                      setResult(null);
                    }}
                  >
                    <span className="set-radio" aria-hidden="true" />
                    <span className="set-row__main">
                      <span className="set-row__title">
                        <strong>{m.label}</strong>
                        <span className="set-vendor">{m.vendor}</span>
                        {m.default && <span className="tag tag--live">{t(lang, "set_default")}</span>}
                      </span>
                      <span className="set-row__stats" dir="ltr">
                        <span title={t(lang, "set_col_exact")}>
                          {m.extract_exact}/{m.extract_total}
                        </span>
                        <span title={t(lang, "set_col_speed")}>{nf.format(m.extract_p50_ms)} ms</span>
                        <span title={t(lang, "set_col_cost")}>{m.cost_x}×</span>
                        <span className="set-tier">{t(lang, `set_tier_${m.tier}` as const)}</span>
                      </span>
                      {sel && <span className="set-row__note">{lang === "ar" ? m.note_ar : m.note_en}</span>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {catalog.length > RECOMMENDED && (
            <button type="button" className="set-more" onClick={() => setAll((v) => !v)} aria-expanded={all}>
              <Icon name="chevron-down" size={16} />
              {all ? t(lang, "set_less") : t(lang, "set_more", { n: nf.format(catalog.length) })}
            </button>
          )}
          <p className="set-help">{t(lang, "set_cat_sub")}</p>
        </section>

        {/* actions */}
        <div className="set-actions">
          <button type="button" className="btn-lux" disabled={!canSave} onClick={onSave}>
            <Icon name="shield-verify" size={20} />
            {busy ? t(lang, "set_verifying") : t(lang, "set_save")}
          </button>
          {configured && (
            <button type="button" className="btn-lux btn-lux--sm" disabled={busy} onClick={onClear}>
              {t(lang, "set_clear")}
            </button>
          )}
        </div>
        <div className="set-status" role="status" aria-live="polite">
          {result && result !== "error" && result !== "cleared" && result.saved && (
            <p className="set-ok">{t(lang, "set_saved_ok", { model: result.model, ms: nf.format(result.latency_ms) })}</p>
          )}
          {result && result !== "error" && result !== "cleared" && !result.saved && (
            <p className="set-fail">{t(lang, `set_fail_${result.reason}` as const)}</p>
          )}
          {result === "error" && <p className="set-fail">{t(lang, "set_fail_transport")}</p>}
          {result === "cleared" && <p>{t(lang, "set_cleared")}</p>}
        </div>
      </div>
    </main>
  );
}
