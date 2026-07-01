# Run Guide — End-to-End Pipeline + Dashboard

This is the single, sequential guide to run the whole Card & Payment Fraud
Detection POC from scratch and open the dashboard.

It covers:

1. Step 1 — Real-Time Fraud Triage (train the ML model)
2. Client add-on — BIN attack, same-IP repetition, merchant blacklist
3. Dashboard data preparation
4. React dashboard (view in browser)

> Detailed docs per component: [README_STEP1.md](README_STEP1.md),
> [README_CLIENT_REQUIREMENT.md](README_CLIENT_REQUIREMENT.md),
> [README_DASHBOARD.md](README_DASHBOARD.md).

---

## 0. Prerequisites (one-time)

You need **Python** (with the bundled `venv/`) and **Node.js + npm** (for the dashboard).

```
Python  : 3.12  (project venv at ./venv)
Node.js : 18+   (tested on Node 24)
```

Run every command **from the project root**:
`c:\Users\shubham.s\Downloads\fraud_detection`

### 0a. Python dependencies

The project ships a virtual environment in `./venv`. The pipeline needs
`pandas`, `scikit-learn` and `joblib`. If they are not already installed:

**Windows PowerShell**
```powershell
.\venv\Scripts\python.exe -m pip install pandas scikit-learn joblib
```

**Git Bash**
```bash
venv/Scripts/python.exe -m pip install pandas scikit-learn joblib
```

> All Python commands below use `venv/Scripts/python.exe` so you do not need to
> "activate" the venv. (xgboost/lightgbm are intentionally **not** required —
> the models use scikit-learn only.)

---

## 1. Train the Step 1 fraud model

Trains Logistic Regression + Random Forest, tunes triage thresholds, and saves
the model bundle.

**PowerShell**
```powershell
.\venv\Scripts\python.exe src\train_step1_model.py
```

**Git Bash**
```bash
venv/Scripts/python.exe src/train_step1_model.py
```

**Produces**
- `outputs/step1_fraud_model.joblib`  (trained model + tuned thresholds)
- `outputs/model_metrics.json`
- `outputs/feature_list.json`
- `outputs/sample_scored_transactions.csv`

Expect console output ending with test-set ROC AUC / PR AUC / precision / recall
and the chosen triage thresholds. Takes ~1–2 minutes.

---

## 2. Run the client add-on pipeline

Runs BIN attack detection, same-IP repetitive-auth detection, and merchant
blacklist suggestions; writes alert tables + the watchlist lookups that Step 1
scoring consumes.

**PowerShell**
```powershell
.\venv\Scripts\python.exe src\client_requirement_pipeline.py
```

**Git Bash**
```bash
venv/Scripts/python.exe src/client_requirement_pipeline.py
```

**Produces**
- `outputs/bin_attack_alerts.csv`
- `outputs/ip_repetitive_authorisation_alerts.csv`
- `outputs/merchant_blacklist_suggestions.csv`
- `outputs/client_requirement_summary.json`
- `outputs/lookup_bin_attack_subbins.json`, `outputs/lookup_repetitive_ips.json`

Prints a summary (current data: 7 BIN alerts, 84 IP alerts, 3 manual + 76
dynamic merchant entries).

> The manual blacklist at `config/merchant_blacklist.csv` already exists and is
> read by both scoring and the dashboard — no action needed.

---

## 3. Prepare the dashboard data

Converts all of the above outputs into frontend-friendly JSON and builds the KPI
summary, the combined alert queue, and the real before/after scoring simulator.

**PowerShell**
```powershell
.\venv\Scripts\python.exe scripts\prepare_dashboard_data.py
```

**Git Bash**
```bash
venv/Scripts/python.exe scripts/prepare_dashboard_data.py
```

**Produces** (in `frontend/public/data/`)
- `dashboard_summary.json`, `model_metrics.json`
- `sample_scored_transactions.json`
- `bin_attack_alerts.json`, `ip_repetitive_authorisation_alerts.json`
- `merchant_blacklist_suggestions.json`, `manual_merchant_blacklist.json`
- `combined_alert_queue.json`, `overlay_simulator.json`

> Re-run this step any time you re-run steps 1–2 so the dashboard shows fresh data.

---

## 4. Launch the dashboard

**First time only — install Node packages:**

```bash
cd frontend
npm install
```

**Start the dev server:**

```bash
npm run dev
```

Then open the printed URL in your browser:

### ▶ http://localhost:5174/

You should land on the **Executive Overview**. Use the left sidebar to navigate:
Step 1 Triage · Overlay & Simulator · BIN Attack · Same-IP Repetitive Auth ·
Merchant Blacklist · Analyst Alert Queue · Business Summary.

To stop the server: press `Ctrl + C` in that terminal.

---

## Quick copy-paste (Git Bash, from project root)

```bash
# 1-3: Python pipeline + dashboard data
venv/Scripts/python.exe src/train_step1_model.py
venv/Scripts/python.exe src/client_requirement_pipeline.py
venv/Scripts/python.exe scripts/prepare_dashboard_data.py

# 4: dashboard
cd frontend
npm install      # first run only
npm run dev
# open http://localhost:5174/
```

## Quick copy-paste (PowerShell, from project root)

```powershell
.\venv\Scripts\python.exe src\train_step1_model.py
.\venv\Scripts\python.exe src\client_requirement_pipeline.py
.\venv\Scripts\python.exe scripts\prepare_dashboard_data.py

cd frontend
npm install      # first run only
npm run dev
# open http://localhost:5174/
```

---

## Run order & dependencies (why this sequence)

```
train_step1_model.py ──► step1_fraud_model.joblib ─┐
                                                   ├─► prepare_dashboard_data.py ──► frontend/public/data/*.json ──► npm run dev
client_requirement_pipeline.py ──► outputs/*.csv ──┘            (overlay simulator
        (needs the model for the scoring overlay)                needs the model)
```

1. **Step 1 must run first** — it produces the model the other steps use.
2. **Client pipeline second** — its detectors feed the Step 1 scoring overlay and
   the dashboard alert pages.
3. **Dashboard prep third** — it reads everything above (and loads the model to
   build the live before/after simulator).
4. **`npm run dev` last** — serves the prepared JSON.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: pandas` | Run the pip install in step 0a. |
| Dashboard page shows "Could not load data" | Run step 3 (`prepare_dashboard_data.py`) from the project root. |
| Overlay simulator is empty | Step 1 model missing — run step 1, then re-run step 3. |
| `npm` not found | Install Node.js 18+ and reopen the terminal. |
| Port 5174 busy | Stop the other process, or edit `server.port` in `frontend/vite.config.ts`. |
| Blank page after editing | Check the terminal running `npm run dev` for errors. |

---

## What you get

| Layer | Output |
|---|---|
| Step 1 | Real-time triage: `approve` / `step_up` / `decline` with fraud probability, rule risk, reason codes |
| Client add-on | BIN attack alerts, same-IP repetition alerts, merchant blacklist (manual + dynamic) |
| Integration | All add-on signals overlaid back into Step 1 scoring |
| Dashboard | Executive KPIs, per-detector drill-downs, analyst queue, live scoring simulator, business summary |

All data is **synthetic** and for POC/demo purposes only.
