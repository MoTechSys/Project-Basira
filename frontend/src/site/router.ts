/** Minimal History-API router (no dependency). The backend and `vite preview` both fall back to
 *  index.html for unknown paths, so every route below is a real, shareable URL. */

import { useEffect, useState } from "react";

export type Route = "home" | "check" | "services" | "developers" | "trust" | "about" | "settings" | "notfound";

export const PATHS: Record<Exclude<Route, "notfound">, string> = {
  home: "/",
  check: "/check",
  services: "/services",
  developers: "/developers",
  trust: "/trust",
  about: "/about",
  settings: "/settings",
};

export function routeOf(pathname: string): Route {
  const p = pathname.replace(/\/+$/, "") || "/";
  if (p === "/limits") return "trust";
  for (const [k, v] of Object.entries(PATHS)) if (v === p) return k as Route;
  return "notfound";
}

export function navigate(to: string, opts: { replace?: boolean } = {}): void {
  if (to === location.pathname + location.search + location.hash) return;
  if (opts.replace) history.replaceState(null, "", to);
  else history.pushState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function useLocation(): { route: Route; search: URLSearchParams; hash: string; path: string } {
  const read = () => ({ route: routeOf(location.pathname), search: new URLSearchParams(location.search), hash: location.hash, path: location.pathname });
  const [loc, setLoc] = useState(read);
  useEffect(() => {
    const on = () => setLoc(read());
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, []);
  return loc;
}

/** Intercept same-origin <a> clicks so internal links stay in the SPA (modifier keys keep native behaviour). */
export function onLinkClick(e: React.MouseEvent<HTMLAnchorElement>): void {
  const a = e.currentTarget;
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  if (a.target && a.target !== "_self") return;
  const url = new URL(a.href, location.href);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/docs") || url.pathname.startsWith("/v1") || url.pathname.startsWith("/openapi")) return;
  e.preventDefault();
  navigate(url.pathname + url.search + url.hash);
}
