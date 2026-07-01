import type { ReactNode } from "react";

interface Props {
  label: string;
  value: ReactNode;
  sub?: string;
  accent?: "navy" | "emerald" | "amber" | "red" | "indigo" | "slate";
  icon?: ReactNode;
}

const ACCENTS: Record<string, string> = {
  navy: "border-l-blue-900",
  emerald: "border-l-emerald-500",
  amber: "border-l-amber-500",
  red: "border-l-red-500",
  indigo: "border-l-indigo-500",
  slate: "border-l-slate-400",
};

export default function KpiCard({ label, value, sub, accent = "navy", icon }: Props) {
  return (
    <div
      className={`rounded-xl border border-slate-200 border-l-4 bg-[#161619] p-4 shadow-sm ${ACCENTS[accent]}`}
    >
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {label}
        </p>
        {icon && <span className="text-slate-300">{icon}</span>}
      </div>
      <p className="mt-2 text-2xl font-bold tabular text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}
