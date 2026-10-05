/** Platform shell: header (brand, primary nav, engine status, theme, language, CTA), mobile menu, footer.
 *  Each page renders its own <main id="main">. */

import { useEffect, useRef, useState } from "react";
import type { Lang } from "../api";
import { Icon, LogoMark } from "../brand";
import { msg } from "../i18n";
import { useHealth, useTheme } from "./hooks";
import { onLinkClick, PATHS, type Route } from "./router";
import { t, type SiteKey } from "./strings";

const NAV: { route: Exclude<Route, "notfound">; key: SiteKey }[] = [
  { route: "home", key: "nav_home" },
  { route: "check", key: "nav_check" },
  { route: "services", key: "nav_services" },
  { route: "developers", key: "nav_developers" },
  { route: "trust", key: "nav_trust" },
  { route: "about", key: "nav_about" },
  { route: "settings", key: "nav_settings" },
];

export const GITHUB = "https://github.com/MoTechSys/Basira.ai";

export function A({ to, className, children, ...rest }: { to: string; className?: string; children: React.ReactNode } & Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href">) {
  return (
    <a href={to} className={className} onClick={onLinkClick} {...rest}>
      {children}
    </a>
  );
}

function EngineDot({ lang }: { lang: Lang }) {
  const { state } = useHealth();
  const label = t(lang, state === "ok" ? "health_ok" : state === "loading" ? "health_loading" : "health_down");
  return (
    <span className="engine-dot" data-state={state} title={label}>
      <span className="sr-only" aria-live="polite">
        {label}
      </span>
    </span>
  );
}

export function Header({ lang, onLang, route }: { lang: Lang; onLang: (l: Lang) => void; route: Route }) {
  const [theme, toggleTheme] = useTheme();
  const [open, setOpen] = useState(false);
  const menuBtn = useRef<HTMLButtonElement>(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => setOpen(false), [route]);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 8);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        menuBtn.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header className="site-header" data-scrolled={scrolled || undefined} data-route={route}>
      <div className="wrap site-header__inner">
        <A to="/" className="site-brand">
          <LogoMark size={36} title="" />
          <span className="site-brand__name">
            <strong>{lang === "ar" ? "بصيرة" : "Basira"}</strong>
            <span lang={lang === "ar" ? "en" : "ar"}>{lang === "ar" ? "Basira" : "بصيرة"}</span>
          </span>
        </A>

        <nav className="site-nav" aria-label={t(lang, "nav_primary")}>
          <ul>
            {NAV.slice(1).map((n) => (
              <li key={n.route}>
                <A to={PATHS[n.route]} aria-current={route === n.route ? "page" : undefined}>
                  {t(lang, n.key)}
                </A>
              </li>
            ))}
          </ul>
        </nav>

        <div className="site-actions">
          <EngineDot lang={lang} />
          <button type="button" className="icon-btn" onClick={toggleTheme} aria-label={t(lang, "theme")} aria-pressed={theme === "dark"}>
            <Icon name="theme" size={20} />
          </button>
          <button type="button" className="icon-btn icon-btn--text" lang={lang === "ar" ? "en" : "ar"} onClick={() => onLang(lang === "ar" ? "en" : "ar")}>
            <Icon name="language" size={18} />
            <span className="hide-sm">{t(lang, "lang")}</span>
            <span className="sr-only show-sm-sr">{t(lang, "lang")}</span>
          </button>
          {route !== "check" && (
            <A to="/check" className="btn-lux btn-lux--sm hide-sm">
              {t(lang, "cta_start")}
            </A>
          )}
          <button
            ref={menuBtn}
            type="button"
            className="icon-btn menu-btn"
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={t(lang, open ? "nav_close" : "nav_menu")}
            onClick={() => setOpen((o) => !o)}
          >
            <Icon name={open ? "close" : "menu"} size={22} />
          </button>
        </div>
      </div>

      <div id="mobile-menu" className="mobile-menu" data-open={open || undefined} hidden={!open}>
        <nav aria-label={t(lang, "nav_primary")}>
          <ul>
            {NAV.map((n, i) => (
              <li key={n.route} style={{ "--i": i } as React.CSSProperties}>
                <A to={PATHS[n.route]} aria-current={route === n.route ? "page" : undefined}>
                  <span>{t(lang, n.key)}</span>
                  <Icon name="arrow-start" size={18} className="flip-rtl" />
                </A>
              </li>
            ))}
          </ul>
          <A to="/check" className="btn-lux btn-lux--block">
            {t(lang, "cta_start")}
          </A>
        </nav>
      </div>
    </header>
  );
}

export function Footer({ lang }: { lang: Lang }) {
  return (
    <footer className="site-footer">
      <div className="wrap">
        <div className="site-footer__top">
          <div className="site-footer__brand">
            <LogoMark size={44} title="" />
            <p className="site-footer__identity">{t(lang, "identity")}</p>
            <p className="site-footer__motto">
              <span>{t(lang, "motto_ai")}</span>
              <span aria-hidden="true">·</span>
              <span>{t(lang, "motto_engine")}</span>
            </p>
          </div>
          <nav aria-label={t(lang, "footer_product")}>
            <h2>{t(lang, "footer_product")}</h2>
            <ul>
              <li><A to="/check">{t(lang, "nav_check")}</A></li>
              <li><A to="/services">{t(lang, "nav_services")}</A></li>
              <li><A to="/developers">{t(lang, "nav_developers")}</A></li>
              <li><a href="/docs" target="_blank" rel="noopener noreferrer">{t(lang, "footer_api")}</a></li>
            </ul>
          </nav>
          <nav aria-label={t(lang, "footer_trust")}>
            <h2>{t(lang, "footer_trust")}</h2>
            <ul>
              <li><A to="/trust">{t(lang, "nav_trust")}</A></li>
              <li><A to="/trust#limits">{t(lang, "footer_limits")}</A></li>
              <li><A to="/trust#sources">{t(lang, "footer_sources")}</A></li>
              <li><A to="/about">{t(lang, "nav_about")}</A></li>
              <li><a href={GITHUB} target="_blank" rel="noopener noreferrer">{t(lang, "about_code")}</a></li>
            </ul>
          </nav>
        </div>
        <p className="site-footer__fixed" dir="auto">{msg(lang, "fixed", "footer")}</p>
        <p className="site-footer__bottom">{t(lang, "footer_tag")}</p>
      </div>
    </footer>
  );
}

export function SoonBadge({ lang, long = false }: { lang: Lang; long?: boolean }) {
  return (
    <span className="tag tag--soon" title={t(lang, "badge_soon_long")}>
      {t(lang, long ? "badge_soon_long" : "badge_soon")}
    </span>
  );
}
export function LiveBadge({ lang }: { lang: Lang }) {
  return <span className="tag tag--live">{t(lang, "badge_live")}</span>;
}
