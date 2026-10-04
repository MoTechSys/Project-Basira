import { lazy, Suspense, useEffect, useState } from "react";
import type { Lang } from "./api";
import Home from "./site/Home";
import { useLocation } from "./site/router";
import { Footer, Header } from "./site/Shell";
import { t } from "./site/strings";

// the workspace and secondary pages are separate chunks: the home page (the hook) ships only what it shows
const Check = lazy(() => import("./Check"));
const Services = lazy(() => import("./site/Pages").then((m) => ({ default: m.Services })));
const Developers = lazy(() => import("./site/Pages").then((m) => ({ default: m.Developers })));
const Trust = lazy(() => import("./site/Pages").then((m) => ({ default: m.Trust })));
const About = lazy(() => import("./site/Pages").then((m) => ({ default: m.About })));
const NotFound = lazy(() => import("./site/Pages").then((m) => ({ default: m.NotFound })));
const Settings = lazy(() => import("./site/Settings"));

function initialLang(): Lang {
  const q = new URLSearchParams(location.search).get("lang");
  if (q === "ar" || q === "en") return q;
  const saved = localStorage.getItem("basira.lang");
  if (saved === "ar" || saved === "en") return saved;
  return "ar"; // Arabic-first product
}

const TITLES: Record<string, Record<Lang, string>> = {
  home: { ar: "بصيرة | تحقّق من نقل الآيات والأحاديث قبل أن تنشر", en: "Basira | Check verses and hadiths before you publish" },
};

export default function App() {
  const [lang, setLang] = useState<Lang>(initialLang);
  const { route } = useLocation();

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    localStorage.setItem("basira.lang", lang);
  }, [lang]);

  useEffect(() => {
    const key = ({ check: "nav_check", services: "nav_services", developers: "nav_developers", trust: "nav_trust", about: "nav_about", settings: "nav_settings" } as const)[route as "check"];
    document.title = key ? `${t(lang, key)} | ${lang === "ar" ? "بصيرة" : "Basira"}` : (TITLES["home"]?.[lang] ?? "Basira");
    if (!location.hash) window.scrollTo({ top: 0 });
  }, [route, lang]);

  let page: React.ReactNode;
  switch (route) {
    case "home":
      page = <Home lang={lang} />;
      break;
    case "check":
      page = <Check lang={lang} />;
      break;
    case "services":
      page = <Services lang={lang} />;
      break;
    case "developers":
      page = <Developers lang={lang} />;
      break;
    case "trust":
      page = <Trust lang={lang} />;
      break;
    case "about":
      page = <About lang={lang} />;
      break;
    case "settings":
      page = <Settings lang={lang} />;
      break;
    default:
      page = <NotFound lang={lang} />;
  }

  return (
    <div className="app-lux" data-route={route}>
      <a href="#main" className="skip-link">
        {t(lang, "skip")}
      </a>
      <Header lang={lang} onLang={setLang} route={route} />
      <Suspense fallback={<main id="main" className="page page--loading" aria-busy="true" />}>{page}</Suspense>
      <Footer lang={lang} />
    </div>
  );
}
