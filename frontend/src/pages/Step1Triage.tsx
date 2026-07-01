import { useMemo, useState } from "react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import PageState from "../components/PageState";
import DataTable, { type Column } from "../components/DataTable";
import ActionBadge from "../components/ActionBadge";
import ReasonCodeList from "../components/ReasonCodeList";
import { loaders, useData } from "../utils/dataLoaders";
import { fmtMoney, fmtNum, fmtPct, splitReasonCodes, titleCase } from "../utils/formatters";
import type { ModelMetrics, ScoredTransaction } from "../types/fraud";

export default function Step1Triage() {
  const metrics = useData(loaders.metrics);
  const scored = useData(loaders.scored);

  const loading = metrics.loading || scored.loading;
  const error = metrics.error || scored.error;

  return (
    <PageState loading={loading} error={error}>
      {metrics.data && scored.data && <Content metrics={metrics.data} rows={scored.data} />}
    </PageState>
  );
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-200">
      <p className="text-[11px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 text-lg font-bold tabular text-slate-800">{value}</p>
    </div>
  );
}

function ConfusionMatrix({ cm }: { cm: number[][] }) {
  const [[tn, fp], [fn, tp]] = cm;
  const cell = (v: number, label: string, tone: string) => (
    <div className={`rounded-lg p-3 text-center ${tone}`}>
      <p className="text-xs opacity-80">{label}</p>
      <p className="text-xl font-bold tabular">{v.toLocaleString()}</p>
    </div>
  );
  return (
    <div className="grid grid-cols-2 gap-2">
      {cell(tn, "True Negative", "bg-emerald-50 text-emerald-800")}
      {cell(fp, "False Positive", "bg-amber-50 text-amber-800")}
      {cell(fn, "False Negative", "bg-red-50 text-red-800")}
      {cell(tp, "True Positive", "bg-blue-50 text-blue-800")}
    </div>
  );
}

function Content({ metrics, rows }: { metrics: ModelMetrics; rows: ScoredTransaction[] }) {
  const best = metrics.best_model;
  const bestTest = metrics.model_results[best].test;

  const [action, setAction] = useState("all");
  const [scenario, setScenario] = useState("all");
  const [band, setBand] = useState("all");

  const scenarios = useMemo(
    () => Array.from(new Set(rows.map((r) => r.fraud_scenario))).sort(),
    [rows]
  );

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (action !== "all" && r.recommended_action !== action) return false;
      if (scenario !== "all" && r.fraud_scenario !== scenario) return false;
      if (band !== "all") {
        const s = r.final_risk_score;
        if (band === "approve" && !(s < 190)) return false;
        if (band === "step_up" && !(s >= 190 && s < 430)) return false;
        if (band === "decline" && !(s >= 430)) return false;
      }
      return true;
    });
  }, [rows, action, scenario, band]);

  const columns: Column<ScoredTransaction>[] = [
    {
      key: "transaction_id",
      header: "Transaction",
      render: (r) => <span className="font-mono text-xs">{r.transaction_id.slice(0, 10)}…</span>,
    },
    { key: "merchant_id", header: "Merchant", className: "font-mono text-xs" },
    { key: "Txn_Amt", header: "Amount", align: "right", sortValue: (r) => r.Txn_Amt, render: (r) => fmtMoney(r.Txn_Amt) },
    {
      key: "fraud_probability",
      header: "ML Prob",
      align: "right",
      sortValue: (r) => r.fraud_probability,
      render: (r) => fmtNum(r.fraud_probability, 3),
    },
    {
      key: "final_risk_score",
      header: "Risk Score",
      align: "right",
      sortValue: (r) => r.final_risk_score,
      render: (r) => <span className="font-semibold">{r.final_risk_score}</span>,
    },
    {
      key: "recommended_action",
      header: "Action",
      render: (r) => <ActionBadge action={r.recommended_action} />,
      sortValue: (r) => r.recommended_action,
    },
    {
      key: "actual_is_fraud",
      header: "Actual",
      align: "center",
      sortValue: (r) => r.actual_is_fraud,
      render: (r) =>
        r.actual_is_fraud ? (
          <span className="text-xs font-semibold text-red-600">FRAUD</span>
        ) : (
          <span className="text-xs text-slate-400">legit</span>
        ),
    },
    {
      key: "reason_codes",
      header: "Reason Codes",
      render: (r) => <ReasonCodeList codes={splitReasonCodes(r.reason_codes)} />,
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
        title="Step 1 — Real-Time Fraud Triage"
        badge="Step 1"
        description="Hybrid ML + rules scoring against each cardholder's behavioural profile. The selected model is chosen by validation PR AUC; metrics below are on the held-out test set."
      />

      {/* Model metrics */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title={`Model Performance — ${titleCase(best)}`} subtitle="Held-out test set (20,000 transactions)" className="lg:col-span-2">
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
            <MetricPill label="ROC AUC" value={fmtNum(bestTest.roc_auc, 3)} />
            <MetricPill label="PR AUC" value={fmtNum(bestTest.pr_auc, 3)} />
            <MetricPill label="Precision" value={fmtNum(bestTest.precision, 3)} />
            <MetricPill label="Recall" value={fmtNum(bestTest.recall, 3)} />
            <MetricPill label="F1" value={fmtNum(bestTest.f1, 3)} />
          </div>
          <div className="mt-4 overflow-x-auto thin-scroll">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="py-1.5 pr-4">Model</th>
                  <th className="px-3 text-right">ROC AUC</th>
                  <th className="px-3 text-right">PR AUC</th>
                  <th className="px-3 text-right">Precision</th>
                  <th className="px-3 text-right">Recall</th>
                  <th className="px-3 text-right">F1</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {Object.entries(metrics.model_results).map(([name, r]) => (
                  <tr key={name} className={name === best ? "bg-blue-50/40 font-medium" : ""}>
                    <td className="py-2 pr-4">
                      {titleCase(name)} {name === best && <span className="text-xs text-blue-600">★ selected</span>}
                    </td>
                    <td className="px-3 text-right tabular">{fmtNum(r.test.roc_auc, 3)}</td>
                    <td className="px-3 text-right tabular">{fmtNum(r.test.pr_auc, 3)}</td>
                    <td className="px-3 text-right tabular">{fmtNum(r.test.precision, 3)}</td>
                    <td className="px-3 text-right tabular">{fmtNum(r.test.recall, 3)}</td>
                    <td className="px-3 text-right tabular">{fmtNum(r.test.f1, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Triage thresholds — approve &lt; {metrics.triage_thresholds.step_up}, step-up{" "}
            {metrics.triage_thresholds.step_up}–{metrics.triage_thresholds.decline - 1}, decline ≥{" "}
            {metrics.triage_thresholds.decline}. Agreement with dataset recommended_action:{" "}
            {fmtPct(metrics.recommended_action_agreement)}.
          </p>
        </Card>

        <Card title="Confusion Matrix" subtitle={`${titleCase(best)} @ 0.5 · test set`}>
          <ConfusionMatrix cm={bestTest.confusion_matrix} />
          <div className="mt-3 space-y-1 text-xs text-slate-500">
            <p>Fraud caught in step-up + decline bands: {fmtPct(metrics.triage_test_evaluation.fraud_caught_step_up_or_decline)}</p>
            <p>Decline-band fraud rate: {fmtPct(metrics.triage_test_evaluation.fraud_rate_by_action.decline)}</p>
          </div>
        </Card>
      </div>

      {/* Scored transactions */}
      <Card
        title="Sample Scored Transactions"
        subtitle="Per-transaction triage with ML probability, final risk score and reason codes"
        className="mt-4"
        right={
          <div className="flex flex-wrap gap-2">
            {select(action, setAction, [
              { value: "all", label: "All actions" },
              { value: "approve", label: "Approve" },
              { value: "step_up", label: "Step-up" },
              { value: "decline", label: "Decline" },
            ])}
            {select(band, setBand, [
              { value: "all", label: "All risk bands" },
              { value: "approve", label: "Low (<190)" },
              { value: "step_up", label: "Medium (190-429)" },
              { value: "decline", label: "High (430+)" },
            ])}
            {select(scenario, setScenario, [
              { value: "all", label: "All scenarios" },
              ...scenarios.map((s) => ({ value: s, label: titleCase(s) })),
            ])}
          </div>
        }
      >
        <DataTable
          columns={columns}
          rows={filtered}
          searchKeys={(r) => `${r.transaction_id} ${r.merchant_id} ${r.cardholder_id} ${r.reason_codes ?? ""}`}
          pageSize={12}
        />
      </Card>
    </>
  );
}
