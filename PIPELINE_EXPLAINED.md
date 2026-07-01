# Pipeline Explained — Step & Component Walkthrough

A complete, read-line-by-line explanation of the Card & Payment Fraud Detection
POC: what each stage does, what each file/component is responsible for, how data
flows between them, and the limitations at every level.

> This is a **conceptual + code-level** companion to the run instructions in
> [RUN_END_TO_END.md](RUN_END_TO_END.md). Read this to understand *how and why*
> it works; read the run guide to *execute* it.

---

## Table of contents

1. [The big picture](#1-the-big-picture)
2. [Input datasets](#2-input-datasets)
3. [Component A — Step 1: Real-Time Fraud Triage](#3-component-a--step-1-real-time-fraud-triage)
4. [Component B — Client Add-On Detectors](#4-component-b--client-add-on-detectors)
5. [Component C — Dashboard](#5-component-c--dashboard)
6. [End-to-end data flow](#6-end-to-end-data-flow)
7. [Reason-code glossary](#7-reason-code-glossary)
8. [Consolidated limitations](#8-consolidated-limitations)

---

## 1. The big picture

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

- **Step 1** answers: *"For this single authorisation, should we approve, step-up
  (challenge), or decline — right now, in milliseconds?"* It uses a hybrid of a
  machine-learning model and deterministic business rules.
- **Client add-on** answers three operational questions the client prioritised:
  *Is a BIN/SubBIN under a card-enumeration attack? Is one IP hammering
  authorisations? Which merchants should be blacklisted?* It also **feeds its
  findings back into Step 1** so the real-time decision is enriched.
- **Dashboard** is a **read-only presentation layer** for stakeholders and
  analysts — it never re-computes anything, it only visualises the outputs.

**Design choice:** Step 1 is intentionally **not agentic**. It is a practical,
explainable hybrid (ML score + rule score → blended risk → action). Every
decision carries human-readable *reason codes*.

---

## 2. Input datasets

All inputs live in `fraud_detection_enriched_dataset_pack/`. Step 1 + the add-on
use these:

| File | Rows | Role |
|---|---|---|
| `ehi_authorisation_transactions_enriched.csv` | 100,000 | **Main feed** — one row per authorisation, with EHI message fields + enriched device/IP/behaviour signals + labels |
| `historical_cardholder_baselines_enriched.csv` | 8,000 | Prior per-cardholder behaviour (avg/p95 amount, usual rates, distinct devices/IPs, etc.) |
| `cardholder_profiles.csv` | 8,000 | Cardholder attributes (`risk_segment`, `prior_chargebacks`) |
| `merchant_profiles.csv` | 1,500 | Merchant attributes (`merchant_risk_segment`, name, MCC) |
| `synthetic_merchant_risk_events.csv` | 1,500 | Per-merchant risk telemetry (laundering score, fraud/chargeback/volume-spike rates) |

**Key identifiers used for joins:** `cardholder_id`, `merchant_id`, `SubBIN`.

**The target label:** `is_fraud` (binary). The dataset also ships a
`recommended_action` and a `risk_score_baseline` — these are used **only for
comparison/evaluation**, never as model inputs (see leakage rules below).

> **Limitation (data):** Everything is **synthetic**. The signals are realistic
> in shape but the relationships were generated, so absolute metric values are
> illustrative, not predictive of production performance.

---

## 3. Component A — Step 1: Real-Time Fraud Triage

Six Python files under `src/`. Read them in this order.

### 3.1 `src/config.py` — the single source of truth

Holds **all** paths, column lists, thresholds, and weights so nothing is
hard-coded elsewhere. The important parts:

- **`TARGET = "is_fraud"`** — what the model predicts.
- **`LEAKAGE_COLS`** — the list of fields that must **never** be features because
  they are only known *after* the authorisation outcome (e.g. `is_fraud`,
  `recommended_action`, `risk_score_baseline`, response/status codes, balances,
  analyst decisions, chargeback status, loss amounts). Using these would be
  **data leakage** — the model would "cheat" by looking at the answer.
- **`NUMERIC_FEATURES`** (~54) and **`CATEGORICAL_FEATURES`** (~11) — the only
  columns the model is allowed to see. All are available *before* the auth
  decision (amount, velocity counters, device/IP match flags, account-takeover
  signals, joined baselines, etc.).
- **`RULE_WEIGHTS` / `RULE_THRESHOLDS`** — points each business rule adds and the
  trigger levels.
- **`THRESHOLD_STEP_UP` / `THRESHOLD_DECLINE`** — default action cut-offs on the
  0–1000 final score.
- **`ML_WEIGHT = 0.7`** — how much the ML score contributes vs the rules in the
  blend.

> **Limitation:** Feature lists and rule weights are **hand-curated starting
> points**. They should be reviewed with fraud-ops and tuned against real
> loss/friction trade-offs.

### 3.2 `src/data_loader.py` — load + join

- `load_raw_transactions()` reads the main authorisation CSV.
- `load_enriched_dataset()` **left-joins** the supporting tables onto every
  authorisation row:
  - `historical_cardholder_baselines` on `cardholder_id` (prior behaviour),
  - `cardholder_profiles` on `cardholder_id` (`prior_chargebacks`),
  - `merchant_profiles` on `merchant_id` (`merchant_risk_segment`).
- Left joins mean the authorisation feed always drives the row set; missing
  matches become nulls (handled later by imputation).

> **Limitation (point-in-time):** Baselines are joined purely on `cardholder_id`
> without strict "as-of-timestamp" alignment. In production you must guarantee
> every feature was computed **strictly before** the authorisation, or you
> reintroduce subtle leakage.

### 3.3 `src/features.py` — build X/y and the preprocessor

- `build_xy(df)` selects only the allowed feature columns and the target. It also
  **asserts that no leakage column slipped into the feature list** — a safety net.
- `build_preprocessor()` returns a scikit-learn `ColumnTransformer`:
  - **Numeric** → `SimpleImputer(median)` then `StandardScaler` (fill gaps,
    standardise scale).
  - **Categorical** → `SimpleImputer(most_frequent)` then
    `OneHotEncoder(handle_unknown="ignore")` (unseen categories at scoring time
    are safely ignored, not errors).
- `get_feature_metadata()` produces the JSON written to
  `outputs/feature_list.json`.

### 3.4 `src/rules_engine.py` — the explainable overlay

Pure functions, no ML. Two responsibilities:

1. **`apply_rules(txn)`** inspects raw signals and returns
   `(rule_risk_score, reason_codes)`. Each rule maps to a fraud pattern:
   - High velocity + device/IP mismatch → `HIGH_VELOCITY_NEW_DEVICE`
   - CVV/AVS mismatch on an online txn → `CVV_MISMATCH_ONLINE`, `AVS_MISMATCH_ONLINE`
   - Account-takeover signals (password reset / email change / failed logins) →
     `ATO_*`
   - BIN-attack-style IP signals → `BIN_ATTACK_IP_MANY_CARDS`, `BIN_ATTACK_IP_HIGH_TXN_RATE`
   - Big amount + new country/merchant → `AMOUNT_ANOMALY_NEW_CONTEXT`
   - Online + high-risk country + no 3DS → `ONLINE_HIGHRISK_NO_3DS`
   - IP mismatch in high-risk geography → `HIGH_RISK_GEO_IP_MISMATCH`
   - Score is capped at 1000.
2. **`combine_scores(proba, rule_score)`** and **`decide_action(final)`**:
   - `final_risk_score = clamp(ML_WEIGHT × proba × 1000 + rule_risk_score, 0, 1000)`
   - `< step_up` → approve · `step_up..decline-1` → step_up · `≥ decline` → decline

> **Limitation:** Rules are simple thresholds, deliberately. They are great for
> explainability but can be brittle; sophisticated fraud may sit just under a
> threshold. The ML model exists precisely to catch what the rules miss.

### 3.5 `src/train_step1_model.py` — train, evaluate, tune, save

The training script, step by step:

1. **Load + build features** via the modules above.
2. **Stratified split** 60% train / 20% validation / 20% test (stratified keeps
   the fraud rate consistent across splits).
3. **Train two models**, each wrapped in a pipeline with the preprocessor:
   - **Logistic Regression** (`class_weight="balanced"`) — linear baseline.
   - **Random Forest** (`class_weight="balanced"`) — non-linear, usually stronger.
4. **Evaluate** both on validation + test: ROC AUC, PR AUC, precision, recall,
   F1, confusion matrix, classification report.
5. **Select** the best model by **validation PR AUC** (PR AUC is the right metric
   for rare-event/imbalanced fraud — Random Forest wins here).
6. **Tune triage thresholds on the validation set** (not the test set, to avoid
   optimistic bias): sweep candidate decline thresholds to maximise decline-band
   F1 vs `is_fraud`, then pick a step-up band. Current result ≈ step-up ≥ 190,
   decline ≥ 430.
7. **Re-fit the chosen model on train+val** for deployment and **save a bundle**
   with `joblib`: the fitted pipeline + feature lists + tuned thresholds.
8. **Write outputs:** `model_metrics.json`, `feature_list.json`,
   `sample_scored_transactions.csv`.

**What the metrics mean (current run):** Random Forest test ROC AUC ≈ 0.823,
PR AUC ≈ 0.655, precision ≈ 0.82, recall ≈ 0.46. With the blended triage,
~73% of all fraud lands in the step-up+decline bands, and the decline band is
~75% fraud.

> **Limitation:** Recall at the default 0.5 cut is modest — the model is
> precision-leaning. The **triage thresholds** (not the 0.5 cut) are what matter
> operationally, and they catch much more fraud by routing borderline cases to
> step-up rather than outright approve. The large Random Forest also produces a
> ~330 MB model file; for production, cap tree depth/count or switch to a
> gradient-boosted model.

### 3.6 `src/score_authorisation.py` — the real-time entry point

The function the rest of the system calls:

```python
score_transaction(transaction: dict) -> {
  "fraud_probability": float,
  "rule_risk_score": int,
  "final_risk_score": int,
  "recommended_action": "approve" | "step_up" | "decline",
  "reason_codes": [ ... ]
}
```

Sequence inside it:

1. Load the model bundle once (cached).
2. Build a one-row DataFrame from the dict → ML `fraud_probability`. Missing
   fields are imputed; unknown categories ignored.
3. Run `apply_rules` → base `rule_risk_score` + reason codes.
4. **Apply the client add-on overlays** (see §4.4) — blacklist, BIN watchlist, IP
   watchlist — adding points and reason codes, and possibly **forcing** an
   action.
5. Blend ML + rules → `final_risk_score`; map to action; apply any forced action.
6. Add `ML_HIGH_FRAUD_PROBABILITY` when the model itself is the main driver.

> **Limitation:** Scoring is single-row and lightweight, but there is **no formal
> millisecond-latency benchmark under load** yet, and **no model monitoring /
> drift detection** (those belong to later POC steps).

---

## 4. Component B — Client Add-On Detectors

Files under `src/`. These are **batch detectors** (Step 3 of the roadmap, partial)
plus a **Step 1 enhancement** (merchant blacklist). They write alert tables and
small "watchlist" lookups that Step 1 scoring consumes.

### 4.0 The critical data insight (read this first)

The synthetic timestamps are **spread out** — there are *no literal sub-second
bursts* (the minimum gap between two transactions on the same IP is ~30 seconds).
A real "10 transactions in 60 seconds" rule would therefore find **nothing**.

But the attack *velocity* is fully captured in **pre-aggregated 1-hour counters**
that the feed already provides:

- `ip_card_count_1h` — distinct cards seen from this IP in the last hour
  (normal max ≈ 7; **attack traffic reaches 30–69**).
- `ip_txn_count_1h` — transactions from this IP in the last hour
  (normal max ≈ 9; **attack traffic reaches 80–160**).

So the detectors are **signal-driven** on this dataset (they key off those
counters), while the **literal rolling-window logic is still implemented** and
activates automatically when real high-resolution timestamps are available.

> **Limitation (and why it matters):** This is the single most important caveat.
> On this data the second-level windows are dormant; production data with real
> millisecond timestamps is what turns them on. The dashboard states this
> explicitly on the relevant pages.

### 4.1 `src/detection_utils.py` — shared helpers

- `severity_from_score(score)` → LOW/MEDIUM/HIGH/CRITICAL bands.
- `parse_event_time(df)` → parse + sort by timestamp.
- `declined_flag(df)` → mark declined/failed auths (`Txn_Stat_Code == 'D'` or a
  populated decline response code).
- `forward_window_counts(times, window_seconds)` → the **literal rolling-window
  engine** (two-pointer): for each transaction, how many fall within the next
  *N* seconds. This is the production-ready burst detector.
- `segment_indices(...)` → split flagged rows into separate alert clusters by
  time gap.

### 4.2 `src/bin_attack_detection.py` — BIN/SubBIN attack detection

Detects **card-enumeration attacks** against a BIN range.

- A transaction is a **suspicious attempt** if `ip_card_count_1h ≥ 8` **or**
  `ip_txn_count_1h ≥ 15` (the velocity signature).
- Suspicious attempts are **grouped per SubBIN** into one alert.
- Each alert computes: transaction count, unique cards/merchants/IPs/devices,
  average amount, decline rate, max IP txn/hr, a 0–1000 **risk score**, a
  **severity**, a **recommended control** (monitor → throttle → block), and
  **reason codes** (`MANY_UNIQUE_CARDS_SAME_SUBBIN`, `LOW_VALUE_REPEATED_ATTEMPTS`,
  `HIGH_DECLINE_RATE`, `SHARED_IP_MULTI_CARD`, …).
- Output: `outputs/bin_attack_alerts.csv` + a **SubBIN watchlist**
  (`lookup_bin_attack_subbins.json`).
- **Current result:** 7 alerts = the 7 truly attacked SubBINs, all CRITICAL,
  ~100% decline, avg amount ~$13–18 (classic low-value card testing).

> **Limitation:** Because attempts are grouped per SubBIN (timestamps are sparse),
> an "attack window" can span the whole dataset period. With real timing the same
> code can segment distinct attack *waves*. The SubBIN watchlist is also **coarse**
> for real-time use — see §4.4.

### 4.3 `src/ip_repetition_detection.py` — same-IP repetitive auth

Detects **one IP issuing many authorisations** (card testing / enumeration from a
single source). Two complementary methods:

1. **Literal rolling windows** (3+/10s, 5+/30s, 10+/60s) via the engine in
   `detection_utils` — produces `WINDOW_*` reason codes and the
   `max_transactions_per_10_seconds` column. **Dormant on this synthetic data.**
2. **1-hour velocity counters** — an IP is flagged when `ip_txn_count_1h ≥ 12` or
   `ip_card_count_1h ≥ 8` (normal peaks ~9/7). **This is what fires here.**

Each alert records unique cardholders/merchants/SubBINs/devices and escalates when
one IP spans multiple entities (`MULTI_CARDHOLDER_SAME_IP`, etc.).

- Output: `outputs/ip_repetitive_authorisation_alerts.csv` + an **IP watchlist**
  (`lookup_repetitive_ips.json`).
- **Current result:** 84 alerts = the 84 attack IPs (peak 80–160 txns/IP-hour).

> **Limitation:** All 84 currently land at MEDIUM severity because the dominant
> signal is the 1-hour counter (no sub-second intensity to push them higher).
> Real burst timing would raise some to HIGH/CRITICAL.

### 4.4 `src/merchant_blacklist.py` — merchant blacklist (Step 1 enhancement)

Two sources:

1. **Manual / operator blacklist** — `config/merchant_blacklist.csv`
   (`merchant_id`, `blacklist_reason`, `effective_date`, `action`). **Authoritative**
   at scoring time. `action=decline` forces decline; `step_up`/`review` forces at
   least step-up.
2. **Dynamic suggestions** — generated from `synthetic_merchant_risk_events.csv`.
   A merchant is recommended for blacklisting when **≥ 2** risk signals trip:
   high laundering score (≥70), high fraud rate (≥0.25), high chargeback rate
   (≥0.12), volume spike (≥0.10), or HIGH risk segment. Suggested action escalates
   with evidence (laundering + fraud/chargeback, or ≥3 signals → decline; else
   step-up).
   - Output: `outputs/merchant_blacklist_suggestions.csv`.
   - **Current result:** 3 manual entries + 76 dynamic suggestions (of 1,500).

> **Limitation:** The manual blacklist records an `effective_date` but does **not
> yet enforce expiry**. Dynamic suggestions are **advisory** — they should be
> human-reviewed before promotion to the manual list.

### 4.5 How the add-on feeds Step 1 (`_apply_overlays` in score_authorisation.py)

At scoring time, four overlays layer onto the Step 1 score:

| Reason code | Trigger | Effect |
|---|---|---|
| `BLACKLISTED_MERCHANT` | merchant on manual list | forces decline / ≥ step-up |
| `HIGH_RISK_MERCHANT_BLACKLIST_SUGGESTED` | merchant on dynamic list | +risk points |
| `BIN_ATTACK_PATTERN` | txn's SubBIN on BIN watchlist | +risk points |
| `SAME_IP_REPETITIVE_AUTH` | txn's IP on IP watchlist | +risk points |

This is exactly what the **Overlay & Simulator** dashboard page demonstrates
(base Step-1 score → final score with overlays).

> **Limitation:** Watchlist membership is **coarse** — any transaction on a
> previously attacked SubBIN/IP is flagged, with **no time-boxing/expiry**. This
> can over-flag legitimate traffic that later reuses that SubBIN/IP. Production
> should expire watchlist entries and score per-entity, not per-membership.

### 4.6 `src/client_requirement_pipeline.py` — the orchestrator

Runs all three detectors over the authorisation feed, writes the alert CSVs +
watchlist lookups + `client_requirement_summary.json`, and prints a summary.
This is the single command for Component B.

> **Limitation (architecture):** It is **batch** — it processes a snapshot.
> Production needs a **streaming** feature store keeping per-IP / per-SubBIN
> counters continuously fresh.

---

## 5. Component C — Dashboard

### 5.1 `scripts/prepare_dashboard_data.py` — the bridge

The dashboard never reads CSVs or the model directly. This script converts
everything into frontend-friendly JSON in `frontend/public/data/`:

- Copies the alert tables + manual blacklist + model metrics to JSON.
- Builds `dashboard_summary.json` — all KPI counts + chart distributions
  (action mix, fraud scenarios, severity, risk bands, top reason codes).
- Builds `combined_alert_queue.json` — BIN + IP + merchant alerts merged into one
  analyst queue (167 rows).
- Builds `overlay_simulator.json` — **genuine before/after scoring**: it loads the
  real model and scores a handful of curated transactions twice (Step 1 only vs
  Step 1 + overlays), so the simulator page is accurate, not faked.

> **Limitation:** This is a **snapshot exporter**. Re-run it whenever the Python
> pipeline re-runs, or the dashboard shows stale numbers. If a source file is
> missing it warns and skips, and the matching page shows an empty state.

### 5.2 The React app (`frontend/`)

- **Stack:** React 19 + TypeScript + Vite + Tailwind CSS v4 + Recharts + React
  Router. **No backend** — it fetches the static JSON.
- **Shared components:** `KpiCard`, `Card`, `DataTable` (search/sort/paginate),
  `SeverityBadge`, `ActionBadge`, `ReasonCodeList` (overlay codes highlighted),
  `AlertDetailModal`, `Charts`, `Layout` (sidebar + header).
- **Pages (left sidebar):**
  1. **Executive Overview** — KPIs + 5 charts.
  2. **Step 1 Fraud Triage** — model metrics, confusion matrix, model comparison,
     filterable scored-transaction table.
  3. **Overlay & Simulator** — interactive base→final scoring per scenario.
  4. **BIN Attack** — alerts table + drill-down modal + charts.
  5. **Same-IP Repetitive** — alerts + drill-down + charts.
  6. **Merchant Blacklist** — manual vs dynamic tabs with filters.
  7. **Analyst Alert Queue** — unified, sortable/filterable 167-alert queue.
  8. **Business Summary** — capability→requirement mapping + limitations.

> **Limitation:** The dashboard is **read-only**. Alert "status" is display-only;
> there is no case-management write-back, no auth, and no multi-user state.

---

## 6. End-to-end data flow

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

**Why this order is mandatory:**
1. Step 1 must run first — it produces the model B and C depend on.
2. B runs second — its detectors feed the Step 1 overlay and the dashboard alerts.
3. C runs third — it reads everything above (and loads the model for the simulator).
4. `npm run dev` last — it just serves the prepared JSON.

---

## 7. Reason-code glossary

**Step 1 (transaction-intrinsic) codes**
| Code | Meaning |
|---|---|
| `ML_HIGH_FRAUD_PROBABILITY` | The model itself scored this txn high (≥0.5) |
| `HIGH_VELOCITY_NEW_DEVICE` | Velocity spike + device/IP mismatch |
| `CVV_MISMATCH_ONLINE` / `AVS_MISMATCH_ONLINE` | CVV/AVS failed on a card-not-present txn |
| `ATO_PASSWORD_RESET_7D` / `ATO_EMAIL_CHANGED_7D` / `ATO_LOGIN_FAILURES_24H` | Account-takeover signals |
| `BIN_ATTACK_IP_MANY_CARDS` / `BIN_ATTACK_IP_HIGH_TXN_RATE` | High IP card/txn velocity at txn level |
| `AMOUNT_ANOMALY_NEW_CONTEXT` | Big amount vs average + new country/merchant |
| `ONLINE_HIGHRISK_NO_3DS` | Online + high-risk country + no 3DS |
| `HIGH_RISK_GEO_IP_MISMATCH` | IP-country mismatch in high-risk geography |

**Client add-on overlay codes** (highlighted indigo in the UI)
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

## 8. Consolidated limitations

A single place that gathers every caveat mentioned above.

### Data
1. **All data is synthetic.** Metrics are illustrative; do not present them as
   production performance.
2. **Timestamps are not sub-minute bursty.** Attack velocity is carried by
   pre-aggregated 1-hour counters; literal second-level burst detection is
   implemented but dormant until real high-resolution timestamps exist.

### Step 1 model
3. **Point-in-time joins are approximate** (`cardholder_id` join without strict
   as-of alignment) — production must guarantee features precede the auth.
4. **Modest recall at the 0.5 cut**; the model is precision-leaning. Operational
   recall comes from the **triage thresholds**, not the raw cut.
5. **Rule weights & thresholds are hand-set** starting points; calibrate with
   fraud-ops against real loss/friction.
6. **Large model artefact** (~330 MB Random Forest) — cap depth/trees or move to
   a gradient-boosted model for deployment.
7. **No latency benchmark and no drift/monitoring** yet.

### Client add-on detectors
8. **BIN alert windows can span the whole period** because attempts are sparse in
   time — real timing enables wave segmentation.
9. **IP alerts cluster at MEDIUM** — sub-second intensity (which would push
   HIGH/CRITICAL) is absent in the synthetic timestamps.
10. **Watchlists are coarse and not time-boxed** — any txn on a previously
    attacked SubBIN/IP is flagged; production should expire entries and score
    per-entity.
11. **Manual blacklist has no expiry enforcement** (`effective_date` is recorded
    but not applied).
12. **Detection is batch, not streaming** — production needs a live feature store.
13. **Dynamic merchant suggestions are advisory** — review before promotion.

### Dashboard
14. **Read-only / static JSON** — re-run the prep script after each pipeline run;
    the simulator uses precomputed (not live-API) scoring.
15. **No authentication, no case write-back** — alert "status" is display-only.
16. **Triage KPI counts** (approve/step-up/decline) are from the 20k held-out test
    set; the scored-transactions table shows the 200-row sample.

### Scope
17. Only **Step 1** and the **client-requested slices of Step 3** (BIN attack,
    same-IP repetition) plus the **merchant-blacklist Step 1 enhancement** are
    implemented. Full Step 2 (behaviour/compliance monitoring), Step 4
    (merchant/transaction-laundering risk) and Step 5 (regulatory reporting) are
    **not** built yet.

---

*All figures in this document reflect the current synthetic run
(100,000 transactions; 7 BIN alerts; 84 IP alerts; 3 manual + 76 dynamic merchant
entries; 167 combined queue alerts). For POC / demonstration purposes only.*
