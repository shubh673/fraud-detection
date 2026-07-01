import { useState } from "react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import PageState from "../components/PageState";
import ActionBadge from "../components/ActionBadge";
import ReasonCodeList from "../components/ReasonCodeList";
import { loaders, useData } from "../utils/dataLoaders";
import { fmtMoney, titleCase } from "../utils/formatters";
import type { OverlayScenario, ScoreResult } from "../types/fraud";

const OVERLAY_DOCS: { code: string; desc: string }[] = [
  { code: "BLACKLISTED_MERCHANT", desc: "Merchant on the manual blacklist. action=decline forces decline; step_up/review forces ≥ step-up." },
  { code: "HIGH_RISK_MERCHANT_BLACKLIST_SUGGESTED", desc: "Merchant flagged by the dynamic suggestion engine. Adds risk points." },
  { code: "BIN_ATTACK_PATTERN", desc: "Transaction's SubBIN is on the BIN-attack watchlist. Adds risk points." },
  { code: "SAME_IP_REPETITIVE_AUTH", desc: "Transaction's IP is on the repetitive-auth watchlist. Adds risk points." },
];

export default function OverlaySimulator() {
  const { data, error, loading } = useData(loaders.simulator);
  return (
    <PageState loading={loading} error={error}>
      {data && (data.length ? <Content scenarios={data} /> : <Empty />)}
    </PageState>
  );
}

function Empty() {
  return (
    <Card title="Overlay Simulator">
      <p className="text-sm text-slate-500">
        No simulator scenarios were generated. Ensure the trained model exists and re-run{" "}
        <code className="rounded bg-slate-100 px-1">python scripts/prepare_dashboard_data.py</code>.
      </p>
    </Card>
  );
}

function ScoreColumn({ title, result, tone }: { title: string; result: ScoreResult; tone: "slate" | "blue" }) {
  const ring = tone === "blue" ? "ring-blue-200 bg-blue-50/40" : "ring-slate-200 bg-slate-50/60";
  return (
    <div className={`rounded-xl p-4 ring-1 ring-inset ${ring}`}>
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <div className="space-y-2.5">
        <Row label="Fraud probability" value={result.fraud_probability.toFixed(3)} />
        <Row label="Rule risk score" value={String(result.rule_risk_score)} />
        <Row label="Final risk score" value={<span className="text-lg font-bold">{result.final_risk_score}</span>} />
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">Recommended action</span>
          <ActionBadge action={result.recommended_action} />
        </div>
      </div>
      <div className="mt-3">
        <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">Reason codes</p>
        <ReasonCodeList codes={result.reason_codes} emptyText="none" />
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="tabular font-semibold text-slate-800">{value}</span>
    </div>
  );
}

function Content({ scenarios }: { scenarios: OverlayScenario[] }) {
  const [idx, setIdx] = useState(0);
  const sc = scenarios[idx];
  const changed = sc.base.recommended_action !== sc.final.recommended_action;

  return (
    <>
      <PageHeader
        title="Integrated Step 1 Overlay & Scoring Simulator"
        badge="Step 1 + Add-on"
        description="Shows how the client add-on overlays change the Step 1 decision. Each scenario is scored twice against the real model: Step 1 only, then Step 1 + overlays."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Scenario picker */}
        <Card title="Choose a Transaction" subtitle="Precomputed from the live model" className="lg:col-span-1">
          <div className="space-y-1.5">
            {scenarios.map((s, i) => (
              <button
                key={s.id}
                onClick={() => setIdx(i)}
                className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                  i === idx ? "border-blue-500 bg-blue-50 text-blue-900" : "border-slate-200 hover:bg-slate-50"
                }`}
              >
                <span className="block font-medium">{s.label}</span>
                <span className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
                  <ActionBadge action={s.base.recommended_action} />
                  <span>→</span>
                  <ActionBadge action={s.final.recommended_action} />
                </span>
              </button>
            ))}
          </div>
        </Card>

        {/* Before / after */}
        <div className="space-y-4 lg:col-span-2">
          <Card title={sc.label} subtitle="Transaction context">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
              <Field label="Amount" value={fmtMoney(sc.transaction.Txn_Amt)} />
              <Field label="Country" value={sc.transaction.Txn_Ctry || "—"} />
              <Field label="Channel" value={sc.transaction.is_online ? "Online / CNP" : "In-person"} />
              <Field label="Scenario" value={titleCase(sc.transaction.fraud_scenario || "none")} />
              <Field label="Merchant" value={<span className="font-mono text-xs">{sc.transaction.merchant_id}</span>} />
              <Field label="SubBIN" value={<span className="font-mono text-xs">{sc.transaction.SubBIN}</span>} />
              <Field
                label="IP hash"
                value={<span className="font-mono text-xs">{sc.transaction.ip_address_hash.slice(0, 12)}…</span>}
              />
              <Field
                label="Ground truth"
                value={sc.transaction.actual_is_fraud ? <span className="font-semibold text-red-600">FRAUD</span> : "legit"}
              />
            </dl>
          </Card>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <ScoreColumn title="Step 1 only (baseline)" result={sc.base} tone="slate" />
            <ScoreColumn title="Step 1 + client overlays" result={sc.final} tone="blue" />
          </div>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-800">Overlay impact</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {changed ? (
                    <>
                      Decision changed{" "}
                      <span className="font-semibold">{titleCase(sc.base.recommended_action)}</span> →{" "}
                      <span className="font-semibold text-blue-700">{titleCase(sc.final.recommended_action)}</span>{" "}
                      (risk {sc.base.final_risk_score} → {sc.final.final_risk_score}).
                    </>
                  ) : (
                    <>No change in final action — baseline already covered this case.</>
                  )}
                </p>
              </div>
              <div>
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">Triggered overlays</p>
                <ReasonCodeList codes={sc.overlay_reason_codes} emptyText="none" />
              </div>
            </div>
          </Card>
        </div>
      </div>

      <Card title="How the overlay works" subtitle="Four add-on reason codes layered onto Step 1 scoring" className="mt-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {OVERLAY_DOCS.map((d) => (
            <div key={d.code} className="rounded-lg bg-indigo-50/50 p-3 ring-1 ring-inset ring-indigo-100">
              <p className="text-xs font-semibold text-indigo-700">{d.code}</p>
              <p className="mt-1 text-xs text-slate-600">{d.desc}</p>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 font-semibold text-slate-800">{value}</dd>
    </div>
  );
}
