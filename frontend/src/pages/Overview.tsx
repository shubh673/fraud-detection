import Card from "../components/Card";
import KpiCard from "../components/KpiCard";
import PageHeader from "../components/PageHeader";
import PageState from "../components/PageState";
import { BarChartCard, DonutChartCard, HBarChartCard, type Datum } from "../components/Charts";
import { loaders, useData } from "../utils/dataLoaders";
import { fmtInt, fmtPct, titleCase } from "../utils/formatters";
import { ACTION_HEX, SEVERITY_HEX } from "../utils/theme";

export default function Overview() {
  const { data, error, loading } = useData(loaders.summary);

  return (
    <PageState loading={loading} error={error}>
      {data && <OverviewContent s={data} />}
    </PageState>
  );
}

function OverviewContent({ s }: { s: import("../types/fraud").DashboardSummary }) {
  const k = s.kpis;

  const actionData: Datum[] = Object.entries(s.charts.action_distribution).map(([name, value]) => ({
    name: titleCase(name),
    value,
    color: ACTION_HEX[name],
  }));

  const scenarioData: Datum[] = Object.entries(s.charts.fraud_scenario_distribution)
    .filter(([name]) => name !== "none")
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name: titleCase(name), value }));

  const severityData: Datum[] = Object.entries(s.charts.severity_distribution).map(([name, value]) => ({
    name,
    value,
    color: SEVERITY_HEX[name],
  }));

  const riskData: Datum[] = s.charts.risk_score_distribution.map((b) => ({
    name: b.band.split(" ")[0],
    value: b.count,
    color: ACTION_HEX[b.band.toLowerCase().includes("decline") ? "decline" : b.band.toLowerCase().includes("step") ? "step_up" : "approve"],
  }));

  const reasonData: Datum[] = s.charts.top_reason_codes.map((r) => ({ name: r.code, value: r.count }));

  return (
    <>
      <PageHeader
        title="Executive Overview"
        badge="Steps 1 + 3 add-on"
        description="Portfolio-level view of real-time fraud triage performance and the client add-on detectors (BIN attack, same-IP repetition, merchant blacklist) running on the synthetic EHI dataset."
      />

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="Transactions Scanned" value={fmtInt(k.transactions_scanned)} accent="navy" />
        <KpiCard label="Portfolio Fraud Rate" value={fmtPct(k.fraud_rate)} accent="red" />
        <KpiCard label="Approve" value={fmtInt(k.approve)} sub="held-out test set" accent="emerald" />
        <KpiCard label="Step-up" value={fmtInt(k.step_up)} sub="held-out test set" accent="amber" />
        <KpiCard label="Decline" value={fmtInt(k.decline)} sub="held-out test set" accent="red" />
        <KpiCard label="Critical Alerts" value={fmtInt(k.critical_alerts)} accent="red" />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="BIN Attack Alerts" value={fmtInt(k.bin_attack_alerts)} accent="red" />
        <KpiCard label="Repetitive IP Alerts" value={fmtInt(k.ip_repetitive_alerts)} accent="amber" />
        <KpiCard label="Manual Blacklist" value={fmtInt(k.manual_blacklist)} sub="merchants" accent="navy" />
        <KpiCard label="Dynamic Suggestions" value={fmtInt(k.dynamic_suggestions)} sub="merchants flagged" accent="indigo" />
        <KpiCard label="High Severity" value={fmtInt(k.high_alerts)} accent="amber" />
        <KpiCard label="Best Model" value={titleCase(s.best_model)} sub="selected by PR AUC" accent="slate" />
      </div>

      {/* Charts */}
      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Recommended Action Distribution" subtitle="Triage decisions on the 20k held-out test set">
          <DonutChartCard data={actionData} />
        </Card>
        <Card title="Alert Severity Distribution" subtitle="BIN attack + same-IP repetitive alerts">
          <DonutChartCard data={severityData} />
        </Card>
        <Card title="Fraud Scenario Distribution" subtitle="Injected fraud scenarios across 100k transactions (excl. none)">
          <BarChartCard data={scenarioData} />
        </Card>
        <Card title="Risk Score Bands" subtitle="Final risk score on the scored sample">
          <BarChartCard data={riskData} />
        </Card>
        <Card title="Top Reason Codes" subtitle="Most frequent signals across all detectors" className="lg:col-span-2">
          <HBarChartCard data={reasonData} height={320} />
        </Card>
      </div>
    </>
  );
}
