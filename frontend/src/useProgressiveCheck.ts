/** Two-phase check (E-044): two parallel requests — `stage=rules` (deterministic: markers, model tags,
 *  corpus anchors; tens of ms) and `stage=full` (rules ∪ model proposals; 2–8 s). The final REPLACES
 *  the preliminary wholesale — never merged card-by-card — so the end state is a pure function of the
 *  text (determinism). Copy/share/print must be gated on `isFinal`.
 *
 *  Failure matrix (all four tested):
 *   rules ok, full ok        → "final" (or "final_degraded" when the backend flags the model pass)
 *   rules ok, full fails     → keep preliminary, "failed_after_rules", offer retry
 *   rules fails, full ok     → "final" (the preliminary simply never showed)
 *   both fail                → error surfaced, "idle"
 *  A late preliminary can never overwrite a final that already landed. */

import { useCallback, useRef, useState } from "react";
import { check, type CheckResponse, type Lang } from "./api";

export type Phase = "idle" | "rules" | "full" | "final" | "final_degraded" | "failed_after_rules";

export interface ProgressiveState {
  phase: Phase;
  result: CheckResponse | null;
  isFinal: boolean;
  error: string | null;
  /** ids of quotes whose status changed between preliminary and final (brief "updated" tag) */
  changed: Set<string>;
  /** "start-end" keys of spans the deterministic stage found; final quotes outside this set were
   *  added by the model pass. Empty when the preliminary never arrived. */
  ruleSpans: Set<string>;
}

const INITIAL: ProgressiveState = { phase: "idle", result: null, isFinal: false, error: null, changed: new Set(), ruleSpans: new Set() };
const key = (q: { span: { start: number; end: number } }) => `${q.span.start}-${q.span.end}`;

export function diffStatuses(prelim: CheckResponse | null, final: CheckResponse): Set<string> {
  const out = new Set<string>();
  if (!prelim) return out;
  const byKey = new Map(prelim.quotes.map((q) => [key(q), q.status]));
  for (const q of final.quotes) {
    const prev = byKey.get(key(q));
    if (prev !== undefined && prev !== q.status) out.add(q.id);
  }
  return out;
}

export function useProgressiveCheck(lang: Lang, errorText: (e: unknown) => string) {
  const [state, setState] = useState<ProgressiveState>(INITIAL);
  const abort = useRef<AbortController | null>(null);
  const lastText = useRef("");

  const reset = useCallback(() => {
    abort.current?.abort();
    setState(INITIAL);
  }, []);

  /** single-shot (image path: OCR is the slow part; no preliminary) */
  const setSingle = useCallback((r: CheckResponse) => {
    abort.current?.abort();
    setState({ ...INITIAL, phase: r.extraction_degraded ? "final_degraded" : "final", result: r, isFinal: true });
  }, []);

  const run = useCallback(
    async (text: string) => {
      abort.current?.abort();
      const ac = new AbortController();
      abort.current = ac;
      lastText.current = text;
      setState({ ...INITIAL, phase: "rules" });

      let prelim: CheckResponse | null = null;
      const pRules = check(text, lang, ac.signal, "rules").then(
        (r) => {
          if (ac.signal.aborted) return;
          prelim = r;
          const keys = new Set(r.quotes.map(key));
          // show the preliminary only if the final has not already landed
          setState((s) => (s.isFinal ? { ...s, ruleSpans: keys } : { ...s, phase: "full", result: r, ruleSpans: keys }));
        },
        () => undefined, // preliminary failure is non-fatal; the final decides
      );
      const pFull = check(text, lang, ac.signal, "full");

      try {
        const final = await pFull;
        if (ac.signal.aborted) return;
        await pRules;
        if (ac.signal.aborted) return;
        setState((s) => ({
          phase: final.extraction_degraded ? "final_degraded" : "final",
          result: final,
          isFinal: true,
          error: null,
          changed: diffStatuses(prelim, final),
          ruleSpans: s.ruleSpans,
        }));
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        await pRules;
        if (ac.signal.aborted) return;
        if (prelim) {
          setState((s) => ({ ...s, phase: "failed_after_rules", result: prelim, isFinal: false, error: null, changed: new Set() }));
        } else {
          setState({ ...INITIAL, error: errorText(e) });
        }
      }
    },
    [lang, errorText],
  );

  const retry = useCallback(() => {
    if (lastText.current) void run(lastText.current);
  }, [run]);

  return { state, run, reset, retry, setSingle };
}
