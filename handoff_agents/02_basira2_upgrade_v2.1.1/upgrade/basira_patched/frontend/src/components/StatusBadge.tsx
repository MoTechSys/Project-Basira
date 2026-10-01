import type { Lang, Status } from "../api";
import { msg } from "../i18n";

const ICON: Record<Status, string> = { found: "✓", partial_match: "≈", needs_review: "?", not_found: "—" };

export function StatusBadge({ status, lang }: { status: Status; lang: Lang }) {
  return (
    <span className="badge" data-status={status} role="status">
      <span aria-hidden="true">{ICON[status]}</span>
      {msg(lang, "labels", status)}
    </span>
  );
}
