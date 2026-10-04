import { useEffect, useState } from "react";
import { sources, type Lang, type SourceInfo } from "../api";
import { Icon, type BasiraIconName } from "../brand";
import { msg, ui } from "../i18n";

const PRINCIPLES: { key: string; icon: BasiraIconName }[] = [
  { key: "principle_1", icon: "byte-exact" },
  { key: "principle_2", icon: "no-judgment" },
  { key: "principle_3", icon: "limits" },
  { key: "principle_4", icon: "privacy-nostore" },
];

export function SourcesFooter({ lang, corpus }: { lang: Lang; corpus: Record<string, string> | null }) {
  const [list, setList] = useState<SourceInfo[] | null>(null);
  useEffect(() => {
    let alive = true;
    sources()
      .then((s) => alive && setList(s))
      .catch(() => alive && setList([]));
    return () => {
      alive = false;
    };
  }, []);
  const nf = new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en");
  return (
    <footer className="footer" id="sources">
      <div className="container container--wide">
        <div className="footer__grid">
          <section aria-labelledby="pr-h">
            <h2 id="pr-h">{ui(lang, "principles_title")}</h2>
            <ul className="principles">
              {PRINCIPLES.map((p) => (
                <li key={p.key} dir="auto">
                  <Icon name={p.icon} size={20} />
                  <span>{ui(lang, p.key)}</span>
                </li>
              ))}
            </ul>
            <p className="fixed" dir="auto" style={{ marginBlockStart: "var(--bs-sp-4)" }}>
              {msg(lang, "fixed", "footer")}
            </p>
            <p dir="auto">{msg(lang, "fixed", "transparency_notice")}</p>
            <p dir="auto">{msg(lang, "fixed", "privacy_notice")}</p>
          </section>
          <section aria-labelledby="src-h">
            <h2 id="src-h">{ui(lang, "sources_title")}</h2>
            <p style={{ marginBlockStart: 0 }}>{ui(lang, "sources_hint")}</p>
            {list && list.length > 0 && (
              <ul className="sources">
                {list.map((s) => (
                  <li key={s.id} className="source">
                    <strong dir="auto">{s.name}</strong>
                    <span>
                      {ui(lang, "version")}: {s.version || corpus?.[s.id === "ohd" ? "ohd_commit" : (s.id.split("_")[0] ?? "")] || "—"}
                      {s.records ? ` · ${nf.format(s.records)} ${ui(lang, "records")}` : ""}
                    </span>
                    <br />
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
        </div>
        <div className="footer__bottom">
          <span>
            {ui(lang, "app_name")} · <span lang="en">Basira</span>
          </span>
          <nav aria-label="links" style={{ display: "flex", gap: "var(--bs-sp-4)", flexWrap: "wrap" }}>
            <a href="/docs" target="_blank" rel="noopener noreferrer">
              <Icon name="api" size={16} />
              {ui(lang, "api_link")}
            </a>
            <a href="https://github.com/MoTechSys/Project-Basira" target="_blank" rel="noopener noreferrer">
              <Icon name="github" size={16} />
              {ui(lang, "github_link")}
            </a>
          </nav>
        </div>
      </div>
    </footer>
  );
}
