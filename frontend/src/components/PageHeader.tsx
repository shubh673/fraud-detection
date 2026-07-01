import type { ReactNode } from "react";

interface Props {
  title: string;
  description?: string;
  badge?: string;
  children?: ReactNode;
}

export default function PageHeader({ title, description, badge, children }: Props) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold text-slate-900">{title}</h1>
          {badge && (
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700 ring-1 ring-inset ring-blue-200">
              {badge}
            </span>
          )}
        </div>
        {description && <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>}
      </div>
      {children}
    </div>
  );
}
