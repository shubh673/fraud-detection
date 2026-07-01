import { useState } from "react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import PageState from "../components/PageState";
import DataTable, { type Column } from "../components/DataTable";
import SeverityBadge from "../components/SeverityBadge";
import ReasonCodeList from "../components/ReasonCodeList";
import AlertDetailModal, { DetailGrid } from "../components/AlertDetailModal";
import NoteBanner from "../components/NoteBanner";
import { HBarChartCard, DonutChartCard, type Datum } from "../components/Charts";
import { loaders, useData } from "../utils/dataLoaders";
import { fmtMoney, shortHash, splitReasonCodes, titleCase } from "../utils/formatters";
import { SEVERITY_HEX } from "../utils/theme";
import type { IpRepetitionAlert } from "../types/fraud";

export default function IpRepetition() {
  const { data, error, loading } = useData(loaders.ipAlerts);
  return (
    <PageState loading={loading} error={error}>
      {data && <Content rows={data} />}
    </PageState>
  );
}

function Content({ rows }: { rows: IpRepetitionAlert[] }) {
  const [selected, setSelected] = useState<IpRepetitionAlert | null>(null);

  const topRisky: Datum[] = [...rows]
    .sort((a, b) => b.max_ip_txn_count_1h - a.max_ip_txn_count_1h)
    .slice(0, 10)
    .map((r) => ({ name: shortHash(r.ip_address_hash, 8), value: r.max_ip_txn_count_1h, color: SEVERITY_HEX[r.severity] }));

  const bySeverity = rows.reduce<Record<string, number>>((acc, r) => {
    acc[r.severity] = (acc[r.severity] ?? 0) + r.transaction_count;
    return acc;
  }, {});
  const severityData: Datum[] = Object.entries(bySeverity).map(([name, value]) => ({
    name,
    value,
    color: SEVERITY_HEX[name],
  }));

  const columns: Column<IpRepetitionAlert>[] = [
    { key: "ip_address_hash", header: "IP Hash", className: "font-mono text-xs", render: (r) => shortHash(r.ip_address_hash, 14) },
    { key: "severity", header: "Severity", render: (r) => <SeverityBadge severity={r.severity} />, sortValue: (r) => r.risk_score },
    { key: "risk_score", header: "Risk", align: "right", sortValue: (r) => r.risk_score, render: (r) => <span className="font-semibold">{r.risk_score}</span> },
    { key: "transaction_count", header: "Txns", align: "right", sortValue: (r) => r.transaction_count },
    { key: "unique_cardholders", header: "Cards", align: "right", sortValue: (r) => r.unique_cardholders },
    { key: "unique_subbins", header: "SubBINs", align: "right", sortValue: (r) => r.unique_subbins },
    { key: "max_transactions_per_10_seconds", header: "Max/10s", align: "right", sortValue: (r) => r.max_transactions_per_10_seconds },
    { key: "max_ip_txn_count_1h", header: "Max txn/1h", align: "right", sortValue: (r) => r.max_ip_txn_count_1h },
    { key: "recommended_control", header: "Control", render: (r) => <span className="text-xs font-medium text-slate-600">{titleCase(r.recommended_control)}</span> },
  ];

  return (
    <>
      <PageHeader
        title="Same-IP Repetitive Authorisation"
        badge="Step 3 (partial)"
        description="Detects an IP address issuing many authorisations in a short period — a hallmark of card-testing and enumeration. Escalates when one IP spans multiple cardholders, merchants or SubBINs."
      />

      <NoteBanner tone="warn">
        Current synthetic data uses pre-aggregated 1-hour velocity counters (normal peaks ~9 txns/hour;
        attack IPs reach 80–160). The literal second-level rolling-window logic (3+/10s, 5+/30s, 10+/60s)
        is implemented and will activate automatically with production timestamp bursts — see the
        <code> WINDOW_*</code> reason codes and <code>max/10s</code> column.
      </NoteBanner>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Top Risky IPs" subtitle="By peak transactions per IP-hour">
          <HBarChartCard data={topRisky} />
        </Card>
        <Card title="Transaction Volume by IP Severity" subtitle="Total transactions across alerted IPs">
          <DonutChartCard data={severityData} />
        </Card>
      </div>

      <Card title="Repetitive IP Alerts" subtitle="Click a row for full drill-down" className="mt-4">
        <DataTable
          columns={columns}
          rows={rows}
          onRowClick={setSelected}
          searchKeys={(r) => `${r.ip_address_hash} ${r.severity} ${r.reason_codes}`}
          pageSize={10}
        />
      </Card>

      <AlertDetailModal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? "Same-IP Repetitive Authorisation" : ""}
        subtitle={selected ? `${selected.alert_id} · ${selected.severity}` : ""}
      >
        {selected && (
          <div className="space-y-4">
            <p className="break-all rounded bg-slate-50 px-2 py-1.5 font-mono text-xs text-slate-600 ring-1 ring-inset ring-slate-200">
              {selected.ip_address_hash}
            </p>
            <DetailGrid
              items={[
                { label: "Severity", value: <SeverityBadge severity={selected.severity} /> },
                { label: "Risk Score", value: selected.risk_score },
                { label: "Recommended Control", value: titleCase(selected.recommended_control) },
                { label: "Transactions", value: selected.transaction_count.toLocaleString() },
                { label: "Unique Cardholders", value: selected.unique_cardholders.toLocaleString() },
                { label: "Unique Merchants", value: selected.unique_merchants.toLocaleString() },
                { label: "Unique SubBINs", value: selected.unique_subbins.toLocaleString() },
                { label: "Unique Devices", value: selected.unique_devices.toLocaleString() },
                { label: "Total Amount", value: fmtMoney(selected.total_amount) },
                { label: "Max Txns / 10s", value: selected.max_transactions_per_10_seconds },
                { label: "Max IP Txn / 1h", value: selected.max_ip_txn_count_1h },
                { label: "Window Start", value: <span className="text-xs">{selected.alert_start_time}</span> },
                { label: "Window End", value: <span className="text-xs">{selected.alert_end_time}</span> },
              ]}
            />
            <div>
              <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-400">Reason Codes</p>
              <ReasonCodeList codes={splitReasonCodes(selected.reason_codes)} />
            </div>
          </div>
        )}
      </AlertDetailModal>
    </>
  );
}
