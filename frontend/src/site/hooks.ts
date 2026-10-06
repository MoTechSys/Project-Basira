/** Shared hooks: one health poller for the whole app (header dot + workspace gate), theme, motion/device tier. */

import { useEffect, useState, useSyncExternalStore } from "react";
import { health, type Health } from "../api";

export type HealthState = "ok" | "loading" | "down";
interface HealthSnap {
  state: HealthState;
  data: Health | null;
}

let snap: HealthSnap = { state: "loading", data: null };
const subs = new Set<() => void>();
let timer: ReturnType<typeof setTimeout> | undefined;
let started = false;

function set(next: HealthSnap) {
  snap = next;
  subs.forEach((f) => f());
}

async function poll() {
  try {
    const h = await health();
    if (h.corpus_loaded) {
      set({ state: "ok", data: h });
      return; // ready: stop polling
    }
    set({ state: "loading", data: h });
  } catch {
    set({ state: "down", data: null });
  }
  timer = setTimeout(() => void poll(), 3000);
}

/** test helper: forget the cached state so each test starts from "loading" */
export function __resetHealth(): void {
  if (timer) clearTimeout(timer);
  started = false;
  snap = { state: "loading", data: null };
}

export function useHealth(): HealthSnap {
  const s = useSyncExternalStore(
    (f) => {
      subs.add(f);
      if (!started) {
        started = true;
        void poll();
      }
      return () => subs.delete(f);
    },
    () => snap,
  );
  return s;
}

export type Theme = "light" | "dark";
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("basira.theme");
    if (saved === "light" || saved === "dark") return saved;
    const mq = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    return mq?.matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.dataset["theme"] = theme;
    localStorage.setItem("basira.theme", theme);
    const meta = document.querySelector('meta[name="theme-color"]:not([media])');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#0B0F2A" : "#F2F4FF");
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

export function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function useReducedMotion(): boolean {
  const [r, setR] = useState(prefersReducedMotion);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setR(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return r;
}

/** Heavy visuals (WebGL) only on capable devices: no reduced motion, no data-saver, ≥4 cores, ≥4 GB when reported. */
export function capableDevice(): boolean {
  if (prefersReducedMotion()) return false;
  const nav = navigator as Navigator & { deviceMemory?: number; connection?: { saveData?: boolean; effectiveType?: string } };
  if (nav.connection?.saveData) return false;
  if (nav.connection?.effectiveType && /(^|-)2g|3g/.test(nav.connection.effectiveType)) return false;
  if ((nav.hardwareConcurrency ?? 8) < 4) return false;
  if (nav.deviceMemory !== undefined && nav.deviceMemory < 4) return false;
  return true;
}

/** Reveal-on-scroll. Elements already in view stay untouched (no flash, no CLS); elements below the fold get
 *  data-in="0" (hidden) and switch to "1" when they intersect. A 4 s safety timer reveals everything.
 *
 *  Runs once per mount (empty deps). The earlier version re-ran on every render: when the page re-rendered
 *  ~1 s later (Starfield mounting, language or theme toggle) the cleanup disconnected the observer and
 *  cancelled the safety timer, and the new run selected `[data-reveal]:not([data-in])` — zero elements,
 *  because all had been marked "0" already — so everything below the fold stayed at opacity 0 for ever
 *  (measured live: 18/18 hidden after a full scroll). Now hidden elements are re-adopted, and cleanup
 *  reveals everything so nothing can be left invisible (E-065). */
export function useReveal(): void {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
    const showAll = () => els.forEach((e) => (e.dataset["in"] = "1"));
    if (!("IntersectionObserver" in window) || prefersReducedMotion()) {
      showAll();
      return;
    }
    const vh = window.innerHeight;
    const below = els.filter((e) => e.dataset["in"] !== "1" && e.getBoundingClientRect().top > vh * 0.92);
    els.filter((e) => !below.includes(e)).forEach((e) => (e.dataset["in"] = "1"));
    below.forEach((e) => (e.dataset["in"] = "0"));
    const io = new IntersectionObserver(
      (entries) => {
        for (const en of entries)
          if (en.isIntersecting) {
            (en.target as HTMLElement).dataset["in"] = "1";
            io.unobserve(en.target);
          }
      },
      { rootMargin: "0px 0px -6% 0px" },
    );
    below.forEach((e) => io.observe(e));
    const safety = window.setTimeout(showAll, 4000);
    return () => {
      io.disconnect();
      clearTimeout(safety);
      showAll(); // never leave content hidden behind a torn-down observer
    };
  }, []);
}
