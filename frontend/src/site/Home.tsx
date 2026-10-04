import { lazy, Suspense, useEffect, useState } from "react";
import type { Lang, Status } from "../api";
import { Icon, type BasiraIconName } from "../brand";
import { msg } from "../i18n";
import { capableDevice, useReveal } from "./hooks";
import { LensDemo } from "./LensDemo";
import { A, LiveBadge, SoonBadge } from "./Shell";
import { SERVICES } from "./services";
import { t, type SiteKey } from "./strings";

const Starfield = lazy(() => import("./Starfield"));

const STATES: { s: Status; icon: BasiraIconName; d: SiteKey }[] = [
  { s: "found", icon: "state-found", d: "state_found_d" },
  { s: "partial_match", icon: "state-partial", d: "state_partial_match_d" },
  { s: "needs_review", icon: "state-review", d: "state_needs_review_d" },
  { s: "not_found", icon: "state-notfound", d: "state_not_found_d" },
];

/** Mount the WebGL backdrop only after first paint + idle, and only on capable devices. */
function useAmbient(): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (!capableDevice()) return;
    const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number };
    const go = () => setOn(true);
    const id = w.requestIdleCallback ? w.requestIdleCallback(go, { timeout: 2500 }) : window.setTimeout(go, 1200);
    return () => {
      if (!w.requestIdleCallback) clearTimeout(id);
    };
  }, []);
  return on;
}

export default function Home({ lang }: { lang: Lang }) {
  const ambient = useAmbient();
  useReveal();
  const dark = document.documentElement.dataset["theme"] === "dark";
  return (
    <main id="main" className="page page--home">
      <section className="hero-lux" aria-labelledby="hero-title">
        <div className="hero-lux__bg" aria-hidden="true">
          {ambient && (
            <Suspense fallback={null}>
              <Starfield dark={dark} />
            </Suspense>
          )}
        </div>
        <div className="wrap hero-lux__grid">
          <div className="hero-lux__head">
            <p className="kicker">
              <span className="kicker__dot" aria-hidden="true" />
              {t(lang, "hero_kicker")}
            </p>
            <h1 id="hero-title">{t(lang, "hero_title")}</h1>
          </div>
          <div className="hero-lux__body">
            <p className="hero-lux__sub">{t(lang, "hero_sub")}</p>
            <div className="hero-lux__ctas">
              <A to="/check" className="btn-lux">
                <Icon name="check-run" size={20} />
                {t(lang, "cta_try")}
              </A>
              <A to="#how" className="btn-ghost-lux">
                {t(lang, "hero_secondary")}
              </A>
            </div>
            <p className="motto" aria-label={`${t(lang, "motto_ai")} ${t(lang, "motto_engine")}`}>
              <span className="motto__ai">{t(lang, "motto_ai")}</span>
              <span className="motto__sep" aria-hidden="true" />
              <span className="motto__engine">{t(lang, "motto_engine")}</span>
            </p>
          </div>
          <LensDemo lang={lang} />
        </div>
      </section>

      <section id="how" className="section" aria-labelledby="how-h">
        <div className="wrap">
          <header className="section__head" data-reveal>
            <h2 id="how-h">{t(lang, "how_title")}</h2>
            <p>{t(lang, "how_sub")}</p>
          </header>
          <ol className="steps">
            {([
              ["how_1_t", "how_1_d", "paste-text", null],
              ["how_2_t", "how_2_d", "ocr-scan", "how_role_ai"],
              ["how_3_t", "how_3_d", "byte-exact", "how_role_engine"],
            ] as [SiteKey, SiteKey, BasiraIconName, SiteKey | null][]).map(([tt, dd, ic, role], i) => (
              <li key={tt} className="step" data-reveal data-kind={i === 1 ? "ai" : i === 2 ? "engine" : "you"} style={{ "--i": i } as React.CSSProperties}>
                <span className="step__num" aria-hidden="true">{new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en").format(i + 1)}</span>
                <span className="step__icon" aria-hidden="true">
                  <Icon name={ic} size={26} />
                </span>
                {role && <span className="step__role">{t(lang, role)}</span>}
                <h3>{t(lang, tt)}</h3>
                <p>{t(lang, dd)}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="section section--states" aria-labelledby="states-h">
        <div className="wrap">
          <header className="section__head" data-reveal>
            <h2 id="states-h">{t(lang, "states_title")}</h2>
            <p>{t(lang, "states_sub")}</p>
          </header>
          <ul className="states">
            {STATES.map((x, i) => (
              <li key={x.s} className="state-card" data-status={x.s} data-reveal style={{ "--i": i } as React.CSSProperties}>
                <span className="state-card__icon" aria-hidden="true">
                  <Icon name={x.icon} size={26} />
                </span>
                <h3>{msg(lang, "labels", x.s)}</h3>
                <p>{t(lang, x.d)}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section" aria-labelledby="svc-h">
        <div className="wrap">
          <header className="section__head section__head--row" data-reveal>
            <div>
              <h2 id="svc-h">{t(lang, "services_title")}</h2>
              <p>{t(lang, "services_sub")}</p>
            </div>
            <A to="/services" className="btn-ghost-lux">
              {t(lang, "svc_learn")}
              <Icon name="arrow-start" size={18} className="flip-rtl" />
            </A>
          </header>
          <ul className="svc-grid">
            {SERVICES.map((s, i) => (
              <li key={s.id} className="svc" data-live={s.live || undefined} data-reveal style={{ "--i": i } as React.CSSProperties}>
                <A to={s.href} className="svc__link">
                  <span className="svc__icon" aria-hidden="true">
                    <Icon name={s.icon} size={24} />
                  </span>
                  <span className="svc__title">
                    {t(lang, s.title)}
                    {s.live ? <LiveBadge lang={lang} /> : <SoonBadge lang={lang} />}
                  </span>
                  <span className="svc__desc">{t(lang, s.desc)}</span>
                </A>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section section--cta" aria-labelledby="cta-h">
        <div className="wrap cta-band" data-reveal>
          <h2 id="cta-h">{t(lang, "identity")}</h2>
          <p>{t(lang, "svc_audience")}</p>
          <A to="/check" className="btn-lux">
            <Icon name="check-run" size={20} />
            {t(lang, "cta_start")}
          </A>
        </div>
      </section>
    </main>
  );
}
