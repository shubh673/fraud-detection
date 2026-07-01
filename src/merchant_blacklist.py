"""
Merchant blacklist  (Step 1 real-time rule enhancement).

Two sources:
  1. Static / manual blacklist  -> config/merchant_blacklist.csv
        operator-maintained; action in {decline, step_up, review}
  2. Dynamic suggested blacklist -> generated from merchant risk data
        (synthetic_merchant_risk_events.csv + merchant_profiles.csv)

The static list is authoritative at scoring time. The dynamic suggestions are
advisory: they add risk and a reason code, and are reviewed before promotion to
the manual list.
"""

import pandas as pd

import config


# ---------------------------------------------------------------------------
# Static / manual blacklist
# ---------------------------------------------------------------------------
def load_manual_blacklist():
    """
    Load the operator-maintained blacklist.
    Returns dict: merchant_id -> {"action", "reason", "Merch_ID_DE42"}.
    Returns {} if the file is absent (scoring still works).
    """
    if not config.MERCHANT_BLACKLIST_FILE.exists():
        return {}
    bl = pd.read_csv(config.MERCHANT_BLACKLIST_FILE, dtype=str).fillna("")
    out = {}
    for _, r in bl.iterrows():
        mid = r.get("merchant_id", "").strip()
        if not mid:
            continue
        action = r.get("action", "review").strip().lower() or "review"
        out[mid] = {
            "action": action,
            "reason": r.get("blacklist_reason", ""),
            "Merch_ID_DE42": r.get("Merch_ID_DE42", ""),
        }
    return out


# ---------------------------------------------------------------------------
# Dynamic suggested blacklist
# ---------------------------------------------------------------------------
def suggest_blacklist():
    """
    Build dynamic merchant blacklist suggestions from merchant risk data.
    Returns a DataFrame with the required columns.
    """
    t = config.MERCHANT_RISK_THRESHOLDS
    risk = pd.read_csv(config.MERCHANT_RISK_EVENTS_FILE)
    profiles = pd.read_csv(config.MERCHANT_PROFILE_FILE)

    # bring merchant_name / segment from profiles where missing
    df = risk.merge(
        profiles[["merchant_id", "merchant_name", "merchant_risk_segment"]],
        on="merchant_id", how="left", suffixes=("", "_prof"),
    )
    for col in ["merchant_name", "merchant_risk_segment"]:
        if f"{col}_prof" in df.columns:
            df[col] = df[col].fillna(df[f"{col}_prof"])

    def _num(col):
        return pd.to_numeric(df.get(col), errors="coerce").fillna(0.0)

    laundering = _num("laundering_risk_score")
    fraud_rate = _num("fraud_rate")
    cb_rate = _num("chargeback_rate_30d")
    spike = _num("volume_spike_rate")
    segment = df["merchant_risk_segment"].astype("string").fillna("")

    # signal flags
    sig_laundering = laundering >= t["laundering_risk_score"]
    sig_fraud = fraud_rate >= t["fraud_rate"]
    sig_cb = cb_rate >= t["chargeback_rate_30d"]
    sig_spike = spike >= t["volume_spike_rate"]
    sig_segment = segment == t["high_segment"]

    signal_count = (
        sig_laundering.astype(int) + sig_fraud.astype(int) + sig_cb.astype(int)
        + sig_spike.astype(int) + sig_segment.astype(int)
    )

    def reason_codes(i):
        codes = []
        if sig_laundering.iloc[i]:
            codes.append("HIGH_LAUNDERING_RISK")
        if sig_fraud.iloc[i]:
            codes.append("HIGH_FRAUD_RATE")
        if sig_cb.iloc[i]:
            codes.append("HIGH_CHARGEBACK_RATE")
        if sig_spike.iloc[i]:
            codes.append("VOLUME_SPIKE")
        if sig_segment.iloc[i]:
            codes.append("HIGH_RISK_SEGMENT")
        return codes

    records = []
    for i in range(len(df)):
        n = int(signal_count.iloc[i])
        codes = reason_codes(i)
        recommend = n >= t["min_signals_to_suggest"]

        # action escalates with evidence
        if not recommend:
            action = "monitor"
        elif sig_laundering.iloc[i] and (sig_fraud.iloc[i] or sig_cb.iloc[i]):
            action = "decline"
        elif n >= 3:
            action = "decline"
        else:
            action = "step_up"

        records.append({
            "merchant_id": df["merchant_id"].iloc[i],
            "Merch_ID_DE42": df.get("Merch_ID_DE42", pd.Series([""] * len(df))).iloc[i],
            "merchant_name": df["merchant_name"].iloc[i],
            "merchant_risk_segment": segment.iloc[i],
            "laundering_risk_score": round(float(laundering.iloc[i]), 2),
            "fraud_rate": round(float(fraud_rate.iloc[i]), 4),
            "chargeback_rate_30d": round(float(cb_rate.iloc[i]), 4),
            "volume_spike_rate": round(float(spike.iloc[i]), 4),
            "blacklist_recommendation": "blacklist" if recommend else "monitor",
            "recommended_action": action,
            "reason_codes": "|".join(codes),
        })

    cols = [
        "merchant_id", "Merch_ID_DE42", "merchant_name", "merchant_risk_segment",
        "laundering_risk_score", "fraud_rate", "chargeback_rate_30d",
        "volume_spike_rate", "blacklist_recommendation", "recommended_action",
        "reason_codes",
    ]
    out = pd.DataFrame(records, columns=cols)
    # sort most risky first
    return out.sort_values(
        ["blacklist_recommendation", "laundering_risk_score"],
        ascending=[True, False],
    ).reset_index(drop=True)


def build_suggested_set(suggestions):
    """Return the set of merchant_ids recommended for blacklisting (for scoring)."""
    flagged = suggestions[suggestions["blacklist_recommendation"] == "blacklist"]
    return set(flagged["merchant_id"].astype(str))


def run(save=True):
    """Generate dynamic suggestions, optionally save the CSV."""
    suggestions = suggest_blacklist()
    if save:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        suggestions.to_csv(config.MERCHANT_BLACKLIST_SUGGESTIONS_FILE, index=False)
    return suggestions


if __name__ == "__main__":
    s = run()
    n_flagged = (s["blacklist_recommendation"] == "blacklist").sum()
    print(f"Merchant suggestions: {len(s)}  |  recommended for blacklist: {n_flagged}")
    print("Manual blacklist entries:", len(load_manual_blacklist()))
    print(s.head(10).to_string(index=False))
