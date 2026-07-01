import { ACTION_STYLES } from "../utils/theme";
import { titleCase } from "../utils/formatters";

export default function ActionBadge({ action }: { action: string }) {
  const cls = ACTION_STYLES[action] ?? "bg-slate-100 text-slate-700 ring-slate-200";
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${cls}`}
    >
      {titleCase(action)}
    </span>
  );
}
