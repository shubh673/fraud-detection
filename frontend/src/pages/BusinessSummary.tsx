import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import PageState from "../components/PageState";
import { loaders, useData } from "../utils/dataLoaders";
import { fmtInt, fmtPct } from "../utils/formatters";
import type { DashboardSummary } from "../types/fraud";

interface CapRow {
  capability: string;
  clientAsk: string;
  step: string;
  stepTone: string;
  action: string;
}

const CAPABILITIES: CapRow[] = [
  {
    capability: "Real-Time Fraud Triage",
    clientAsk: "Score each authorisation and recommend approve / step-up / decline",
    step: "Step 1",
    stepTone: "bg-blue-100 text-blue-700",
    action: "Auto-approve clean traffic; challenge or block risky auths in milliseconds",
  },
  {
    capability: "BIN / SubBIN Attack Detection",
    clientAsk: "Detect card-enumeration attacks on a BIN range",
    step: "Step 3 (partial)",
    stepTone: "bg-red-100 text-red-700",
    action: "Throttle or block attacked SubBINs; open analyst case",
  },
  {
    capability: "Same-IP Repetitive Auth",
    clientAsk: "Detect many authorisations from one IP in a short window",
    step: "Step 3 (partial)",
    stepTone: "bg-amber-100 text-amber-700",
    action: "Rate-limit or block offending IPs; feed Step 1 overlay",
  },
  {
    capability: "Merchant Blacklist",
    clientAsk: "Manual blacklist + dynamic risk-based suggestions",
    step: "Step 1 enhancement",
    stepTone: "bg-indigo-100 text-indigo-700",
    action: "Decline/step-up blacklisted merchants; review suggested merchants",
  },
  {
    capability: "Step 1 Overlay Integration",
    clientAsk: "Feed all of the above back into real-time scoring",
    step: "Step 1 enhancement",
    stepTone: "bg-indigo-100 text-indigo-700",
    action: "One unified decision with explainable reason codes",
  },
];

const LIMITATIONS = [
  "All data is synthetic — metrics are illustrative and will not transfer directly to production.",
  "Attack velocity is carried by pre-aggregated 1-hour counters; literal second-level burst windows activate with real timestamps.",
  "SubBIN/IP watchlists are coarse for real-time use (no time-boxing yet) — production should expire entries.",
  "Detectors run in batch over a snapshot; production needs a streaming feature store.",
  "Rule weights and triage thresholds are tuned lightly and should be calibrated with fraud-ops against real loss/friction.",
];

export default function BusinessSummary() {
  const { data, error, loading } = useData(loaders.summary);
  return (
    <PageState loading={loading} error={error}>
      {data && <Content s={data} />}
    </PageState>
  );
}

function Content({ s }: { s: DashboardSummary }) {
  const k = s.kpis;
  return (
    <>
      <PageHeader
        title="Business Impact & Client Summary"
        description="What was delivered, which client ask each item satisfies, how it maps to the original POC roadmap, and what the fraud team can do with it."
      />

      {/* Headline impact */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat value={fmtInt(k.transactions_scanned)} label="Transactions scanned" />
        <Stat value={fmtInt(k.bin_attack_alerts + k.ip_repetitive_alerts)} label="Step 3 alerts raised" />
        <Stat value={fmtInt(k.manual_blacklist + k.dynamic_suggestions)} label="Merchants blacklisted / flagged" />
        <Stat value={fmtPct(s.fraud_caught_step_up_or_decline)} label="Fraud caught (step-up + decline)" />
      </div>

      <Card title="Capability → Requirement Mapping" className="mt-5">
        <div className="overflow-x-auto thin-scroll">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2.5">Capability</th>
                <th className="px-3 py-2.5">Client ask</th>
                <th className="px-3 py-2.5">Requirement step</th>
                <th className="px-3 py-2.5">Fraud-team action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {CAPABILITIES.map((c) => (
                <tr key={c.capability} className="align-top">
                  <td className="px-3 py-3 font-medium text-slate-800">{c.capability}</td>
                  <td className="px-3 py-3 text-slate-600">{c.clientAsk}</td>
                  <td className="px-3 py-3">
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${c.stepTone}`}>{c.step}</span>
                  </td>
                  <td className="px-3 py-3 text-slate-600">{c.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="What was implemented">
          <ul className="space-y-2 text-sm text-slate-600">
            <Li>Hybrid ML (Random Forest, selected by PR AUC) + deterministic rules for real-time triage.</Li>
            <Li>BIN/SubBIN attack detector producing severity-scored alerts and a SubBIN watchlist.</Li>
            <Li>Same-IP repetitive authorisation detector with watchlist + literal rolling-window logic.</Li>
            <Li>Merchant blacklist: authoritative manual list + dynamic risk-based suggestions.</Li>
            <Li>All four detectors feed back into Step 1 scoring as explainable overlay reason codes.</Li>
            <Li>This dashboard — executive KPIs, per-detector drill-downs, analyst queue and a live scoring simulator.</Li>
          </ul>
        </Card>

        <Card title="Current limitations">
          <ul className="space-y-2 text-sm text-slate-600">
            {LIMITATIONS.map((l) => (
              <Li key={l}>{l}</Li>
            ))}
          </ul>
        </Card>
      </div>

      <p className="mt-5 text-xs text-slate-400">
        Best model: {s.best_model} · Portfolio fraud rate {fmtPct(s.fraud_rate)} · Recommended-action agreement{" "}
        {fmtPct(s.recommended_action_agreement)} · Synthetic POC data only.
      </p>
    </>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-[#1c1c20] to-[#141417] p-4 shadow-sm">
      <p className="text-2xl font-bold tabular text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{label}</p>
    </div>
  );
}

function Li({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-2">
      <span className="mt-1 text-blue-500">▸</span>
      <span>{children}</span>
    </li>
  );
}
