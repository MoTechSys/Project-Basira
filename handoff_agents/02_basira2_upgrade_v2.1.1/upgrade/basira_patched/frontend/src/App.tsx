import { useEffect, useState } from "react";
import type { Lang } from "./api";
import Check from "./Check";

function initialLang(): Lang {
  const saved = localStorage.getItem("basira.lang");
  if (saved === "ar" || saved === "en") return saved;
  return navigator.language.toLowerCase().startsWith("ar") ? "ar" : "ar"; // Arabic-first product
}

export default function App() {
  const [lang, setLang] = useState<Lang>(initialLang);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    localStorage.setItem("basira.lang", lang);
  }, [lang]);
  return <Check lang={lang} onLang={setLang} />;
}
