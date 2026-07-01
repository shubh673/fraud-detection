"""
BIN / SubBIN attack detection  (belongs mainly to Step 3).

Scans the enriched authorisation transactions for SubBIN-level attack patterns:
  - many transactions on the same SubBIN (card enumeration)
  - many unique cards on the same SubBIN
  - same IP/device reused across multiple cards
  - low-value repeated attempts (card testing)
  - high decline / failed-auth rate
  - same country / merchant repeated in the burst

How detection works on this dataset
------------------------------------
The synthetic transaction timestamps are spread out, so a literal "N txns in T
seconds" window does not fire. The BIN-attack velocity is instead carried by the
auth feed's pre-aggregated 1h counters (ip_card_count_1h / ip_txn_count_1h),
which are very high for attack traffic (normal max ~7/9 vs attack 30-160) and
come with the card-testing signature (low value, ~100% decline). We flag those
attempt rows and aggregate them per SubBIN into one alert.

Produces outputs/bin_attack_alerts.csv and a SubBIN watchlist lookup that the
Step 1 real-time scorer consumes.
"""

import json

import pandas as pd

import config
import detection_utils as du


def _suspicious_attempts(df):
    """Boolean mask of rows that carry the BIN-attack attempt signature."""
    p = config.BIN_ATTACK_PARAMS
    card_sig = pd.to_numeric(df.get("ip_card_count_1h"), errors="coerce").fillna(0)
    txn_sig = pd.to_numeric(df.get("ip_txn_count_1h"), errors="coerce").fillna(0)
    return (card_sig >= p["card_signal_min"]) | (txn_sig >= p["txn_signal_min"])


def _alert_for_subbin(rows, subbin):
    """Build one alert from all suspicious attempts on a SubBIN."""
    p = config.BIN_ATTACK_PARAMS

    txn_count = len(rows)
    unique_cards = rows["cardholder_id"].nunique()
    unique_merchants = rows["merchant_id"].nunique() if "merchant_id" in rows else 0
    unique_ips = rows["ip_address_hash"].nunique() if "ip_address_hash" in rows else 0
    unique_devices = rows["device_id"].nunique() if "device_id" in rows else 0
    avg_amount = float(rows["Txn_Amt"].mean()) if "Txn_Amt" in rows else 0.0
    decline_rate = float(rows["_declined"].mean())
    max_ip_txn_1h = int(rows["ip_txn_count_1h"].max()) if "ip_txn_count_1h" in rows else 0

    shared_ip_multi_card = False
    if "ip_address_hash" in rows:
        cards_per_ip = rows.groupby("ip_address_hash")["cardholder_id"].nunique()
        shared_ip_multi_card = bool((cards_per_ip >= p["shared_ip_card_count"]).any())

    low_value_share = 0.0
    if "Txn_Amt" in rows:
        low_value_share = float((rows["Txn_Amt"] <= p["low_value_amount"]).mean())

    same_country = False
    if "Txn_Ctry" in rows and txn_count:
        same_country = bool(rows["Txn_Ctry"].value_counts(normalize=True).iloc[0] >= 0.8)
    same_merchant = bool(unique_merchants == 1 and txn_count > 1)

    # ---- reason codes ----
    reasons = ["MANY_TXN_SAME_SUBBIN"]
    if unique_cards >= p["min_unique_cards"]:
        reasons.append("MANY_UNIQUE_CARDS_SAME_SUBBIN")
    if shared_ip_multi_card:
        reasons.append("SHARED_IP_MULTI_CARD")
    if low_value_share >= p["low_value_share"]:
        reasons.append("LOW_VALUE_REPEATED_ATTEMPTS")
    if decline_rate >= p["high_decline_rate"]:
        reasons.append("HIGH_DECLINE_RATE")
    if same_country:
        reasons.append("BURST_SAME_COUNTRY")
    if same_merchant:
        reasons.append("BURST_SAME_MERCHANT")

    # ---- risk score (0-1000) ----
    score = 0.0
    score += min(250.0, (txn_count / p["min_attempts"]) * 60.0)
    score += min(250.0, (unique_cards / p["min_unique_cards"]) * 60.0)
    score += decline_rate * 250.0
    score += low_value_share * 150.0
    score += 150.0 if shared_ip_multi_card else 0.0
    risk_score = int(min(1000, round(score)))
    severity = du.severity_from_score(risk_score)

    control = {
        "CRITICAL": "block_subbin",
        "HIGH": "block_subbin_temporarily",
        "MEDIUM": "throttle_subbin",
        "LOW": "monitor_subbin",
    }[severity]

    return {
        "alert_id": f"BIN-{subbin}",
        "SubBIN": subbin,
        "alert_start_time": str(rows["_event_time"].min()),
        "alert_end_time": str(rows["_event_time"].max()),
        "transaction_count": txn_count,
        "unique_cards": int(unique_cards),
        "unique_merchants": int(unique_merchants),
        "unique_ips": int(unique_ips),
        "unique_devices": int(unique_devices),
        "avg_amount": round(avg_amount, 2),
        "decline_rate": round(decline_rate, 4),
        "max_ip_txn_count_1h": max_ip_txn_1h,
        "risk_score": risk_score,
        "severity": severity,
        "recommended_control": control,
        "reason_codes": "|".join(reasons),
    }


def detect_bin_attacks(df):
    """Return a DataFrame of BIN-attack alerts (one per attacked SubBIN)."""
    p = config.BIN_ATTACK_PARAMS
    data = du.parse_event_time(df)
    data["_declined"] = du.declined_flag(data).values

    suspicious = data[_suspicious_attempts(data).values]

    alerts = []
    for subbin, rows in suspicious.groupby("SubBIN", sort=True):
        if len(rows) < p["min_attempts"] or rows["cardholder_id"].nunique() < p["min_unique_cards"]:
            continue
        alerts.append(_alert_for_subbin(rows, subbin))

    cols = [
        "alert_id", "SubBIN", "alert_start_time", "alert_end_time",
        "transaction_count", "unique_cards", "unique_merchants", "unique_ips",
        "unique_devices", "avg_amount", "decline_rate", "max_ip_txn_count_1h",
        "risk_score", "severity", "recommended_control", "reason_codes",
    ]
    return pd.DataFrame(alerts, columns=cols)


def build_subbin_watchlist(alerts):
    """Map each attacked SubBIN to its alert severity (for real-time scoring)."""
    watch = {}
    for _, a in alerts.iterrows():
        watch[str(a["SubBIN"])] = {
            "severity": a["severity"],
            "risk_score": int(a["risk_score"]),
        }
    return watch


def run(df=None, save=True):
    """Detect BIN attacks, optionally save alerts + watchlist lookup."""
    if df is None:
        from data_loader import load_raw_transactions
        df = load_raw_transactions()

    alerts = detect_bin_attacks(df)
    watch = build_subbin_watchlist(alerts)

    if save:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        alerts.to_csv(config.BIN_ATTACK_ALERTS_FILE, index=False)
        with open(config.BIN_ATTACK_LOOKUP_FILE, "w") as f:
            json.dump({"subbins": watch}, f, indent=2)
    return alerts, watch


if __name__ == "__main__":
    a, w = run()
    print(f"BIN attack alerts: {len(a)}  |  SubBINs on watchlist: {len(w)}")
    if len(a):
        print(a.to_string(index=False))
