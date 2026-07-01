import { useMemo, useState } from "react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import PageState from "../components/PageState";
import DataTable, { type Column } from "../components/DataTable";
import ActionBadge from "../components/ActionBadge";
import ReasonCodeList from "../components/ReasonCodeList";
import { loaders, useData } from "../utils/dataLoaders";
import { fmtNum, fmtPct, splitReasonCodes } from "../utils/formatters";
import type { ManualBlacklistEntry, MerchantSuggestion } from "../types/fraud";

export default function MerchantBlacklist() {
  const manual = useData(loaders.manualBlacklist);
  const suggestions = useData(loaders.suggestions);
  const loading = manual.loading || suggestions.loading;
  const error = manual.error || suggestions.error;

  return (
    <PageState loading={loading} error={error}>
      {manual.data && suggestions.data && <Content manual={manual.data} suggestions={suggestions.data} />}
    </PageState>
  );
}

function SegmentBadge({ seg }: { seg: string }) {
  const map: Record<string, string> = {
    HIGH: "bg-red-100 text-red-700",
    MEDIUM: "bg-amber-100 text-amber-700",
    LOW: "bg-slate-100 text-slate-600",
  };
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${map[seg] ?? map.LOW}`}>{seg}</span>;
}

function Content({ manual, suggestions }: { manual: ManualBlacklistEntry[]; suggestions: MerchantSuggestion[] }) {
  const [tab, setTab] = useState<"manual" | "dynamic">("manual");
  const [action, setAction] = useState("all");
  const [segment, setSegment] = useState("all");
  const [minLaundering, setMinLaundering] = useState(0);

  const flagged = useMemo(() => suggestions.filter((s) => s.blacklist_recommendation === "blacklist"), [suggestions]);

  const filteredSuggestions = useMemo(() => {
    return flagged.filter((s) => {
      if (action !== "all" && s.recommended_action !== action) return false;
      if (segment !== "all" && s.merchant_risk_segment !== segment) return false;
      if (s.laundering_risk_score < minLaundering) return false;
      return true;
    });
  }, [flagged, action, segment, minLaundering]);

  const manualCols: Column<ManualBlacklistEntry>[] = [
    { key: "merchant_id", header: "Merchant ID", className: "font-mono text-xs" },
    { key: "Merch_ID_DE42", header: "DE42", className: "font-mono text-xs" },
    { key: "blacklist_reason", header: "Reason" },
    { key: "effective_date", header: "Effective", className: "text-xs" },
    { key: "action", header: "Action", render: (r) => <ActionBadge action={r.action} /> },
  ];

  const dynCols: Column<MerchantSuggestion>[] = [
    { key: "merchant_id", header: "Merchant ID", className: "font-mono text-xs" },
    { key: "merchant_name", header: "Name", className: "text-xs" },
    { key: "merchant_risk_segment", header: "Segment", render: (r) => <SegmentBadge seg={r.merchant_risk_segment} /> },
    { key: "laundering_risk_score", header: "Laundering", align: "right", sortValue: (r) => r.laundering_risk_score, render: (r) => fmtNum(r.laundering_risk_score, 1) },
    { key: "fraud_rate", header: "Fraud %", align: "right", sortValue: (r) => r.fraud_rate, render: (r) => fmtPct(r.fraud_rate, 1) },
    { key: "chargeback_rate_30d", header: "CB 30d %", align: "right", sortValue: (r) => r.chargeback_rate_30d, render: (r) => fmtPct(r.chargeback_rate_30d, 1) },
    { key: "volume_spike_rate", header: "Vol Spike %", align: "right", sortValue: (r) => r.volume_spike_rate, render: (r) => fmtPct(r.volume_spike_rate, 1) },
    { key: "recommended_action", header: "Action", render: (r) => <ActionBadge action={r.recommended_action} />, sortValue: (r) => r.recommended_action },
    { key: "reason_codes", header: "Reason Codes", render: (r) => <ReasonCodeList codes={splitReasonCodes(r.reason_codes)} /> },
  ];

  const select = (val: string, set: (v: string) => void, opts: { value: string; label: string }[]) => (
    <select
      value={val}
      onChange={(e) => set(e.target.value)}
      className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm outline-none focus:border-blue-500"
    >
      {opts.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );

  return (
    <>
      <PageHeader
        title="Merchant Blacklist"
        badge="Step 1 enhancement"
        description="A real-time merchant blacklist with two sources: an authoritative manual list maintained by operators, and dynamic suggestions generated from merchant risk telemetry."
      />

      {/* Tabs */}
      <div className="mb-4 inline-flex rounded-lg border border-slate-200 bg-[#161619] p-1 shadow-sm">
        <button
          onClick={() => setTab("manual")}
          className={`rounded-md px-4 py-1.5 text-sm font-medium ${tab === "manual" ? "bg-yellow-400 text-black" : "text-slate-600 hover:bg-slate-50"}`}
        >
          Manual Blacklist ({manual.length})
        </button>
        <button
          onClick={() => setTab("dynamic")}
          className={`rounded-md px-4 py-1.5 text-sm font-medium ${tab === "dynamic" ? "bg-yellow-400 text-black" : "text-slate-600 hover:bg-slate-50"}`}
        >
          Dynamic Suggestions ({flagged.length})
        </button>
      </div>

      {tab === "manual" ? (
        <Card title="Manual / Operator Blacklist" subtitle="Authoritative at scoring time — decline forces decline, step_up forces ≥ step_up">
          <DataTable columns={manualCols} rows={manual} searchKeys={(r) => `${r.merchant_id} ${r.blacklist_reason} ${r.action}`} pageSize={10} />
        </Card>
      ) : (
        <Card
          title="Dynamic Blacklist Suggestions"
          subtitle="Merchants flagged from risk telemetry (≥2 risk signals). Advisory — reviewed before promotion to the manual list."
          right={
            <div className="flex flex-wrap items-center gap-2">
              {select(action, setAction, [
                { value: "all", label: "All actions" },
                { value: "decline", label: "Decline" },
                { value: "step_up", label: "Step-up" },
                { value: "review", label: "Review" },
              ])}
              {select(segment, setSegment, [
                { value: "all", label: "All segments" },
                { value: "HIGH", label: "High" },
                { value: "MEDIUM", label: "Medium" },
                { value: "LOW", label: "Low" },
              ])}
              <label className="flex items-center gap-1.5 text-xs text-slate-500">
                Min laundering
                <input
                  type="number"
                  value={minLaundering}
                  min={0}
                  max={100}
                  step={10}
                  onChange={(e) => setMinLaundering(Number(e.target.value))}
                  className="w-16 rounded border border-slate-300 px-1.5 py-1 text-sm"
                />
              </label>
            </div>
          }
        >
          <DataTable
            columns={dynCols}
            rows={filteredSuggestions}
            searchKeys={(r) => `${r.merchant_id} ${r.merchant_name} ${r.reason_codes}`}
            pageSize={10}
          />
        </Card>
      )}
    </>
  );
}
