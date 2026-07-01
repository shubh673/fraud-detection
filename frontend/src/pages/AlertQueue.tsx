import { useMemo, useState } from "react";
import Card from "../components/Card";
import KpiCard from "../components/KpiCard";
import PageHeader from "../components/PageHeader";
import PageState from "../components/PageState";
import DataTable, { type Column } from "../components/DataTable";
import SeverityBadge from "../components/SeverityBadge";
import ReasonCodeList from "../components/ReasonCodeList";
import { loaders, useData } from "../utils/dataLoaders";
import { fmtInt, splitReasonCodes, titleCase } from "../utils/formatters";
import type { QueueAlert } from "../types/fraud";

const TYPE_LABEL: Record<string, string> = {
  BIN_ATTACK: "BIN Attack",
  IP_REPETITIVE: "Same-IP Repetition",
  MERCHANT_BLACKLIST: "Merchant Blacklist",
};

const TYPE_STYLE: Record<string, string> = {
  BIN_ATTACK: "bg-red-50 text-red-700 ring-red-200",
  IP_REPETITIVE: "bg-amber-50 text-amber-700 ring-amber-200",
  MERCHANT_BLACKLIST: "bg-indigo-50 text-indigo-700 ring-indigo-200",
};

const SEV_RANK: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

export default function AlertQueue() {
  const { data, error, loading } = useData(loaders.queue);
  return (
    <PageState loading={loading} error={error}>
      {data && <Content rows={data} />}
    </PageState>
  );
}

function Content({ rows }: { rows: QueueAlert[] }) {
  const [type, setType] = useState("all");
  const [severity, setSeverity] = useState("all");

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (type !== "all" && r.alert_type !== type) return false;
      if (severity !== "all" && r.severity !== severity) return false;
      return true;
    });
  }, [rows, type, severity]);

  const counts = useMemo(() => {
    return {
      total: rows.length,
      bin: rows.filter((r) => r.alert_type === "BIN_ATTACK").length,
      ip: rows.filter((r) => r.alert_type === "IP_REPETITIVE").length,
      merchant: rows.filter((r) => r.alert_type === "MERCHANT_BLACKLIST").length,
      critical: rows.filter((r) => r.severity === "CRITICAL").length,
    };
  }, [rows]);

  const columns: Column<QueueAlert>[] = [
    {
      key: "alert_type",
      header: "Type",
      sortValue: (r) => r.alert_type,
      render: (r) => (
        <span className={`rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TYPE_STYLE[r.alert_type]}`}>
          {TYPE_LABEL[r.alert_type]}
        </span>
      ),
    },
    { key: "entity_id", header: "Entity", className: "max-w-xs truncate text-xs", render: (r) => <span title={r.entity_id}>{r.entity_id}</span> },
    { key: "severity", header: "Severity", render: (r) => <SeverityBadge severity={r.severity} />, sortValue: (r) => SEV_RANK[r.severity] ?? 0 },
    { key: "risk_score", header: "Risk", align: "right", sortValue: (r) => r.risk_score, render: (r) => <span className="font-semibold">{r.risk_score}</span> },
    { key: "recommended_action", header: "Recommended Control", render: (r) => <span className="text-xs font-medium text-slate-600">{titleCase(r.recommended_action)}</span> },
    { key: "reason_codes", header: "Reason Codes", render: (r) => <ReasonCodeList codes={splitReasonCodes(r.reason_codes)} /> },
    {
      key: "status",
      header: "Status",
      render: (r) => (
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize text-slate-600">{r.status}</span>
      ),
    },
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
        title="Analyst Alert Queue"
        description="Unified, triageable queue combining BIN attack, same-IP repetition and merchant blacklist alerts — sorted and filterable for fraud-operations workflow."
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <KpiCard label="Total Alerts" value={fmtInt(counts.total)} accent="navy" />
        <KpiCard label="BIN Attack" value={fmtInt(counts.bin)} accent="red" />
        <KpiCard label="Same-IP Rep." value={fmtInt(counts.ip)} accent="amber" />
        <KpiCard label="Merchant" value={fmtInt(counts.merchant)} accent="indigo" />
        <KpiCard label="Critical" value={fmtInt(counts.critical)} accent="red" />
      </div>

      <Card
        title="Combined Alert Queue"
        subtitle="Sort by clicking a column header"
        className="mt-4"
        right={
          <div className="flex flex-wrap gap-2">
            {select(type, setType, [
              { value: "all", label: "All types" },
              { value: "BIN_ATTACK", label: "BIN Attack" },
              { value: "IP_REPETITIVE", label: "Same-IP Repetition" },
              { value: "MERCHANT_BLACKLIST", label: "Merchant Blacklist" },
            ])}
            {select(severity, setSeverity, [
              { value: "all", label: "All severities" },
              { value: "CRITICAL", label: "Critical" },
              { value: "HIGH", label: "High" },
              { value: "MEDIUM", label: "Medium" },
              { value: "LOW", label: "Low" },
            ])}
          </div>
        }
      >
        <DataTable
          columns={columns}
          rows={filtered}
          searchKeys={(r) => `${r.entity_id} ${r.alert_type} ${r.severity} ${r.reason_codes}`}
          pageSize={15}
        />
      </Card>
    </>
  );
}
