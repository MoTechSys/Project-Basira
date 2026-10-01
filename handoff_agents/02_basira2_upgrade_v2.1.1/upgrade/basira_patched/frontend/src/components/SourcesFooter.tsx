import { useEffect, useState } from "react";
import { sources, type Lang, type SourceInfo } from "../api";
import { msg, ui } from "../i18n";

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
      <p className="fixed" dir="auto">
        {msg(lang, "fixed", "footer")}
      </p>
      <p className="fixed" dir="auto">
        {msg(lang, "fixed", "transparency_notice")}
      </p>
      <p className="fixed" dir="auto">
        {msg(lang, "fixed", "privacy_notice")}
      </p>
      <h2>{ui(lang, "sources_title")}</h2>
      <p>{ui(lang, "sources_hint")}</p>
      {list && list.length > 0 && (
        <ul className="sources" style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {list.map((s) => (
            <li key={s.id} className="source">
              <strong dir="auto">{s.name}</strong>
              <span>
                {ui(lang, "version")}: {s.version || corpus?.[s.id === "ohd" ? "ohd_commit" : s.id.split("_")[0] ?? ""] || "—"}
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
    </footer>
  );
}
