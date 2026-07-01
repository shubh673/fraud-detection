import type { Severity } from "../types/fraud";
import { SEVERITY_STYLES } from "../utils/theme";

export default function SeverityBadge({ severity }: { severity: Severity }) {
  const cls = SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.LOW;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${cls}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {severity}
    </span>
  );
}
