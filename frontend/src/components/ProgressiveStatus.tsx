/** Three-step strip + preliminary/final note for the two-phase check (E-044).
 *  Text only — no spinner that never ends, no seconds counter. Fixed block size (CLS 0).
 *  Live announcements (exactly two: preliminary, final) are emitted by the parent; this is inert. */

import type { Lang } from "../api";
import { Icon } from "../brand";
import { ui } from "../i18n";
import type { Phase } from "../useProgressiveCheck";

export function ProgressiveStatus({
  phase,
  lang,
  totalMs,
  hash,
  onRetry,
}: {
  phase: Phase;
  lang: Lang;
  totalMs?: number | undefined;
  hash?: string | undefined;
  onRetry?: (() => void) | undefined;
}) {
  if (phase === "idle") return null;
  const nf = new Intl.NumberFormat(lang === "ar" ? "ar-SA" : "en");
  const done = phase === "final" || phase === "final_degraded";
  const steps: { key: string; done: boolean; current: boolean }[] = [
    { key: "step_rules", done: phase !== "rules", current: phase === "rules" },
    { key: "step_llm", done, current: phase === "full" },
    { key: "step_done", done, current: false },
  ];
  return (
    <div className="progress" data-phase={phase} data-testid="progressive-status">
      <ol className="steps" aria-label={ui(lang, "progress_label")}>
        {steps.map((s) => (
          <li key={s.key} data-done={s.done ? "" : undefined} data-current={s.current ? "" : undefined}>
            {s.done ? <Icon name="state-found" size={14} /> : s.current ? <Icon name="spinner" size={14} /> : <span className="steps__dot" aria-hidden="true" />}
            {ui(lang, s.key)}
          </li>
        ))}
      </ol>
      <p className="stage-note" dir="auto">
        {phase === "rules" || phase === "full" ? ui(lang, "preliminary_note") : null}
        {phase === "final" && totalMs !== undefined
          ? ui(lang, "final_note", { ms: nf.format(totalMs) }) + (hash ? ` · ${ui(lang, "hash_label")} ${hash.slice(0, 8)}` : "")
          : null}
        {phase === "final_degraded" ? ui(lang, "final_degraded_note") : null}
        {phase === "failed_after_rules" ? (
          <>
            {ui(lang, "failed_after_rules_note")}{" "}
            {onRetry && (
              <button type="button" className="btn btn--ghost btn--sm" onClick={onRetry}>
                {ui(lang, "retry")}
              </button>
            )}
          </>
        ) : null}
      </p>
    </div>
  );
}
