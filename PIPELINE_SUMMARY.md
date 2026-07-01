# Fraud Detection POC — Internal Summary

A one-page brief to explain the pipeline to the team. For the deep version see
[PIPELINE_EXPLAINED.md](PIPELINE_EXPLAINED.md); to run it see
[RUN_END_TO_END.md](RUN_END_TO_END.md).

---

## The elevator pitch

> We built a working proof-of-concept that scores every card authorisation in
> real time and recommends **approve / step-up / decline**, using a hybrid of a
> machine-learning model and explainable business rules. On top of that we added
> three things the client specifically asked for — **BIN-attack detection**,
> **same-IP repetitive-authorisation detection**, and a **merchant blacklist** —
> and we feed all of those back into the real-time score. Everything is visualised
> in an interactive dashboard for analysts and stakeholders.

---

## What it does, in three parts

| Part | Question it answers | Output |
|---|---|---|
| **1. Real-time triage** (Step 1) | "Should we approve, challenge, or decline *this* authorisation, right now?" | A decision + risk score + reason codes per transaction |
| **2. Client add-on** (Step 3 slices + enhancement) | "Is a BIN under attack? Is one IP hammering us? Which merchants are risky?" | Alert lists + watchlists that also enrich the Step 1 score |
| **3. Dashboard** | "How do I see and act on all of this?" | An interactive web UI with KPIs, drill-downs, and an analyst queue |

---

## How the scoring works (plain English)

```
   ML model gives a fraud probability  ┐
                                        ├──►  blended risk score (0–1000)  ──►  approve / step-up / decline
   Business rules add risk + reasons   ┘            ▲
                                                    │
        Client add-on overlays (blacklist, BIN, IP) │
        add risk or force a decision, with reasons ─┘
```

- The **ML model** (Random Forest, chosen over Logistic Regression) learns
  patterns from history.
- The **rules engine** catches known fraud signatures (CVV/AVS mismatch, account
  takeover, velocity spikes, etc.) and is fully explainable.
- The **overlays** let the new detectors influence the live decision — e.g. a
  blacklisted merchant is declined, a transaction on an attacked BIN is escalated.
- Every decision ships with **reason codes**, so analysts always know *why*.

**Anti-cheating safeguard:** we explicitly exclude all "outcome" fields
(`is_fraud`, chargeback status, balances, analyst decisions, etc.) from the model
so it can't peek at the answer — this is the **data-leakage** discipline.

---

## Key numbers (current synthetic run)

| Metric | Value |
|---|---|
| Transactions scanned | **100,000** |
| Model quality (test ROC AUC / PR AUC) | **0.82 / 0.66** |
| Fraud caught in step-up + decline bands | **~73%** |
| Decline band purity (how much is real fraud) | **~75%** |
| BIN-attack alerts | **7** SubBINs (all CRITICAL) |
| Same-IP repetitive alerts | **84** IPs |
| Merchant blacklist | **3 manual + 76 suggested** |
| Combined analyst queue | **167 alerts** |

---

## What the team can say about each piece

- **Step 1 triage** — "Sub-second, hybrid ML + rules, explainable, tuned to route
  borderline cases to step-up rather than blunt-approve or blunt-decline."
- **BIN attack** — "We detect card-enumeration: many cards probed on one BIN,
  low-value attempts, ~100% declines. We flag the BIN and recommend a control
  (monitor → throttle → block)."
- **Same-IP repetition** — "We flag IPs issuing abnormally many auths. The
  second-level burst logic (3-in-10s etc.) is built and will switch on with real
  timestamps; today the 1-hour velocity counters carry the signal."
- **Merchant blacklist** — "An authoritative manual list plus auto-generated
  suggestions from merchant risk telemetry, both wired into real-time scoring."
- **Dashboard** — "A banking-themed UI: executive KPIs, per-detector drill-downs,
  a live before/after scoring simulator, and a unified analyst alert queue."

---

## Be upfront about these limitations

- **Synthetic data** — numbers are illustrative, not production performance.
- **Timestamps aren't sub-second bursty** — so the literal second-level windows
  are dormant; we use the pre-computed 1-hour velocity counters instead. Real
  feeds will activate the burst logic.
- **Watchlists are coarse / not time-boxed** — a previously attacked BIN/IP stays
  flagged; production needs expiry + per-entity scoring.
- **Batch, not streaming** — detectors run over a snapshot; production needs a
  live feature store.
- **Dashboard is read-only** — no case write-back, no auth (it's a showcase).
- **Scope** — Step 1 + the requested slices of Step 3 + the merchant-blacklist
  enhancement are done. Full Step 2, 4, 5 are **not** built yet.

---

## How it maps to the roadmap

| Capability | Roadmap step | Status |
|---|---|---|
| Real-time fraud triage | Step 1 | ✅ Done |
| BIN / SubBIN attack detection | Step 3 (partial) | ✅ Done |
| Same-IP repetitive authorisation | Step 3 (partial) | ✅ Done |
| Merchant blacklist + overlay | Step 1 enhancement | ✅ Done |
| Behaviour / compliance monitoring | Step 2 | ⏳ Not started |
| Merchant / transaction-laundering risk | Step 4 | ⏳ Not started |
| Regulatory reporting assembler | Step 5 | ⏳ Not started |

---

## Run order (one line each)

```
1. python src/train_step1_model.py          # train the model
2. python src/client_requirement_pipeline.py # run the 3 detectors
3. python scripts/prepare_dashboard_data.py  # build dashboard data
4. cd frontend && npm run dev                # open http://localhost:5174/
```

*POC / demonstration only. All data synthetic.*
