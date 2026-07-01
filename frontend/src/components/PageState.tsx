interface Props {
  loading: boolean;
  error: string | null;
  children: React.ReactNode;
}

// Wraps page content with consistent loading / error states.
export default function PageState({ loading, error, children }: Props) {
  if (loading)
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-400">
        <span className="animate-pulse">Loading dashboard data…</span>
      </div>
    );
  if (error)
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
        <p className="font-semibold">Could not load data</p>
        <p className="mt-1 text-red-600">{error}</p>
        <p className="mt-3 text-xs text-red-500">
          Run <code className="rounded bg-red-100 px-1">python scripts/prepare_dashboard_data.py</code>{" "}
          from the project root to regenerate <code className="rounded bg-red-100 px-1">frontend/public/data</code>.
        </p>
      </div>
    );
  return <>{children}</>;
}
