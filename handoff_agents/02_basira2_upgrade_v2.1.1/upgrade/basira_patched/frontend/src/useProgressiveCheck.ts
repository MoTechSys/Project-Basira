/** Two parallel requests: `stage=rules` (deterministic, ~ms) and `stage=full` (rules + LLM, 2–8 s).
 *  The final REPLACES the preliminary wholesale — never merged card-by-card — so the end state is a
 *  pure function of the text (determinism). Report/share actions must be gated on `isFinal`.
 *
 *  Failure matrix:
 *   rules ok, full ok           → phase "final" (or "final_degraded" when the backend flags it)
 *   rules ok, full fails        → keep preliminary, phase "failed_after_rules", offer retry
 *   rules fails, full ok        → phase "final" (preliminary simply never showed)
 *   both fail                   → error surfaced, phase "idle"
 */

import { useCallback, useRef, useState } from "react";
import { BasiraError, check, type CheckResponse, type Lang } from "./api";
import type { Phase } from "./components/ProgressiveStatus";

export interface ProgressiveState {
  phase: Phase;
  result: CheckResponse | null;
  isFinal: boolean;
  error: string | null;
  /** ids of quotes whose status changed between preliminary and final (for a brief "updated" tag) */
  changed: Set<string>;
  /** "start-end" keys of spans found by deterministic rules (preliminary); final quotes not in this
   *  set were added by the LLM stage. Empty when the preliminary never arrived. */
  ruleSpans: Set<string>;
}

const INITIAL: ProgressiveState = { phase: "idle", result: null, isFinal: false, error: null, changed: new Set(), ruleSpans: new Set() };

function diffStatuses(prelim: CheckResponse | null, final: CheckResponse): Set<string> {
  const out = new Set<string>();
  if (!prelim) return out;
  const byKey = new Map(prelim.quotes.map((q) => [`${q.span.start}-${q.span.end}`, q.status]));
  for (const q of final.quotes) {
    const prev = byKey.get(`${q.span.start}-${q.span.end}`);
    if (prev !== undefined && prev !== q.status) out.add(q.id);
  }
  return out;
}

export function useProgressiveCheck(lang: Lang, errorText: (e: unknown) => string) {
  const [state, setState] = useState<ProgressiveState>(INITIAL);
  const abort = useRef<AbortController | null>(null);
  const lastText = useRef<string>("");

  const reset = useCallback(() => {
    abort.current?.abort();
    setState(INITIAL);
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
          // Only show preliminary if the final has not already landed.
          const keys = new Set(r.quotes.map((q) => `${q.span.start}-${q.span.end}`));
          setState((s) => (s.isFinal ? { ...s, ruleSpans: keys } : { ...s, phase: "full", result: r, ruleSpans: keys }));
        },
        () => {
          /* preliminary failure is non-fatal; final decides */
        },
      );
      const pFull = check(text, lang, ac.signal, "full");

      try {
        const final = await pFull;
        if (ac.signal.aborted) return;
        await pRules; // make sure a late preliminary cannot overwrite the final
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
          setState({ ...INITIAL, error: e instanceof BasiraError ? errorText(e) : errorText(null) });
        }
      }
    },
    [lang, errorText],
  );

  const retry = useCallback(() => {
    if (lastText.current) void run(lastText.current);
  }, [run]);

  return { state, run, reset, retry };
}
