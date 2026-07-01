# Enriched Synthetic Fraud Detection Dataset Pack

This pack extends the original synthetic EHI-style fraud dataset with additional synthetic fields and linked tables for a more complete end-to-end POC.

## What Was Added

- Raw-style device and IP fields for account takeover, card-not-present, BIN attack, and behavioural anomaly detection.
- Transaction-level BIN attack attempts linked to SubBIN, IP/device pattern and proposed throttle/block rules.
- Analyst review outcomes, false-positive flags and loss estimates.
- Chargeback/dispute lifecycle data.
- Account movement/fund-flow data for mule and transaction-laundering scenarios.
- Merchant risk events covering volume spikes, chargebacks, refund behaviour, MCC mismatch and settlement-account changes.
- Expanded graph edges for cardholder-device, cardholder-IP and account-to-account links.
- Regulatory report templates and enriched case files with governance notes.

## Important Note

All added fields are synthetic and suitable for POC, demo, model prototyping and workflow validation. They should not be presented as production evidence. For production, the client should provide real device/IP telemetry, analyst outcomes, chargeback lifecycle data, account movement data, and jurisdiction-specific regulatory templates.

## Recommended Real-Time Model Exclusions

Do not train a real-time authorisation model using future/outcome fields such as `is_fraud`, `fraud_scenario`, `analyst_decision`, `confirmed_fraud`, `chargeback_status`, `final_loss_amount`, or regulatory report fields. Use those only for training labels, evaluation, monitoring or case workflow.
