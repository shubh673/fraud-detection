// Thin fetch helpers for the precomputed JSON data files in /public/data.
// All data is static JSON produced by scripts/prepare_dashboard_data.py.

const BASE = `${import.meta.env.BASE_URL}data`;

async function loadJson<T>(file: string): Promise<T> {
  const res = await fetch(`${BASE}/${file}`);
  if (!res.ok) throw new Error(`Failed to load ${file} (${res.status})`);
  return (await res.json()) as T;
}

export const loaders = {
  summary: () => loadJson<import("../types/fraud").DashboardSummary>("dashboard_summary.json"),
  metrics: () => loadJson<import("../types/fraud").ModelMetrics>("model_metrics.json"),
  scored: () => loadJson<import("../types/fraud").ScoredTransaction[]>("sample_scored_transactions.json"),
  binAttacks: () => loadJson<import("../types/fraud").BinAttackAlert[]>("bin_attack_alerts.json"),
  ipAlerts: () => loadJson<import("../types/fraud").IpRepetitionAlert[]>("ip_repetitive_authorisation_alerts.json"),
  suggestions: () => loadJson<import("../types/fraud").MerchantSuggestion[]>("merchant_blacklist_suggestions.json"),
  manualBlacklist: () => loadJson<import("../types/fraud").ManualBlacklistEntry[]>("manual_merchant_blacklist.json"),
  queue: () => loadJson<import("../types/fraud").QueueAlert[]>("combined_alert_queue.json"),
  simulator: () => loadJson<import("../types/fraud").OverlayScenario[]>("overlay_simulator.json"),
};

// Generic hook-friendly loader used by pages.
import { useEffect, useState } from "react";

export function useData<T>(fn: () => Promise<T>): {
  data: T | null;
  error: string | null;
  loading: boolean;
} {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fn()
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { data, error, loading };
}
