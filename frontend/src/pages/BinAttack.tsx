import { useState } from "react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import PageState from "../components/PageState";
import DataTable, { type Column } from "../components/DataTable";
import SeverityBadge from "../components/SeverityBadge";
import ReasonCodeList from "../components/ReasonCodeList";
import AlertDetailModal, { DetailGrid } from "../components/AlertDetailModal";
import NoteBanner from "../components/NoteBanner";
import { BarChartCard, type Datum } from "../components/Charts";
import { loaders, useData } from "../utils/dataLoaders";
import { fmtMoney, fmtPct, splitReasonCodes, titleCase } from "../utils/formatters";
import { SEVERITY_HEX } from "../utils/theme";
import type { BinAttackAlert } from "../types/fraud";

export default function BinAttack() {
  const { data, error, loading } = useData(loaders.binAttacks);
  return (
    <PageState loading={loading} error={error}>
      {data && <Content rows={data} />}
    </PageState>
  );
}

function Content({ rows }: { rows: BinAttackAlert[] }) {
  const [selected, setSelected] = useState<BinAttackAlert | null>(null);

  const topAttacked: Datum[] = [...rows]
    .sort((a, b) => b.transaction_count - a.transaction_count)
    .slice(0, 10)
    .map((r) => ({ name: String(r.SubBIN), value: r.transaction_count, color: SEVERITY_HEX[r.severity] }));

  const declineBySubbin: Datum[] = [...rows]
    .sort((a, b) => b.decline_rate - a.decline_rate)
    .slice(0, 10)
    .map((r) => ({ name: String(r.SubBIN), value: Math.round(r.decline_rate * 100) }));

  const columns: Column<BinAttackAlert>[] = [
    { key: "alert_id", header: "Alert", className: "font-mono text-xs" },
    { key: "SubBIN", header: "SubBIN", className: "font-mono", sortValue: (r) => r.SubBIN },
    { key: "severity", header: "Severity", render: (r) => <SeverityBadge severity={r.severity} />, sortValue: (r) => r.risk_score },
    { key: "risk_score", header: "Risk", align: "right", sortValue: (r) => r.risk_score, render: (r) => <span className="font-semibold">{r.risk_score}</span> },
    { key: "transaction_count", header: "Txns", align: "right", sortValue: (r) => r.transaction_count },
    { key: "unique_cards", header: "Cards", align: "right", sortValue: (r) => r.unique_cards },
    { key: "unique_ips", header: "IPs", align: "right", sortValue: (r) => r.unique_ips },
    { key: "decline_rate", header: "Decline %", align: "right", sortValue: (r) => r.decline_rate, render: (r) => fmtPct(r.decline_rate, 0) },
    { key: "avg_amount", header: "Avg Amt", align: "right", sortValue: (r) => r.avg_amount, render: (r) => fmtMoney(r.avg_amount) },
    { key: "recommended_control", header: "Control", render: (r) => <span className="text-xs font-medium text-slate-600">{titleCase(r.recommended_control)}</span> },
  ];

  return (
    <>
      <PageHeader
        title="BIN / SubBIN Attack Detection"
        badge="Step 3 (partial)"
        description="Detects card-enumeration attacks against a BIN range: many unique cards probed on one SubBIN, low-value repeated attempts, high decline rates and shared IP/device patterns."
      />

      <NoteBanner>
        On this synthetic dataset, attack velocity is carried by the pre-aggregated 1-hour counters
        (<code>ip_card_count_1h</code> / <code>ip_txn_count_1h</code>) rather than literal sub-second
        bursts. Each alert aggregates the attack-signature attempts on one SubBIN.
      </NoteBanner>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Top Attacked SubBINs" subtitle="By suspicious attempt volume">
          <BarChartCard data={topAttacked} />
        </Card>
        <Card title="Decline Rate by SubBIN" subtitle="Percent of attempts declined (probing signal)">
          <BarChartCard data={declineBySubbin} />
        </Card>
      </div>

      <Card title="BIN Attack Alerts" subtitle="Click a row for full drill-down" className="mt-4">
        <DataTable
          columns={columns}
          rows={rows}
          onRowClick={setSelected}
          searchKeys={(r) => `${r.alert_id} ${r.SubBIN} ${r.severity} ${r.reason_codes}`}
          pageSize={10}
        />
      </Card>

      <AlertDetailModal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `BIN Attack — SubBIN ${selected.SubBIN}` : ""}
        subtitle={selected ? `${selected.alert_id} · ${selected.severity}` : ""}
      >
        {selected && (
          <div className="space-y-4">
            <DetailGrid
              items={[
                { label: "Severity", value: <SeverityBadge severity={selected.severity} /> },
                { label: "Risk Score", value: selected.risk_score },
                { label: "Recommended Control", value: titleCase(selected.recommended_control) },
                { label: "Transactions", value: selected.transaction_count.toLocaleString() },
                { label: "Unique Cards", value: selected.unique_cards.toLocaleString() },
                { label: "Unique Merchants", value: selected.unique_merchants.toLocaleString() },
                { label: "Unique IPs", value: selected.unique_ips.toLocaleString() },
                { label: "Unique Devices", value: selected.unique_devices.toLocaleString() },
                { label: "Decline Rate", value: fmtPct(selected.decline_rate, 1) },
                { label: "Avg Amount", value: fmtMoney(selected.avg_amount) },
                { label: "Max IP Txn/1h", value: selected.max_ip_txn_count_1h },
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
