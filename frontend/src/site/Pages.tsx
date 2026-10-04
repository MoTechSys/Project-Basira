/** Services · Developers · Trust (+ limits) · About · 404. */

import { useEffect, useState } from "react";
import { sources, type Lang, type SourceInfo } from "../api";
import { Icon, type BasiraIconName } from "../brand";
import { msg, ui } from "../i18n";
import trust from "../__generated__/trust.json";
import { useHealth, useReveal } from "./hooks";
import { SERVICES } from "./services";
import { A, GITHUB, LiveBadge, SoonBadge } from "./Shell";
import { numfmt, t, type SiteKey } from "./strings";

function PageHead({ title, sub, kicker }: { title: string; sub: string; kicker?: React.ReactNode }) {
  return (
    <header className="page-head">
      <div className="wrap">
        {kicker}
        <h1>{title}</h1>
        <p>{sub}</p>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ services */
export function Services({ lang }: { lang: Lang }) {
  useReveal();
  return (
    <main id="main" className="page">
      <PageHead title={t(lang, "services_title")} sub={t(lang, "services_sub")} />
      <div className="wrap">
        <p className="audience" data-reveal>
          <Icon name="refer-scholar" size={20} />
          <span>
            <b>{t(lang, "svc_for")}</b> {t(lang, "svc_audience")}
          </span>
        </p>
        <ul className="svc-list">
          {SERVICES.map((s, i) => (
            <li key={s.id} id={s.id} className="svc-row" data-live={s.live || undefined} data-reveal style={{ "--i": i } as React.CSSProperties}>
              <span className="svc__icon" aria-hidden="true">
                <Icon name={s.icon} size={26} />
              </span>
              <div className="svc-row__body">
                <h2>
                  {t(lang, s.title)} {s.live ? <LiveBadge lang={lang} /> : <SoonBadge lang={lang} long />}
                </h2>
                <p>{t(lang, s.desc)}</p>
                <p className="svc-row__out">{t(lang, s.out)}</p>
              </div>
              {s.live ? (
                <A to={s.href} className="btn-ghost-lux">
                  {t(lang, "svc_open")}
                  <Icon name="arrow-start" size={18} className="flip-rtl" />
                </A>
              ) : (
                <span className="svc-row__locked" aria-hidden="true">
                  <Icon name="limits" size={22} />
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------ developers */
function CopyBlock({ code, lang, label }: { code: string; lang: Lang; label: string }) {
  const [ok, setOk] = useState(false);
  return (
    <div className="code">
      <div className="code__bar">
        <span>{label}</span>
        <button
          type="button"
          className="chip-btn"
          onClick={() => {
            void navigator.clipboard?.writeText(code).then(() => {
              setOk(true);
              setTimeout(() => setOk(false), 1400);
            });
          }}
        >
          <Icon name={ok ? "state-found" : "copy"} size={16} />
          {t(lang, ok ? "copied" : "copy")}
        </button>
      </div>
      <pre dir="ltr" tabIndex={0}>
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function Developers({ lang }: { lang: Lang }) {
  useReveal();
  const origin = typeof location !== "undefined" ? location.origin : "https://basira.example";
  // The request body is deliberately non-religious placeholder prose: real text comes from the user.
  const curl = `curl -s ${origin}/v1/check \\\n  -H 'Content-Type: application/json' \\\n  -d '{"text": "<your post>", "ui_lang": "ar"}'`;
  const js = `const r = await fetch("${origin}/v1/check", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({ text: post, ui_lang: "en" }),\n});\nconst { quotes, corpus } = await r.json();\nfor (const q of quotes) console.log(q.status, q.matches[0]?.ref_label_en);`;
  const mcp = `{\n  "mcpServers": {\n    "basira": { "type": "http", "url": "${origin}/mcp" }\n  }\n}`;
  const EP: [string, string, SiteKey][] = [
    ["GET", "/health", "ep_health"],
    ["POST", "/v1/check", "ep_check"],
    ["POST", "/v1/check/image", "ep_image"],
    ["GET", "/v1/sources", "ep_sources"],
    ["GET", "/v1/messages/{ar|en}", "ep_messages"],
    ["POST", "/v1/guard", "ep_guard"],
    ["POST", "/v1/receipt", "ep_receipt"],
    ["GET", "/v/{token}?h=", "ep_replay"],
    ["GET", "/v1/rules", "ep_rules"],
    ["GET", "/v1/models", "ep_models"],
    ["POST", "/mcp", "ep_mcp"],
    ["GET", "/docs", "ep_docs"],
  ];
  return (
    <main id="main" className="page">
      <PageHead title={t(lang, "dev_title")} sub={t(lang, "dev_sub")} kicker={<p className="kicker"><LiveBadge lang={lang} /> REST · OpenAPI 3.1</p>} />
      <div className="wrap dev-grid">
        <section aria-labelledby="dq" data-reveal>
          <h2 id="dq">{t(lang, "dev_quick")}</h2>
          <CopyBlock code={curl} lang={lang} label="curl" />
          <CopyBlock code={js} lang={lang} label="JavaScript" />
          <a href="/docs" className="btn-lux" target="_blank" rel="noopener noreferrer">
            <Icon name="api" size={20} />
            {t(lang, "dev_open_docs")}
          </a>
        </section>
        <section aria-labelledby="de" data-reveal>
          <h2 id="de">{t(lang, "dev_endpoints")}</h2>
          <div className="table-wrap" tabIndex={0} role="region" aria-labelledby="de">
            <table className="ep-table">
              <thead>
                <tr>
                  <th scope="col">{t(lang, "dev_method")}</th>
                  <th scope="col">{t(lang, "dev_path")}</th>
                  <th scope="col">{t(lang, "dev_what")}</th>
                </tr>
              </thead>
              <tbody>
                {EP.map(([m, p, k]) => (
                  <tr key={p}>
                    <td><span className="method" data-m={m}>{m}</span></td>
                    <td><code dir="ltr">{p}</code></td>
                    <td>{t(lang, k)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>{t(lang, "dev_contract")}</h3>
          <p>{t(lang, "dev_contract_d")}</p>
          <h3>{t(lang, "dev_guards")}</h3>
          <p>{t(lang, "dev_guards_d")}</p>
        </section>
        <section className="dev-mcp" aria-labelledby="dm" data-reveal>
          <h2 id="dm">
            {t(lang, "dev_mcp")} <LiveBadge lang={lang} />
          </h2>
          <p>{t(lang, "dev_mcp_d")}</p>
          <CopyBlock code={mcp} lang={lang} label={t(lang, "dev_mcp_cfg")} />
        </section>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------ trust */
interface TrustItem {
  key: string;
  value: string;
  n: string | null;
  ci: string | null;
  source: string;
  line: number;
}
const TRUST = (trust as { items: TrustItem[] }).items;

function fmtValue(it: TrustItem, lang: Lang): string {
  const nf = numfmt(lang);
  const v = Number(it.value);
  // rates in [0,1] from eval/REPORT.md are shown as the raw count when available ("150/150") — no rounding games
  if (it.n && it.n.includes("/")) {
    const [a, b] = it.n.split("/").map(Number);
    return `${nf.format(a ?? 0)}/${nf.format(b ?? 0)}`;
  }
  if (it.key === "ie1b_danger") return `${nf.format(v)}/${nf.format(Number(it.n))}`;
  return `${new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v)}%`;
}

export function Trust({ lang }: { lang: Lang }) {
  useReveal();
  const [list, setList] = useState<SourceInfo[] | null>(null);
  const { data } = useHealth();
  const nf = numfmt(lang);
  useEffect(() => {
    let alive = true;
    sources()
      .then((s) => alive && setList(s))
      .catch(() => alive && setList([]));
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
  }, []);
  const METH: [SiteKey, SiteKey, BasiraIconName][] = [
    ["meth_1_t", "meth_1_d", "byte-exact"],
    ["meth_2_t", "meth_2_d", "deterministic"],
    ["meth_3_t", "meth_3_d", "shield-verify"],
    ["meth_4_t", "meth_4_d", "no-judgment"],
  ];
  return (
    <main id="main" className="page">
      <PageHead title={t(lang, "trust_title")} sub={t(lang, "trust_sub")} />
      <div className="wrap">
        <section aria-labelledby="tn" className="trust-block">
          <header className="section__head" data-reveal>
            <h2 id="tn">{t(lang, "trust_numbers")}</h2>
            <p>{t(lang, "trust_numbers_d")}</p>
          </header>
          <ul className="metrics">
            {TRUST.map((it, i) => (
              <li key={it.key} className="metric" data-reveal style={{ "--i": i } as React.CSSProperties} data-key={it.key}>
                <span className="metric__value" dir="ltr">{fmtValue(it, lang)}</span>
                <span className="metric__label">{t(lang, `m_${it.key}` as SiteKey)}</span>
                <span className="metric__meta">
                  {it.ci && (
                    <span>
                      {t(lang, "trust_ci")}: <span dir="ltr">{it.ci}</span>
                    </span>
                  )}
                  {it.n && !it.n.includes("/") && it.key !== "ie1b_danger" && (
                    <span>
                      {t(lang, "trust_n")}: {nf.format(Number(it.n))}
                    </span>
                  )}
                  <a href={`${GITHUB}/blob/main/${it.source}#L${it.line}`} target="_blank" rel="noopener noreferrer" className="metric__src">
                    <Icon name="source-link" size={14} />
                    <span dir="ltr">
                      {it.source}:{it.line}
                    </span>
                  </a>
                </span>
              </li>
            ))}
          </ul>
          <p className="caveat" data-reveal>
            <Icon name="info" size={18} />
            <span>{t(lang, "trust_caveat")}</span>
          </p>
        </section>

        <section aria-labelledby="tm" className="trust-block">
          <h2 id="tm" data-reveal>{t(lang, "trust_method")}</h2>
          <ul className="method-grid">
            {METH.map(([a, b, ic], i) => (
              <li key={a} data-reveal style={{ "--i": i } as React.CSSProperties}>
                <Icon name={ic} size={24} />
                <h3>{t(lang, a)}</h3>
                <p>{t(lang, b)}</p>
              </li>
            ))}
          </ul>
          <p className="fixed-note" dir="auto">{msg(lang, "fixed", "transparency_notice")}</p>
        </section>

        <section id="sources" aria-labelledby="ts" className="trust-block">
          <h2 id="ts">{t(lang, "trust_sources")}</h2>
          <p className="muted">{t(lang, "trust_sources_d")}</p>
          {list === null ? (
            <div className="skeleton" aria-hidden="true" />
          ) : list.length === 0 ? (
            <p className="muted">{t(lang, "trust_sources_offline")}</p>
          ) : (
            <ul className="src-grid">
              {list.map((s) => (
                <li key={s.id} className="src-card">
                  <strong dir="auto">{s.name}</strong>
                  <span>
                    {ui(lang, "version")}: <span dir="ltr">{s.version || data?.corpus[s.id] || "—"}</span>
                    {s.records ? ` · ${nf.format(s.records)} ${ui(lang, "records")}` : ""}
                  </span>
                  <span>
                    {ui(lang, "license")}:{" "}
                    <a href={s.license_url} target="_blank" rel="noopener noreferrer">
                      {s.license.split("—")[0]?.split("(")[0]?.trim()}
                    </a>{" "}
                    ·{" "}
                    <a href={s.url} target="_blank" rel="noopener noreferrer">
                      {new URL(s.url).hostname}
                    </a>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section id="limits" aria-labelledby="tl" className="trust-block limits">
          <header className="section__head">
            <h2 id="tl">{t(lang, "limits_title")}</h2>
            <p>{t(lang, "limits_sub")}</p>
          </header>
          <ol className="limits-list">
            {(["limit_1", "limit_2", "limit_3", "limit_4", "limit_5", "limit_6", "limit_7", "limit_8"] as SiteKey[]).map((k) => (
              <li key={k}>{t(lang, k)}</li>
            ))}
          </ol>
        </section>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------ about */
export function About({ lang }: { lang: Lang }) {
  useReveal();
  const P: [string, BasiraIconName][] = [
    [ui(lang, "principle_1"), "byte-exact"],
    [ui(lang, "principle_2"), "no-judgment"],
    [ui(lang, "principle_3"), "limits"],
    [ui(lang, "principle_4"), "privacy-nostore"],
  ];
  return (
    <main id="main" className="page">
      <PageHead title={t(lang, "about_title")} sub={t(lang, "identity")} />
      <div className="wrap about">
        <p className="about__lead" data-reveal>{t(lang, "about_lead")}</p>
        <div className="about__grid">
          <section data-reveal>
            <h2>{t(lang, "about_why_t")}</h2>
            <p>{t(lang, "about_why_d")}</p>
          </section>
          <section data-reveal>
            <h2>{t(lang, "about_ai_t")}</h2>
            <p>{t(lang, "about_ai_d")}</p>
          </section>
          <section data-reveal>
            <h2>{t(lang, "about_challenge_t")}</h2>
            <p>{t(lang, "about_challenge_d")}</p>
          </section>
        </div>
        <section aria-labelledby="ap" className="trust-block">
          <h2 id="ap">{t(lang, "about_principles_t")}</h2>
          <ul className="method-grid">
            {P.map(([txt, ic]) => (
              <li key={ic} data-reveal>
                <Icon name={ic} size={24} />
                <p>{txt}</p>
              </li>
            ))}
          </ul>
        </section>
        <p>
          <a href={GITHUB} className="btn-ghost-lux" target="_blank" rel="noopener noreferrer">
            <Icon name="github" size={18} />
            {t(lang, "about_code")}
          </a>
        </p>
      </div>
    </main>
  );
}

export function NotFound({ lang }: { lang: Lang }) {
  return (
    <main id="main" className="page">
      <PageHead title={t(lang, "not_found_title")} sub={t(lang, "not_found_d")} />
      <div className="wrap">
        <A to="/" className="btn-lux">
          {t(lang, "back_home")}
        </A>
      </div>
    </main>
  );
}
