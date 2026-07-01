# Step 1 — Real-Time Fraud Alert Triage at Authorisation

This is **Step 1** of the Card & Payment Fraud Detection POC. It scores each
authorisation transaction in real time against the cardholder's behavioural
profile and recommends one of three actions:

- **approve**
- **step_up** (e.g. send to 3DS / OTP challenge)
- **decline**

> Steps 2–5 (behaviour/compliance monitoring, BIN attack detection, merchant /
> transaction-laundering risk, regulatory reporting) are **not** implemented yet.

---

## What Step 1 does

It uses a **practical hybrid approach** (not agentic):

1. **ML model** — a supervised classifier predicts the probability that a
   transaction is fraudulent, using only signals available *before* the
   authorisation decision.
2. **Rules engine** — a deterministic, explainable overlay that adds risk points
   for known fraud patterns (CNP, account takeover, BIN attack, counterfeit /
   lost-stolen, behavioural anomaly).
3. **Triage blend** — the ML probability and the rule score are combined into a
   single `0–1000` `final_risk_score`, which is mapped to an action using tuned
   thresholds.

The fraud patterns covered: **card-not-present, account takeover, counterfeit,
lost/stolen, behavioural anomaly, and transaction-level BIN-attack signals**.

---

## Datasets used

All from `fraud_detection_enriched_dataset_pack/`:

| File | Role | Join key |
|---|---|---|
| `ehi_authorisation_transactions_enriched.csv` | Main authorisation feed (drives every row, 100k txns) | — |
| `historical_cardholder_baselines_enriched.csv` | Prior cardholder behaviour (avg/p95 amount, usual online/intl rates, distinct merchants/devices/countries, historical device/IP risk) | `cardholder_id` |
| `cardholder_profiles.csv` | `prior_chargebacks`, `risk_segment` | `cardholder_id` |
| `merchant_profiles.csv` | `merchant_risk_segment` | `merchant_id` |

`SubBIN` is present in the authorisation feed and used as an identifier; BIN-attack
behaviour is captured through transaction-level IP/device features rather than a
separate join.

The authorisation file already carries the device/IP/behavioural enrichments
inline (velocity, device fingerprint match, IP counts, ATO signals, etc.), so the
joins above add *prior-behaviour baselines* on top of those.

---

## Fields excluded to avoid data leakage

The target is **`is_fraud`** (binary). `recommended_action` is used **only for
evaluation/comparison**, never as a model input.

The following post-transaction / outcome / future fields are **excluded from the
feature set** (see `LEAKAGE_COLS` in `src/config.py`):

```
is_fraud, fraud_scenario, recommended_action, risk_score_baseline,
Responsestatus, Acknowledgement, Resp_Code_DE39, Auth_Code_DE38,
Status_Code, Txn_Stat_Code, EHI_Response_Time, CurBalance, AvlBalance,
analyst_decision, confirmed_fraud, false_positive, chargeback_status,
final_loss_amount, case_priority, sar_required, case_narrative
(plus post-auth balance fields: ActBal, Avl_Bal, BlkAmt)
```

`src/features.py` also asserts at build time that none of these columns leaked
into the feature list.

---

## Features

- **~54 numeric features** — amount, velocity (1h/24h/7d), amount-vs-average
  ratio, device/IP risk scores, IP/device counts, ATO signals (password reset,
  email change, failed logins), account age, plus joined prior-behaviour
  baselines.
- **11 categorical features** — card network/type, CVV/AVS result, CNP channel,
  3DS result, transaction & IP country, MCC code, cardholder & merchant risk
  segment.

Preprocessing (`sklearn`):
- numeric → `SimpleImputer(median)` + `StandardScaler`
- categorical → `SimpleImputer(most_frequent)` + `OneHotEncoder(handle_unknown="ignore")`

The full feature list is written to `outputs/feature_list.json`.

---

## Models & evaluation

Two `sklearn` models are trained (no xgboost/lightgbm), both with
`class_weight="balanced"`:

- **Logistic Regression**
- **Random Forest**

Data is split **60% train / 20% validation / 20% test** (stratified). The best
model is selected by **validation PR AUC**, thresholds are tuned on validation,
and final metrics are reported on the held-out **test** set.

Latest test-set results (`outputs/model_metrics.json`):

| Model | ROC AUC | PR AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|
| Logistic Regression | 0.830 | 0.657 | 0.410 | 0.675 | 0.510 |
| **Random Forest (selected)** | 0.823 | 0.655 | 0.821 | 0.458 | 0.588 |

Metrics reported: ROC AUC, PR AUC, precision, recall, F1, confusion matrix and
full classification report (all in `model_metrics.json`).

### Triage thresholds

Suggested defaults are `approve < 350`, `step_up 350–699`, `decline >= 700`.
Because the score is an **ML+rules blend**, thresholds are **tuned on the
validation set** (sweep maximising decline-F1 vs `is_fraud`, then a step_up band).
Tuned values are saved with the model and used at scoring time. The current run
produced approximately `step_up >= 190`, `decline >= 430`.

On the test set this yields (roughly): ~66% approve, ~25% step_up, ~9% decline,
with a fraud rate of ~75% inside the decline band and ~5–6% in the approve band.
Agreement with the dataset's own `recommended_action` is ~0.70. The blend weight
and thresholds are all configurable in `src/config.py`.

---

## How to train

From the project root, using the project venv:

```bash
# Windows (PowerShell)
.\venv\Scripts\python.exe src\train_step1_model.py

# Git Bash / Linux-style
venv/Scripts/python.exe src/train_step1_model.py
```

This will:
1. Load + join the datasets.
2. Train and evaluate Logistic Regression and Random Forest.
3. Tune triage thresholds on validation data.
4. Save the model bundle with `joblib` to `outputs/step1_fraud_model.joblib`.
5. Write `outputs/model_metrics.json`, `outputs/feature_list.json` and
   `outputs/sample_scored_transactions.csv`.
6. Print final metrics to the console.

Dependencies: `pandas`, `scikit-learn`, `joblib` (already installed in `venv/`).

---

## How to score a new transaction

```python
from score_authorisation import score_transaction   # run from src/, or add src/ to path

txn = {
    "Txn_Amt": 1450.0,
    "is_online": 1,
    "cnp_channel": "ecommerce",
    "high_risk_country": 1,
    "card_network": "VISA",
    "card_type": "CREDIT",
    "cvv_result": "N",
    "avs_result": "N",
    "3ds_authenticated": 0,
    "velocity_1h": 7,
    "amount_vs_avg_ratio": 6.5,
    "new_country": 1,
    "device_fingerprint_match": 0,
    "ip_country_match": 0,
    "password_reset_last_7d": 1,
    "ip_card_count_1h": 14,
    # ... any subset of the configured feature fields
}

result = score_transaction(txn)
```

Returns:

```json
{
  "fraud_probability": 0.8735,
  "rule_risk_score": 1000,
  "final_risk_score": 1000,
  "recommended_action": "decline",
  "reason_codes": ["ML_HIGH_FRAUD_PROBABILITY", "CVV_MISMATCH_ONLINE", ...]
}
```

Missing fields are tolerated — numeric gaps are imputed by the model and unknown
categories are ignored by the encoder. You can also run the built-in demo:

```bash
venv/Scripts/python.exe src/score_authorisation.py
```

---

## Project layout

```
src/
  config.py             # paths, feature lists, leakage exclusions, thresholds, rule weights
  data_loader.py        # load authorisation feed + join baselines/profiles
  features.py           # X/y build + ColumnTransformer (impute/scale/one-hot)
  rules_engine.py       # rule overlay, reason codes, score blend, action mapping
  train_step1_model.py  # train, evaluate, tune thresholds, save artefacts
  score_authorisation.py# score_transaction(dict) -> dict  (real-time entry point)
outputs/
  step1_fraud_model.joblib       # trained model bundle (model + thresholds + feature list)
  model_metrics.json             # all evaluation metrics
  feature_list.json              # features used + leakage exclusions
  sample_scored_transactions.csv # sample of scored test transactions
README_STEP1.md
```

---

## Rules engine (overlay)

Deterministic rules add risk points and reason codes (see `RULE_WEIGHTS` /
`RULE_THRESHOLDS` in `config.py`):

- **High velocity + new device/IP mismatch** → `HIGH_VELOCITY_NEW_DEVICE`
- **CVV / AVS mismatch on online (CNP) txn** → `CVV_MISMATCH_ONLINE`, `AVS_MISMATCH_ONLINE`
- **Account takeover**: password reset / email change in 7d, failed logins 24h →
  `ATO_PASSWORD_RESET_7D`, `ATO_EMAIL_CHANGED_7D`, `ATO_LOGIN_FAILURES_24H`
- **BIN attack**: high `ip_card_count_1h` / `ip_txn_count_1h` →
  `BIN_ATTACK_IP_MANY_CARDS`, `BIN_ATTACK_IP_HIGH_TXN_RATE`
- **Amount anomaly + new country/merchant** → `AMOUNT_ANOMALY_NEW_CONTEXT`
- **Online + high-risk country + no 3DS** → `ONLINE_HIGHRISK_NO_3DS`
- **IP-country mismatch in high-risk geo** → `HIGH_RISK_GEO_IP_MISMATCH`

`final_risk_score = clamp(ML_WEIGHT * proba * 1000 + rule_risk_score, 0, 1000)`.

---

## Current limitations

- **Synthetic data.** All device/IP/ATO signals and labels are synthetic; metrics
  will not transfer directly to production. Real telemetry is needed for a real
  model.
- **Point-in-time joins are approximate.** Baselines are joined on
  `cardholder_id` without strict as-of timestamp alignment; a production system
  must guarantee features are computed strictly before the authorisation.
- **Rule weights/thresholds are hand-set** starting points, tuned only lightly.
  They should be calibrated with the fraud-ops team against real loss/friction
  trade-offs. The current tuned step_up band is fairly aggressive (~25% step-up).
- **Model size.** The Random Forest (300 deep trees) produces a large
  (~330 MB) artefact; for deployment, cap depth / tree count or switch to a
  gradient-boosted model once available.
- **No latency benchmark yet.** Scoring is lightweight (single-row predict +
  rules), but a formal millisecond-latency test under load is not included.
- **No model monitoring / drift detection** — that is part of later steps.
- **Behavioural-anomaly recall is the weakest area** (some low-signal fraud lands
  in the approve band); richer historical/sequence features would help.
