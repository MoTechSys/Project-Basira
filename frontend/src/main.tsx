import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import "./site/lux.css";
import "./site/identity.css"; // identity v4 «ختم المعارضة» — loaded last, see E-056
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// PWA: register the shell service worker after load (production only; never caches API responses).
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
