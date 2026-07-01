import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  tone?: "info" | "warn";
}

export default function NoteBanner({ children, tone = "info" }: Props) {
  const styles =
    tone === "warn"
      ? "bg-amber-50 text-amber-900 ring-amber-200"
      : "bg-sky-50 text-sky-900 ring-sky-200";
  return (
    <div className={`mb-4 flex gap-2 rounded-lg px-3 py-2.5 text-xs ring-1 ring-inset ${styles}`}>
      <span className="font-semibold">Note</span>
      <span>{children}</span>
    </div>
  );
}
