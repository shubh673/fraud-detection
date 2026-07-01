# Fraud Detection Dashboard — Client Showcase UI

An interactive React + TypeScript dashboard that visualises the Card & Payment
Fraud Detection POC for client stakeholders and fraud analysts. It is a
**read-only presentation layer** built entirely on top of the existing pipeline
outputs — it does **not** modify or re-run any Step 1 / client-add-on module.

```
Python pipeline outputs ──► scripts/prepare_dashboard_data.py ──► frontend/public/data/*.json ──► React dashboard
```

---

## What the dashboard shows

| Page | Purpose | Maps to |
|---|---|---|
| **Executive Overview** | KPI cards + charts: action distribution, fraud scenarios, severity, risk bands, top reason codes | All |
| **Step 1 — Fraud Triage** | Model metrics (ROC/PR AUC, precision/recall/F1), confusion matrix, filterable scored-transaction table with reason codes | Step 1 |
| **Overlay & Simulator** | Live before/after scoring (Step 1 only vs Step 1 + overlays) for curated transactions | Step 1 + add-on |
| **BIN Attack Detection** | Alert table + drill-down modal, top attacked SubBINs, decline-rate chart | Step 3 (partial) |
| **Same-IP Repetitive Auth** | Alert table + drill-down, top risky IPs, volume-by-severity | Step 3 (partial) |
| **Merchant Blacklist** | Manual blacklist tab + dynamic suggestions tab with filters | Step 1 enhancement |
| **Analyst Alert Queue** | Unified, sortable/filterable queue across all three detectors | Operations |
| **Business Summary** | Capability → requirement mapping, what was built, limitations | All |

### Severity & action styling
Severity badges (`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`) and action badges
(`approve` / `step_up` / `decline` / `review`) are colour-coded consistently.
Reason codes from the **client add-on overlay** (`BLACKLISTED_MERCHANT`,
`HIGH_RISK_MERCHANT_BLACKLIST_SUGGESTED`, `BIN_ATTACK_PATTERN`,
`SAME_IP_REPETITIVE_AUTH`) are highlighted in indigo so the enhancement is
visible at a glance.

---

## How it maps to client requirements

- **Real-time fraud triage** → Step 1 Triage + Overview KPIs/metrics.
- **BIN attack detection** → BIN Attack page (Step 3 partial).
- **Same-IP repetitive authorisation** → Same-IP page (Step 3 partial).
- **Merchant blacklist (manual + dynamic)** → Merchant Blacklist page (Step 1 enhancement).
- **Overlay integration** → Overlay & Simulator page shows the four add-on reason
  codes changing the Step 1 decision, scored against the **real trained model**.

---

## How to prepare data

From the **project root** (uses the existing Python venv):

```bash
python scripts/prepare_dashboard_data.py
# or explicitly:
venv/Scripts/python.exe scripts/prepare_dashboard_data.py
```

This reads `outputs/`, `config/merchant_blacklist.csv` and the enriched dataset,
and writes JSON to `frontend/public/data/`. The **overlay simulator** scores a
handful of curated transactions through the real model bundle to produce genuine
before/after results (it degrades gracefully to an empty list if the model is
missing).

Re-run this script whenever the Python pipeline is re-run, so the dashboard
reflects fresh outputs.

---

## How to run locally

```bash
cd frontend
npm install
npm run dev
```

Then open the printed URL — by default:

**http://localhost:5174/**

Production build (optional): `npm run build` then `npm run preview`.

---

## Files used

Generated into `frontend/public/data/` by the prep script:

| File | Source |
|---|---|
| `dashboard_summary.json` | KPI counts + chart distributions (built) |
| `model_metrics.json` | `outputs/model_metrics.json` |
| `sample_scored_transactions.json` | `outputs/sample_scored_transactions.csv` |
| `bin_attack_alerts.json` | `outputs/bin_attack_alerts.csv` |
| `ip_repetitive_authorisation_alerts.json` | `outputs/ip_repetitive_authorisation_alerts.csv` |
| `merchant_blacklist_suggestions.json` | `outputs/merchant_blacklist_suggestions.csv` |
| `manual_merchant_blacklist.json` | `config/merchant_blacklist.csv` |
| `combined_alert_queue.json` | built from the three alert sources |
| `overlay_simulator.json` | real model scoring (Step 1 vs Step 1 + overlays) |

### Frontend structure

```
frontend/
  src/
    App.tsx, main.tsx
    components/   KpiCard, Card, DataTable, SeverityBadge, ActionBadge,
                  ReasonCodeList, AlertDetailModal, Charts, Layout, …
    pages/        Overview, Step1Triage, OverlaySimulator, BinAttack,
                  IpRepetition, MerchantBlacklist, AlertQueue, BusinessSummary
    utils/        dataLoaders, formatters, theme
    types/        fraud.ts
  public/data/    *.json (generated)
scripts/
  prepare_dashboard_data.py
```

### Tech
- React 19 + TypeScript + Vite
- Tailwind CSS v4 (`@tailwindcss/vite`)
- Recharts (charts), React Router (navigation)
- No backend — all data is static JSON served from `public/data/`.

---

## Current data snapshot

| Metric | Value |
|---|---|
| Transactions scanned | 100,000 |
| BIN attack alerts | 7 (all CRITICAL) |
| Same-IP repetitive alerts | 84 |
| Manual blacklist / dynamic suggestions | 3 / 76 |
| Combined alert queue | 167 |
| Overlay simulator scenarios | 7 |

---

## Current limitations

- **Read-only / static.** The dashboard renders precomputed JSON. The scoring
  simulator uses precomputed model results (not a live API). Re-run the prep
  script to refresh after a pipeline run.
- **Synthetic data.** Counts and metrics are illustrative POC values.
- **Triage KPI counts** (approve / step-up / decline) are from the 20k held-out
  test set; the scored-transactions table shows the 200-row sample output.
- **No authentication / multi-user state.** Alert "status" is display-only.
- If a source file is missing, the prep script prints a warning and skips it; the
  corresponding page will show an empty state rather than failing.
