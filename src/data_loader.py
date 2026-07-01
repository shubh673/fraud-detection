"""
Data loading + joins for Step 1.

Loads the enriched authorisation transactions and enriches each row with
pre-transaction context from:
  - historical_cardholder_baselines  (join on cardholder_id)
  - cardholder_profiles              (join on cardholder_id)
  - merchant_profiles                (join on merchant_id)

All joins are LEFT joins so the authorisation feed always drives the row set.
No outcome/post-transaction fields are pulled in here.
"""

import pandas as pd

import config


# Columns to pull from the historical cardholder baseline table.
# These describe PRIOR behaviour (known before the current authorisation),
# so they are safe real-time features. We deliberately skip historical fraud /
# chargeback counts to avoid any label-leakage suspicion.
_BASELINE_COLS = [
    "cardholder_id",
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

_CARDHOLDER_PROFILE_COLS = ["cardholder_id", "prior_chargebacks"]
_MERCHANT_PROFILE_COLS = ["merchant_id", "merchant_risk_segment"]


def load_raw_transactions(nrows=None):
    """Load the enriched authorisation transactions file."""
    return pd.read_csv(config.AUTH_TX_FILE, nrows=nrows, low_memory=False)


def load_enriched_dataset(nrows=None):
    """
    Load authorisation transactions and join the supporting profile/baseline
    tables. Returns a single DataFrame ready for feature building.
    """
    tx = load_raw_transactions(nrows=nrows)

    baselines = pd.read_csv(config.CARDHOLDER_BASELINE_FILE, usecols=_BASELINE_COLS)
    profiles = pd.read_csv(config.CARDHOLDER_PROFILE_FILE, usecols=_CARDHOLDER_PROFILE_COLS)
    merchants = pd.read_csv(config.MERCHANT_PROFILE_FILE, usecols=_MERCHANT_PROFILE_COLS)

    tx = tx.merge(baselines, on="cardholder_id", how="left")
    tx = tx.merge(profiles, on="cardholder_id", how="left")
    tx = tx.merge(merchants, on="merchant_id", how="left")

    return tx


if __name__ == "__main__":
    df = load_enriched_dataset(nrows=2000)
    print("Loaded shape:", df.shape)
    print("Fraud rate:", round(df[config.TARGET].mean(), 4))
    missing = [c for c in config.ALL_FEATURES if c not in df.columns]
    print("Missing feature columns:", missing)
