# Card & Payment Fraud Detection POC

A working proof-of-concept that scores every card authorisation in **real time** and
recommends **approve / step-up / decline**, using a hybrid of a machine-learning model
and explainable business rules — plus three client-requested add-ons (BIN-attack
detection, same-IP repetitive-authorisation detection, and a merchant blacklist) that
feed back into the real-time score, all visualised in an interactive dashboard.

> This single README consolidates the previously separate docs (Step 1, client
> add-on, dashboard, run guide, pipeline explainer, and summary).

---

## Table of contents

1. [Executive summary](#1-executive-summary)
2. [Roadmap mapping](#2-roadmap-mapping)
3. [Quick start (run everything)](#3-quick-start-run-everything)
4. [Input datasets](#4-input-datasets)
5. [Component A — Step 1: Real-Time Fraud Triage](#5-component-a--step-1-real-time-fraud-triage)
6. [Component B — Client add-on detectors](#6-component-b--client-add-on-detectors)
7. [Component C — Dashboard](#7-component-c--dashboard)
8. [End-to-end data flow](#8-end-to-end-data-flow)
9. [Reason-code glossary](#9-reason-code-glossary)
10. [Consolidated limitations](#10-consolidated-limitations)
11. [Project layout](#11-project-layout)

---

## 1. Executive summary

> We score each card authorisation in real time and recommend **approve / step-up /
> decline**, using a hybrid of a machine-learning model and explainable business
> rules. On top of that we added three things the client specifically asked for —
> **BIN-attack detection**, **same-IP repetitive-authorisation detection**, and a
> **merchant blacklist** — and we feed all of those back into the real-time score.
> Everything is visualised in an interactive dashboard for analysts and stakeholders.

The POC has **three layers** that run in sequence:

```
   ┌──────────────────────────┐    ┌───────────────────────────┐    ┌──────────────────────┐
   │  A. STEP 1               │    │  B. CLIENT ADD-ON          │    │  C. DASHBOARD        │
   │  Real-time fraud triage  │──► │  BIN attack / Same-IP /    │──► │  React UI showcase   │
   │  (ML + rules)            │    │  Merchant blacklist        │    │                      │
   └──────────────────────────┘    └───────────────────────────┘    └──────────────────────┘
        produces a model               produces alerts + watchlists       reads everything as JSON
        + per-txn scoring              + feeds Step 1 scoring overlay      and visualises it
```

| Part | Question it answers | Output |
|---|---|---|
| **1. Real-time triage** (Step 1) | "Should we approve, challenge, or decline *this* authorisation, right now?" | A decision + risk score + reason codes per transaction |
| **2. Client add-on** (Step 3 slices + enhancement) | "Is a BIN under attack? Is one IP hammering us? Which merchants are risky?" | Alert lists + watchlists that also enrich the Step 1 score |
| **3. Dashboard** | "How do I see and act on all of this?" | An interactive web UI with KPIs, drill-downs, and an analyst queue |

**How the scoring works (plain English):**

```
   ML model gives a fraud probability  ┐
                                        ├──►  blended risk score (0–1000)  ──►  approve / step-up / decline
   Business rules add risk + reasons   ┘            ▲
                                                    │
        Client add-on overlays (blacklist, BIN, IP) │
        add risk or force a decision, with reasons ─┘
```

**Design choice:** Step 1 is intentionally **not agentic**. It is a practical,
explainable hybrid (ML score + rule score → blended risk → action). Every decision
carries human-readable *reason codes*.

**Key numbers (current synthetic run):**

| Metric | Value |
|---|---|
| Transactions scanned | **100,000** |
| Model quality (test ROC AUC / PR AUC) | **0.82 / 0.66** |
| Fraud caught in step-up + decline bands | **~73%** |
| Decline-band purity (share that is real fraud) | **~75%** |
| BIN-attack alerts | **7** SubBINs (all CRITICAL) |
| Same-IP repetitive alerts | **84** IPs |
| Merchant blacklist | **3 manual + 76 suggested** |
| Combined analyst queue | **167 alerts** |

---

## 2. Roadmap mapping

The full POC vision is 5 steps. This build delivers Step 1 and the client-requested
slices of Step 3 plus a Step 1 enhancement.

| Capability | Roadmap step | Status |
|---|---|---|
| Real-time fraud triage | Step 1 | ✅ Done |
| BIN / SubBIN attack detection | Step 3 (partial) | ✅ Done |
| Same-IP repetitive authorisation | Step 3 (partial) | ✅ Done |
| Merchant blacklist + scoring overlay | Step 1 enhancement | ✅ Done |
| Client-showcase dashboard | — | ✅ Done |
| Behaviour / compliance monitoring | Step 2 | ⏳ Not started |
| Merchant / transaction-laundering risk | Step 4 | ⏳ Not started |
| Regulatory reporting assembler | Step 5 | ⏳ Not started |

---

## 3. Quick start (run everything)

### Prerequisites

```
Python  : 3.12  (project venv at ./venv)
Node.js : 18+   (tested on Node 24)
```

Run every command **from the project root**. Python commands use
`venv/Scripts/python.exe` so you don't need to "activate" the venv.

**One-time Python dependencies** (if not already installed):

```powershell
# Windows PowerShell
.\venv\Scripts\python.exe -m pip install pandas scikit-learn joblib
```
```bash
# Git Bash
venv/Scripts/python.exe -m pip install pandas scikit-learn joblib
```
> xgboost/lightgbm are intentionally **not** required — the models use scikit-learn only.

### The four steps in order

```bash
# 1. Train the Step 1 model (ML + tuned triage thresholds)
venv/Scripts/python.exe src/train_step1_model.py

# 2. Run the three client add-on detectors
venv/Scripts/python.exe src/client_requirement_pipeline.py

# 3. Build the dashboard data (JSON in frontend/public/data/)
venv/Scripts/python.exe scripts/prepare_dashboard_data.py

# 4. Launch the dashboard
cd frontend
npm install        # first run only
npm run dev
# open http://localhost:5174/
```

PowerShell equivalent for steps 1–3:

```powershell
.\venv\Scripts\python.exe src\train_step1_model.py
.\venv\Scripts\python.exe src\client_requirement_pipeline.py
.\venv\Scripts\python.exe scripts\prepare_dashboard_data.py
```

### Run it with Docker (local or server)

The whole thing (pipeline + dashboard) is containerised:

```bash
docker compose up -d --build     # builds, then serves on http://localhost/
```

To deploy live on AWS EC2, see **[DEPLOY_AWS_EC2.md](DEPLOY_AWS_EC2.md)**.

### Why this order is mandatory

1. **Step 1 first** — it produces the model that steps 2 and 3 depend on.
2. **Client pipeline second** — its detectors feed the Step 1 scoring overlay and the
   dashboard alert pages.
3. **Dashboard prep third** — it reads everything above (and loads the model to build
   the live before/after simulator).
4. **`npm run dev` last** — it just serves the prepared JSON.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: pandas` | Run the pip install in Prerequisites. |
| Dashboard shows "Could not load data" | Run step 3 (`prepare_dashboard_data.py`) from the project root. |
| Overlay simulator is empty | Step 1 model missing — run step 1, then re-run step 3. |
| `npm` not found | Install Node.js 18+ and reopen the terminal. |
| Port 5174 busy | Stop the other process, or edit `server.port` in `frontend/vite.config.ts`. |

---

## 4. Input datasets

All inputs live in `fraud_detection_enriched_dataset_pack/`.

| File | Rows | Role |
|---|---|---|
| `ehi_authorisation_transactions_enriched.csv` | 100,000 | **Main feed** — one row per authorisation with EHI message fields + enriched device/IP/behaviour signals + labels |
| `historical_cardholder_baselines_enriched.csv` | 8,000 | Prior per-cardholder behaviour (avg/p95 amount, usual rates, distinct devices/IPs) |
| `cardholder_profiles.csv` | 8,000 | Cardholder attributes (`risk_segment`, `prior_chargebacks`) |
| `merchant_profiles.csv` | 1,500 | Merchant attributes (`merchant_risk_segment`, name, MCC) |
| `synthetic_merchant_risk_events.csv` | 1,500 | Per-merchant risk telemetry (laundering score, fraud/chargeback/volume-spike rates) |

- **Join identifiers:** `cardholder_id`, `merchant_id`, `SubBIN`.
- **Target label:** `is_fraud` (binary). `recommended_action` and `risk_score_baseline`
  are used **only for comparison/evaluation**, never as model inputs.
- **All data is synthetic** — realistic in shape, but absolute metrics are illustrative.

---

## 5. Component A — Step 1: Real-Time Fraud Triage

Six Python files under `src/`.

### 5.1 `config.py` — single source of truth
Holds all paths, column lists, thresholds and weights.
- `TARGET = "is_fraud"`.
- `LEAKAGE_COLS` — fields that must **never** be features because they are only known
  *after* the outcome (`is_fraud`, `recommended_action`, `risk_score_baseline`,
  response/status codes, balances, analyst decisions, chargeback status, loss amounts).
  Using them would be **data leakage** — the model would "cheat" by seeing the answer.
- `NUMERIC_FEATURES` (~54) + `CATEGORICAL_FEATURES` (~11) — the only columns the model
  sees, all available *before* the auth decision.
- `RULE_WEIGHTS` / `RULE_THRESHOLDS`, `THRESHOLD_STEP_UP` / `THRESHOLD_DECLINE`,
  `ML_WEIGHT = 0.7`.

### 5.2 `data_loader.py` — load + join
`load_enriched_dataset()` left-joins the supporting tables onto every authorisation row
(`historical_cardholder_baselines` + `cardholder_profiles` on `cardholder_id`,
`merchant_profiles` on `merchant_id`).

### 5.3 `features.py` — build X/y + preprocessor
- `build_xy(df)` selects allowed feature columns + target and **asserts no leakage column
  slipped in**.
- `build_preprocessor()` — a scikit-learn `ColumnTransformer`:
  - numeric → `SimpleImputer(median)` + `StandardScaler`
  - categorical → `SimpleImputer(most_frequent)` + `OneHotEncoder(handle_unknown="ignore")`

### 5.4 `rules_engine.py` — the explainable overlay
Pure functions, no ML.

`apply_rules(txn)` returns `(rule_risk_score, reason_codes)`. Each rule adds fixed points:

| Rule | Fires when… | Points | Reason code |
|---|---|---|---|
| High velocity + device/IP mismatch | `velocity_1h ≥ 5` and (device or IP mismatch) | 180 | `HIGH_VELOCITY_NEW_DEVICE` |
| CVV mismatch online | online and `cvv_result == "N"` | 200 | `CVV_MISMATCH_ONLINE` |
| AVS mismatch online | online and `avs_result == "N"` | 120 | `AVS_MISMATCH_ONLINE` |
| ATO — password reset | `password_reset_last_7d ≥ 1` | 160 | `ATO_PASSWORD_RESET_7D` |
| ATO — email change | `email_changed_last_7d ≥ 1` | 160 | `ATO_EMAIL_CHANGED_7D` |
| ATO — failed logins | `login_failed_count_24h ≥ 3` | 120 | `ATO_LOGIN_FAILURES_24H` |
| BIN attack — many cards/IP | `ip_card_count_1h ≥ 8` | 220 | `BIN_ATTACK_IP_MANY_CARDS` |
| BIN attack — high txn/IP | `ip_txn_count_1h ≥ 15` | 160 | `BIN_ATTACK_IP_HIGH_TXN_RATE` |
| Amount anomaly + new context | `amount_vs_avg_ratio ≥ 3.0` and (new_country or new_merchant) | 180 | `AMOUNT_ANOMALY_NEW_CONTEXT` |
| Online + high-risk + no 3DS | online and high_risk_country and no 3DS | 120 | `ONLINE_HIGHRISK_NO_3DS` |
| IP mismatch in high-risk geo | IP mismatch and high_risk_country | 120 | `HIGH_RISK_GEO_IP_MISMATCH` |

The rule score is capped at 1000. Then:
- `combine_scores(proba, rule_score)`: `final = clamp(ML_WEIGHT × proba × 1000 + rule_risk_score, 0, 1000)`.
  ML contributes at most 700 points (×0.7); rules add full points, leaving headroom for
  rules to push a borderline case over the line.
- `decide_action(final)`: `< step_up` → approve · `step_up..decline-1` → step_up · `≥ decline` → decline.

### 5.5 `train_step1_model.py` — train, evaluate, tune, save
1. Load + build features.
2. Stratified split **60% train / 20% validation / 20% test**.
3. Train **Logistic Regression** and **Random Forest** (both `class_weight="balanced"`).
4. Evaluate on validation + test (ROC AUC, PR AUC, precision, recall, F1, confusion
   matrix, classification report).
5. **Select best by validation PR AUC** (Random Forest wins).
6. **Tune triage thresholds on the validation set** (current: step-up ≥ 190, decline ≥ 430).
7. Re-fit best model on train+val and save a `joblib` bundle (pipeline + feature lists +
   thresholds).
8. Write `outputs/model_metrics.json`, `feature_list.json`, `sample_scored_transactions.csv`.

**Current metrics (test set):**

| Model | ROC AUC | PR AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|
| Logistic Regression | 0.830 | 0.657 | 0.410 | 0.675 | 0.510 |
| **Random Forest (selected)** | 0.823 | 0.655 | 0.821 | 0.458 | 0.588 |

With the blended triage, ~73% of all fraud lands in the step-up+decline bands; the
decline band is ~75% fraud.

### 5.6 `score_authorisation.py` — real-time entry point

```python
score_transaction(transaction: dict) -> {
  "fraud_probability": float,
  "rule_risk_score": int,
  "final_risk_score": int,
  "recommended_action": "approve" | "step_up" | "decline",
  "reason_codes": [ ... ]
}
```

Sequence: load bundle (cached) → ML probability → `apply_rules` → **apply client add-on
overlays** (blacklist / BIN / IP watchlists) → blend → map to action → apply any forced
action. Missing fields are imputed; unknown categories ignored.

### Step 1 — data-leakage exclusions
Excluded from the feature set (see `LEAKAGE_COLS`):
```
is_fraud, fraud_scenario, recommended_action, risk_score_baseline,
Responsestatus, Acknowledgement, Resp_Code_DE39, Auth_Code_DE38,
Status_Code, Txn_Stat_Code, EHI_Response_Time, CurBalance, AvlBalance,
analyst_decision, confirmed_fraud, false_positive, chargeback_status,
final_loss_amount, case_priority, sar_required, case_narrative
(plus post-auth balance fields: ActBal, Avl_Bal, BlkAmt)
```

---

## 6. Component B — Client add-on detectors

Batch detectors (Step 3 slices) plus a Step 1 enhancement. They write alert tables and
small "watchlist" lookups that Step 1 scoring consumes.

### 6.0 The critical data insight (read this)
The synthetic timestamps are **spread out** — there are *no literal sub-second bursts*
(minimum gap between two transactions on the same IP is ~30 seconds). A real
"10 transactions in 60 seconds" rule would find **nothing**.

But attack velocity is fully captured in **pre-aggregated 1-hour counters**:
- `ip_card_count_1h` — distinct cards from this IP in the last hour (normal max ≈ 7;
  **attack traffic 30–69**).
- `ip_txn_count_1h` — transactions from this IP in the last hour (normal max ≈ 9;
  **attack traffic 80–160**).

So the detectors are **signal-driven** on this dataset (they key off those counters),
while the **literal rolling-window logic is still implemented** and activates
automatically when real high-resolution timestamps are available.

### 6.1 `bin_attack_detection.py` — BIN/SubBIN attack
- Suspicious attempt = `ip_card_count_1h ≥ 8` **or** `ip_txn_count_1h ≥ 15`.
- Grouped per SubBIN into one alert with: txn count, unique cards/merchants/IPs/devices,
  avg amount, decline rate, max IP txn/hr, 0–1000 risk score, severity, recommended
  control (monitor → throttle → block), reason codes.
- Output: `outputs/bin_attack_alerts.csv` + `lookup_bin_attack_subbins.json`.
- **Result:** 7 alerts = the 7 truly attacked SubBINs, all CRITICAL, ~100% decline,
  avg ~$13–18 (classic low-value card testing).

### 6.2 `ip_repetition_detection.py` — same-IP repetitive auth
Two complementary methods:
1. **Literal rolling windows** (3+/10s, 5+/30s, 10+/60s) — produces `WINDOW_*` codes and
   the `max_transactions_per_10_seconds` column. **Dormant on this synthetic data.**
2. **1-hour velocity counters** — flags IPs with `ip_txn_count_1h ≥ 12` or
   `ip_card_count_1h ≥ 8`. **This is what fires here.**

Escalates when an IP spans multiple entities (`MULTI_CARDHOLDER_SAME_IP`, …).
- Output: `outputs/ip_repetitive_authorisation_alerts.csv` + `lookup_repetitive_ips.json`.
- **Result:** 84 alerts = the 84 attack IPs.

### 6.3 `merchant_blacklist.py` — merchant blacklist (Step 1 enhancement)
1. **Manual / operator blacklist** — `config/merchant_blacklist.csv`
   (`merchant_id, Merch_ID_DE42, blacklist_reason, effective_date, action`).
   **Authoritative** at scoring time. `action=decline` forces decline; `step_up`/`review`
   forces at least step-up.
2. **Dynamic suggestions** — from `synthetic_merchant_risk_events.csv`. A merchant is
   recommended when **≥ 2** signals trip: laundering score ≥70, fraud rate ≥0.25,
   chargeback rate ≥0.12, volume spike ≥0.10, or HIGH risk segment.
   - Output: `outputs/merchant_blacklist_suggestions.csv`.
   - **Result:** 3 manual + 76 dynamic suggestions (of 1,500).

### 6.4 Overlay integration into Step 1
At scoring time four overlays layer onto the Step 1 score:

| Reason code | Trigger | Effect |
|---|---|---|
| `BLACKLISTED_MERCHANT` | merchant on manual list | forces decline / ≥ step-up |
| `HIGH_RISK_MERCHANT_BLACKLIST_SUGGESTED` | merchant on dynamic list | +risk points |
| `BIN_ATTACK_PATTERN` | txn's SubBIN on BIN watchlist | +risk points |
| `SAME_IP_REPETITIVE_AUTH` | txn's IP on IP watchlist | +risk points |

### 6.5 `client_requirement_pipeline.py` — orchestrator
Runs all three detectors, writes the alert CSVs + watchlist lookups +
`client_requirement_summary.json`, and prints a summary.

---

## 7. Component C — Dashboard

### 7.1 `scripts/prepare_dashboard_data.py` — the bridge
Converts pipeline outputs into frontend JSON in `frontend/public/data/`:
- copies alert tables + manual blacklist + model metrics;
- builds `dashboard_summary.json` (KPI counts + chart distributions);
- builds `combined_alert_queue.json` (167 rows across all detectors);
- builds `overlay_simulator.json` — **genuine before/after scoring** by loading the real
  model and scoring curated transactions twice (Step 1 only vs Step 1 + overlays).

### 7.2 The React app (`frontend/`)
- **Stack:** React 19 + TypeScript + Vite + Tailwind CSS v4 + Recharts + React Router.
  No backend — it fetches static JSON.
- **Theme:** dark "IRIS-style" — black background; palette restricted to yellow, gold,
  grey, white, black. Severity/action distinction is by intensity (grey → gold → solid
  bright-yellow).
- **Pages (left sidebar):**
  1. **Executive Overview** — KPIs + charts (action mix, fraud scenarios, severity,
     risk bands, top reason codes).
  2. **Step 1 Fraud Triage** — model metrics, confusion matrix, model comparison,
     filterable scored-transaction table.
  3. **Overlay & Simulator** — interactive base→final scoring per scenario.
  4. **BIN Attack** — alerts table + drill-down modal + charts.
  5. **Same-IP Repetitive** — alerts + drill-down + charts.
  6. **Merchant Blacklist** — manual vs dynamic tabs with filters.
  7. **Analyst Alert Queue** — unified, sortable/filterable 167-alert queue.
  8. **Business Summary** — capability→requirement mapping + limitations.

### 7.3 KPI denominators (important for reading the Overview)
Cards mix two bases:
- **Full dataset (100,000):** Transactions scanned, portfolio fraud rate, BIN/IP/merchant
  alert counts — the detectors scan all 100k.
- **Held-out test set (20,000):** Approve / step-up / decline counts and **all model
  metrics**. The model is trained on train, tuned on validation, and **never sees the
  test set** during fitting — no leakage.

### 7.4 Dashboard data files (`frontend/public/data/`)
`dashboard_summary.json`, `model_metrics.json`, `sample_scored_transactions.json`,
`bin_attack_alerts.json`, `ip_repetitive_authorisation_alerts.json`,
`merchant_blacklist_suggestions.json`, `manual_merchant_blacklist.json`,
`combined_alert_queue.json`, `overlay_simulator.json`.

---

## 8. End-to-end data flow

```
ehi_authorisation_transactions_enriched.csv  (+ baselines, profiles, risk events)
        │
        ▼
[A] train_step1_model.py ───────────────► outputs/step1_fraud_model.joblib
        │                                  outputs/model_metrics.json
        │                                  outputs/feature_list.json
        │                                  outputs/sample_scored_transactions.csv
        ▼
[B] client_requirement_pipeline.py ─────► outputs/bin_attack_alerts.csv
        │   (uses the model for the         outputs/ip_repetitive_authorisation_alerts.csv
        │    Step 1 scoring overlay)         outputs/merchant_blacklist_suggestions.csv
        │                                    outputs/lookup_bin_attack_subbins.json
        │                                    outputs/lookup_repetitive_ips.json
        │                                    outputs/client_requirement_summary.json
        ▼
[C] scripts/prepare_dashboard_data.py ──► frontend/public/data/*.json
        │   (loads the model to build
        │    the real before/after sim)
        ▼
    npm run dev  ───────────────────────► http://localhost:5174/  (React dashboard)
```

---

## 9. Reason-code glossary

**Step 1 (transaction-intrinsic) codes**
| Code | Meaning |
|---|---|
| `ML_HIGH_FRAUD_PROBABILITY` | Model scored this txn high (≥0.5) |
| `HIGH_VELOCITY_NEW_DEVICE` | Velocity spike + device/IP mismatch |
| `CVV_MISMATCH_ONLINE` / `AVS_MISMATCH_ONLINE` | CVV/AVS failed on a card-not-present txn |
| `ATO_PASSWORD_RESET_7D` / `ATO_EMAIL_CHANGED_7D` / `ATO_LOGIN_FAILURES_24H` | Account-takeover signals |
| `BIN_ATTACK_IP_MANY_CARDS` / `BIN_ATTACK_IP_HIGH_TXN_RATE` | High IP card/txn velocity at txn level |
| `AMOUNT_ANOMALY_NEW_CONTEXT` | Big amount vs average + new country/merchant |
| `ONLINE_HIGHRISK_NO_3DS` | Online + high-risk country + no 3DS |
| `HIGH_RISK_GEO_IP_MISMATCH` | IP-country mismatch in high-risk geography |

**Client add-on overlay codes** (highlighted in the UI)
| Code | Meaning |
|---|---|
| `BLACKLISTED_MERCHANT` | Merchant on the manual blacklist (authoritative) |
| `HIGH_RISK_MERCHANT_BLACKLIST_SUGGESTED` | Merchant on the dynamic suggestion list |
| `BIN_ATTACK_PATTERN` | Txn's SubBIN is on the BIN-attack watchlist |
| `SAME_IP_REPETITIVE_AUTH` | Txn's IP is on the repetitive-auth watchlist |

**Detector alert codes**
| Code | Meaning |
|---|---|
| `MANY_TXN_SAME_SUBBIN` / `MANY_UNIQUE_CARDS_SAME_SUBBIN` | BIN enumeration volume / card spread |
| `LOW_VALUE_REPEATED_ATTEMPTS` | Low-value card testing |
| `HIGH_DECLINE_RATE` | High share of declined attempts (probing) |
| `SHARED_IP_MULTI_CARD` | One IP across many cards |
| `WINDOW_3_IN_10S` / `WINDOW_5_IN_30S` / `WINDOW_10_IN_60S` | Literal rolling-window breaches (production timing) |
| `HIGH_IP_VELOCITY_1H` | Elevated 1-hour IP counters |
| `MULTI_CARDHOLDER_SAME_IP` / `MULTI_MERCHANT_SAME_IP` / `MULTI_SUBBIN_SAME_IP` | IP spans multiple entities |
| `HIGH_LAUNDERING_RISK` / `HIGH_FRAUD_RATE` / `HIGH_CHARGEBACK_RATE` / `VOLUME_SPIKE` / `HIGH_RISK_SEGMENT` | Merchant risk signals |

---

## 10. Consolidated limitations

### Data
1. **All data is synthetic** — metrics are illustrative, not production performance.
2. **Timestamps are not sub-minute bursty** — attack velocity is carried by
   pre-aggregated 1-hour counters; literal second-level burst detection is implemented
   but dormant until real high-resolution timestamps exist.

### Step 1 model
3. **Point-in-time joins are approximate** (`cardholder_id` join without strict as-of
   alignment) — production must guarantee features precede the auth.
4. **Modest recall at the 0.5 cut**; the model is precision-leaning. Operational recall
   comes from the **triage thresholds**, not the raw cut.
5. **Rule weights & thresholds are hand-set** starting points; calibrate with fraud-ops
   against real loss/friction.
6. **Large model artefact** (~330 MB Random Forest) — cap depth/trees or move to a
   gradient-boosted model for deployment.
7. **No latency benchmark and no drift/monitoring** yet.

### Client add-on detectors
8. **BIN alert windows can span the whole period** because attempts are sparse in time —
   real timing enables wave segmentation.
9. **IP alerts cluster at MEDIUM** — sub-second intensity (which would push HIGH/CRITICAL)
   is absent in the synthetic timestamps.
10. **Watchlists are coarse and not time-boxed** — any txn on a previously attacked
    SubBIN/IP is flagged; production should expire entries and score per-entity.
11. **Manual blacklist has no expiry enforcement** (`effective_date` recorded but not applied).
12. **Detection is batch, not streaming** — production needs a live feature store.
13. **Dynamic merchant suggestions are advisory** — review before promotion.

### Dashboard
14. **Read-only / static JSON** — re-run the prep script after each pipeline run; the
    simulator uses precomputed (not live-API) scoring.
15. **No authentication, no case write-back** — alert "status" is display-only.
16. **Triage KPI counts** are from the 20k held-out test set; the scored-transactions
    table shows the 200-row sample.

### Scope
17. Only **Step 1** + the **client-requested slices of Step 3** + the merchant-blacklist
    Step 1 enhancement are implemented. Full **Step 2, 4, 5** are **not** built yet.

---

## 11. Project layout

```
fraud_detection/
├── fraud_detection_enriched_dataset_pack/   # input datasets (synthetic)
├── src/                                      # Python pipeline
│   ├── config.py                             # paths, features, leakage list, thresholds, weights
│   ├── data_loader.py                        # load + join
│   ├── features.py                           # X/y build + preprocessor
│   ├── rules_engine.py                       # rule overlay + score blend + action mapping
│   ├── train_step1_model.py                  # train / evaluate / tune / save
│   ├── score_authorisation.py                # score_transaction() real-time entry point
│   ├── detection_utils.py                    # shared detector helpers
│   ├── bin_attack_detection.py               # BIN/SubBIN attack detector
│   ├── ip_repetition_detection.py            # same-IP repetitive auth detector
│   ├── merchant_blacklist.py                 # manual + dynamic blacklist
│   └── client_requirement_pipeline.py        # runs all three detectors
├── config/
│   └── merchant_blacklist.csv                # manual/operator blacklist
├── scripts/
│   └── prepare_dashboard_data.py             # pipeline outputs -> dashboard JSON
├── outputs/                                  # model, metrics, alerts, lookups
├── frontend/                                 # React + Vite + Tailwind dashboard
│   ├── src/{components,pages,utils,types}/
│   └── public/data/                          # generated dashboard JSON
├── venv/                                     # Python virtual environment
└── README.md                                 # this file
```

---

*Card & Payment Fraud Detection POC. All data is synthetic and for demonstration
purposes only.*
