"""
Central configuration for Step 1: Real-Time Fraud Alert Triage.

Keeps all paths, column lists, leakage exclusions, model settings, rule
weights and decision thresholds in one place so the rest of the code stays
small and readable.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "fraud_detection_enriched_dataset_pack"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
MODEL_PATH = OUTPUT_DIR / "step1_fraud_model.joblib"

# Input files used by Step 1
AUTH_TX_FILE = DATA_DIR / "ehi_authorisation_transactions_enriched.csv"
CARDHOLDER_BASELINE_FILE = DATA_DIR / "historical_cardholder_baselines_enriched.csv"
CARDHOLDER_PROFILE_FILE = DATA_DIR / "cardholder_profiles.csv"
MERCHANT_PROFILE_FILE = DATA_DIR / "merchant_profiles.csv"

# Output artefacts
METRICS_FILE = OUTPUT_DIR / "model_metrics.json"
FEATURE_LIST_FILE = OUTPUT_DIR / "feature_list.json"
SAMPLE_SCORED_FILE = OUTPUT_DIR / "sample_scored_transactions.csv"

# ---------------------------------------------------------------------------
# Target + identifiers
# ---------------------------------------------------------------------------
TARGET = "is_fraud"
ID_COLS = ["transaction_id", "cardholder_id", "merchant_id", "SubBIN"]

# recommended_action is kept ONLY for evaluation/comparison, never as a feature.
COMPARISON_COL = "recommended_action"

# ---------------------------------------------------------------------------
# Leakage exclusions (post-transaction / outcome / future fields).
# These must NEVER be used as model input features.
# ---------------------------------------------------------------------------
LEAKAGE_COLS = [
    "is_fraud",
    "fraud_scenario",
    "recommended_action",
    "risk_score_baseline",
    "Responsestatus",
    "Acknowledgement",
    "Resp_Code_DE39",
    "Auth_Code_DE38",
    "Status_Code",
    "Txn_Stat_Code",
    "EHI_Response_Time",
    "CurBalance",
    "AvlBalance",
    "analyst_decision",
    "confirmed_fraud",
    "false_positive",
    "chargeback_status",
    "final_loss_amount",
    "case_priority",
    "sar_required",
    "case_narrative",
    # extra raw EHI balance/response fields that are outcome-ish or post-auth
    "ActBal",
    "Avl_Bal",
    "BlkAmt",
]

# ---------------------------------------------------------------------------
# Feature definitions.
# Only pre-authorisation signals that are realistically available in real time.
# ---------------------------------------------------------------------------

# Numeric features that come straight from the authorisation message
NUMERIC_FEATURES = [
    "Txn_Amt",
    "is_online",
    "is_contactless",
    "is_international",
    "high_risk_country",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "velocity_1h",
    "velocity_24h",
    "velocity_7d",
    "amount_vs_avg_ratio",
    "days_since_last_txn",
    "new_merchant",
    "new_country",
    "failed_attempts_last_24h",
    "device_fingerprint_match",
    "ip_country_match",
    "billing_shipping_match",
    "3ds_authenticated",
    "account_age_days",
    "chargeback_history",
    "device_age_days",
    "device_card_count_24h",
    "device_txn_count_1h",
    "ip_card_count_1h",
    "ip_card_count_24h",
    "ip_txn_count_1h",
    "ip_txn_count_24h",
    "login_failed_count_24h",
    "password_reset_last_7d",
    "email_changed_last_7d",
    "shipping_billing_country_match",
    "terminal_reuse_count_24h",
    "mcc_mismatch_flag",
    "merchant_volume_spike_flag",
    "device_risk_score",
    "ip_risk_score",
    # joined from cardholder profile
    "prior_chargebacks",
    # joined from historical cardholder baselines (prior behaviour, pre-txn)
    "avg_historical_amount",
    "std_historical_amount",
    "p95_historical_amount",
    "usual_online_rate",
    "usual_international_rate",
    "usual_contactless_rate",
    "distinct_merchants_180d",
    "distinct_countries_180d",
    "distinct_devices_180d",
    "distinct_ip_countries_180d",
    "avg_historical_device_risk",
    "avg_historical_ip_risk",
    "risky_ip_event_rate_180d",
    "failed_login_events_180d",
]

# Categorical features (one-hot encoded)
CATEGORICAL_FEATURES = [
    "card_network",
    "card_type",
    "cvv_result",
    "avs_result",
    "cnp_channel",
    "3ds_result",
    "Txn_Ctry",
    "ip_country",
    "MCC_Code",          # treated as a category code, not a magnitude
    "risk_segment",      # cardholder risk segment
    "merchant_risk_segment",
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# ---------------------------------------------------------------------------
# Model / split settings
# ---------------------------------------------------------------------------
RANDOM_STATE = 42
TEST_SIZE = 0.20
VAL_SIZE = 0.20  # carved out of the train portion for threshold tuning

# ---------------------------------------------------------------------------
# Rules engine weights (added on top of the ML risk component).
# Each rule contributes points to the rule_risk_score (0-1000 scale).
# ---------------------------------------------------------------------------
RULE_WEIGHTS = {
    "high_velocity_new_device": 180,        # velocity spike + device/IP mismatch
    "cvv_mismatch_online": 200,             # CVV mismatch in CNP/online txn
    "avs_mismatch_online": 120,             # AVS mismatch in CNP/online txn
    "ato_password_reset": 160,              # account takeover: recent password reset
    "ato_email_changed": 160,               # account takeover: recent email change
    "ato_login_failures": 120,              # account takeover: many failed logins
    "bin_attack_ip_cards": 220,             # BIN attack: many cards from one IP
    "bin_attack_ip_txns": 160,             # BIN attack: high txn count from one IP
    "amount_anomaly_new_context": 180,      # big amount + new country/merchant
    "no_3ds_online_highrisk": 120,          # online + high-risk country + no 3DS
    "high_risk_geo_mismatch": 120,          # IP country != expected, high-risk geo
}

# Rule trigger thresholds (kept here so they are easy to tune)
RULE_THRESHOLDS = {
    "velocity_1h_high": 5,
    "ip_card_count_1h_high": 8,
    "ip_txn_count_1h_high": 15,
    "login_failed_count_24h_high": 3,
    "amount_vs_avg_ratio_high": 3.0,
}

# ---------------------------------------------------------------------------
# Final triage thresholds on the 0-1000 final_risk_score.
# These defaults can be overridden by tuned values saved with the model.
# ---------------------------------------------------------------------------
THRESHOLD_STEP_UP = 350   # >= this and < decline => step_up
THRESHOLD_DECLINE = 700   # >= this => decline

# Blend weight: how much the ML probability contributes to the final score.
# final_risk_score = ML_WEIGHT * (proba * 1000) + rule_risk_score   (capped 0-1000)
ML_WEIGHT = 0.7


# ===========================================================================
# CLIENT REQUIREMENT ADD-ON
#   - BIN attack detection            (belongs to Step 3)
#   - Same-IP repetitive auth detection (belongs to Step 3)
#   - Merchant blacklist              (Step 1 real-time rule enhancement)
# ===========================================================================

# --- Paths ---------------------------------------------------------------
CONFIG_DIR = PROJECT_ROOT / "config"

# Input datasets used by the add-on detectors
MERCHANT_RISK_EVENTS_FILE = DATA_DIR / "synthetic_merchant_risk_events.csv"

# Static / manual merchant blacklist (operator maintained)
MERCHANT_BLACKLIST_FILE = CONFIG_DIR / "merchant_blacklist.csv"

# Output alert tables
BIN_ATTACK_ALERTS_FILE = OUTPUT_DIR / "bin_attack_alerts.csv"
IP_REPETITION_ALERTS_FILE = OUTPUT_DIR / "ip_repetitive_authorisation_alerts.csv"
MERCHANT_BLACKLIST_SUGGESTIONS_FILE = OUTPUT_DIR / "merchant_blacklist_suggestions.csv"
CLIENT_REQ_SUMMARY_FILE = OUTPUT_DIR / "client_requirement_summary.json"

# Lookup files that Step 1 real-time scoring consumes (small, fast to load)
BIN_ATTACK_LOOKUP_FILE = OUTPUT_DIR / "lookup_bin_attack_subbins.json"
IP_REPETITION_LOOKUP_FILE = OUTPUT_DIR / "lookup_repetitive_ips.json"

# Timestamp column used for time-ordered detection
EVENT_TIME_COL = "Txn_GPS_Date"

# --- BIN attack detection parameters -------------------------------------
# NOTE ON THIS DATASET: the synthetic transaction timestamps are spread out
# (no literal sub-minute bursts). The "velocity" of a BIN-enumeration attack is
# instead carried by the pre-aggregated 1h velocity counters that the auth feed
# provides (ip_card_count_1h / ip_txn_count_1h). We therefore detect attack
# *attempts* from those counters + the card-testing signature (low value, high
# decline) and aggregate them per SubBIN. In production with real timestamps the
# rolling-window utilities in detection_utils.py can window these instead.
BIN_ATTACK_PARAMS = {
    "card_signal_min": 8,            # ip_card_count_1h >= this => attack attempt
    "txn_signal_min": 15,            # ip_txn_count_1h  >= this => attack attempt
    "min_attempts": 5,               # min suspicious attempts on a SubBIN to alert
    "min_unique_cards": 5,           # min distinct cards across those attempts
    "low_value_amount": 10.0,        # "card testing" low-value attempt threshold
    "low_value_share": 0.30,         # share of low-value attempts to flag testing
    "high_decline_rate": 0.30,       # decline rate that signals probing
    "shared_ip_card_count": 5,       # >=N cards from one IP among the attempts
}

# --- Same-IP repetitive authorisation parameters -------------------------
# Two complementary methods:
#   1. Literal rolling-window rules (production-correct) -> each tuple is
#      (window_seconds, min_transactions). Fires when real sub-minute bursts
#      exist in the timestamps.
#   2. Pre-aggregated 1h velocity counters (this synthetic dataset) -> an IP is
#      repetitive when ip_txn_count_1h / ip_card_count_1h are elevated.
IP_REPETITION_PARAMS = {
    "windows": [(10, 3), (30, 5), (60, 10)],
    "ip_txn_count_1h_min": 12,       # normal traffic peaks at ~9
    "ip_card_count_1h_min": 8,
    "max_alert_gap_seconds": 120,    # gap that splits one IP burst into two alerts
    "multi_entity_min": 2,           # >= this many distinct cards/merchants/subbins => escalate
}

# --- Dynamic merchant blacklist suggestion thresholds --------------------
MERCHANT_RISK_THRESHOLDS = {
    "laundering_risk_score": 70.0,
    "fraud_rate": 0.25,
    "chargeback_rate_30d": 0.12,
    "volume_spike_rate": 0.10,
    "high_segment": "HIGH",
    # how many risk signals must trip before we recommend blacklisting
    "min_signals_to_suggest": 2,
}

# --- Severity bands (shared by both detectors, on the 0-1000 risk_score) --
SEVERITY_BANDS = [
    (850, "CRITICAL"),
    (650, "HIGH"),
    (400, "MEDIUM"),
    (0, "LOW"),
]

# --- Real-time scoring overlay weights (added to rule_risk_score) --------
# These let the Step 3 detections + blacklist influence Step 1 triage.
OVERLAY_WEIGHTS = {
    "bin_attack_pattern": 250,                 # SubBIN currently under attack
    "same_ip_repetitive": 220,                 # IP flagged for repetitive auth
    "blacklist_suggested": 200,                # merchant on dynamic suggestion list
}
