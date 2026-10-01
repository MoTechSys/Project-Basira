import type { Lang, Status } from "../api";
import { Icon, type BasiraIconName } from "../brand";
import { msg } from "../i18n";

const ICON: Record<Status, BasiraIconName> = {
  found: "state-found",
  partial_match: "state-partial",
  needs_review: "state-review",
  not_found: "state-notfound",
};

export function StatusBadge({ status, lang }: { status: Status; lang: Lang }) {
  return (
    <span className="bs-badge" data-state={status} data-status={status} role="status">
      <Icon name={ICON[status]} size={18} />
      {msg(lang, "labels", status)}
    </span>
  );
}
