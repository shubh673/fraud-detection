"""
Same-IP repetitive authorisation detection  (belongs mainly to Step 3).

Goal: detect an IP address issuing many authorisations in a very short time.

Two complementary methods (see config.IP_REPETITION_PARAMS):

  1. Literal rolling-window rules (production-correct):
        - 3+ transactions within 10 seconds
        - 5+ transactions within 30 seconds
        - 10+ transactions within 60 seconds
     These fire when real sub-minute bursts exist in the timestamps.

  2. Pre-aggregated 1h velocity counters (this synthetic dataset):
     The auth feed already provides ip_txn_count_1h / ip_card_count_1h. Normal
     traffic peaks at ~9 txns / 7 cards per IP-hour; attack IPs reach 80-160.
     We flag IPs whose counters are elevated. This is what fires on the supplied
     synthetic data, where timestamps are not sub-minute bursty.

Risk is escalated when the same IP spans multiple cardholders, merchants or
SubBINs. Produces outputs/ip_repetitive_authorisation_alerts.csv plus an IP
watchlist lookup the Step 1 scorer consumes.
"""

import json

import numpy as np
import pandas as pd

import config
import detection_utils as du


def _max_per_window(times_epoch, window_seconds):
    """Peak number of transactions inside any rolling window of given length."""
    if len(times_epoch) == 0:
        return 0
    counts, _ = du.forward_window_counts(times_epoch, window_seconds)
    return int(counts.max())


def _alert_for_ip(g, ip_hash, seq):
    """Build one alert for an IP from its (time-sorted) transactions."""
    p = config.IP_REPETITION_PARAMS
    times = g["_event_time"].astype("int64").to_numpy() // 1_000_000_000

    # --- method 1: literal rolling windows ---
    window_reasons = []
    max_per_10s = 0
    for window_seconds, min_txn in p["windows"]:
        peak = _max_per_window(times, window_seconds)
        if window_seconds == 10:
            max_per_10s = peak
        if peak >= min_txn:
            window_reasons.append(f"WINDOW_{min_txn}_IN_{window_seconds}S")

    # --- method 2: pre-aggregated 1h velocity counters ---
    max_txn_1h = int(pd.to_numeric(g.get("ip_txn_count_1h"), errors="coerce").fillna(0).max())
    max_card_1h = int(pd.to_numeric(g.get("ip_card_count_1h"), errors="coerce").fillna(0).max())
    counter_hit = (max_txn_1h >= p["ip_txn_count_1h_min"]) or (max_card_1h >= p["ip_card_count_1h_min"])

    # an IP is only an alert if at least one method fired
    if not window_reasons and not counter_hit:
        return None

    txn_count = len(g)
    unique_cardholders = g["cardholder_id"].nunique()
    unique_merchants = g["merchant_id"].nunique() if "merchant_id" in g else 0
    unique_subbins = g["SubBIN"].nunique() if "SubBIN" in g else 0
    unique_devices = g["device_id"].nunique() if "device_id" in g else 0
    total_amount = float(g["Txn_Amt"].sum()) if "Txn_Amt" in g else 0.0

    multi_min = p["multi_entity_min"]
    multi_card = unique_cardholders >= multi_min
    multi_merchant = unique_merchants >= multi_min
    multi_subbin = unique_subbins >= multi_min

    reasons = ["SAME_IP_REPETITIVE_AUTH"] + window_reasons
    if counter_hit:
        reasons.append("HIGH_IP_VELOCITY_1H")
    if multi_card:
        reasons.append("MULTI_CARDHOLDER_SAME_IP")
    if multi_merchant:
        reasons.append("MULTI_MERCHANT_SAME_IP")
    if multi_subbin:
        reasons.append("MULTI_SUBBIN_SAME_IP")

    # ---- risk score (0-1000) ----
    score = 0.0
    score += min(250.0, max_per_10s * 80.0)            # real sub-minute intensity
    score += min(250.0, (max_txn_1h / max(p["ip_txn_count_1h_min"], 1)) * 90.0)  # 1h intensity
    score += 120.0 * len(window_reasons)
    score += 120.0 if multi_card else 0.0
    score += 100.0 if multi_merchant else 0.0
    score += 100.0 if multi_subbin else 0.0
    risk_score = int(min(1000, round(score)))
    severity = du.severity_from_score(risk_score)

    control = {
        "CRITICAL": "block_ip",
        "HIGH": "block_ip_temporarily",
        "MEDIUM": "throttle_ip",
        "LOW": "monitor_ip",
    }[severity]

    return {
        "alert_id": f"IPREP-{seq:06d}",
        "ip_address_hash": ip_hash,
        "alert_start_time": str(g["_event_time"].min()),
        "alert_end_time": str(g["_event_time"].max()),
        "transaction_count": txn_count,
        "unique_cardholders": int(unique_cardholders),
        "unique_merchants": int(unique_merchants),
        "unique_subbins": int(unique_subbins),
        "unique_devices": int(unique_devices),
        "total_amount": round(total_amount, 2),
        "max_transactions_per_10_seconds": max_per_10s,
        "max_ip_txn_count_1h": max_txn_1h,
        "risk_score": risk_score,
        "severity": severity,
        "recommended_control": control,
        "reason_codes": "|".join(reasons),
    }


def detect_ip_repetition(df):
    """Return a DataFrame of same-IP repetitive authorisation alerts."""
    p = config.IP_REPETITION_PARAMS
    smallest_min_txn = min(m for _, m in p["windows"])
    data = du.parse_event_time(df)

    # Pre-filter to IPs that could plausibly alert (cheap), then evaluate each.
    txn_sig = pd.to_numeric(data.get("ip_txn_count_1h"), errors="coerce").fillna(0)
    card_sig = pd.to_numeric(data.get("ip_card_count_1h"), errors="coerce").fillna(0)
    counter_ips = set(data.loc[
        (txn_sig >= p["ip_txn_count_1h_min"]) | (card_sig >= p["ip_card_count_1h_min"]),
        "ip_address_hash",
    ])
    sizes = data["ip_address_hash"].value_counts()
    busy_ips = set(sizes[sizes >= smallest_min_txn].index)
    candidate_ips = counter_ips | busy_ips

    alerts = []
    seq = 0
    for ip_hash, g in data[data["ip_address_hash"].isin(candidate_ips)].groupby(
        "ip_address_hash", sort=False
    ):
        g = g.sort_values("_event_time").reset_index(drop=True)
        alert = _alert_for_ip(g, ip_hash, seq)
        if alert is not None:
            alerts.append(alert)
            seq += 1

    cols = [
        "alert_id", "ip_address_hash", "alert_start_time", "alert_end_time",
        "transaction_count", "unique_cardholders", "unique_merchants",
        "unique_subbins", "unique_devices", "total_amount",
        "max_transactions_per_10_seconds", "max_ip_txn_count_1h", "risk_score",
        "severity", "recommended_control", "reason_codes",
    ]
    return pd.DataFrame(alerts, columns=cols)


def build_ip_watchlist(alerts):
    """Map each flagged IP to its alert severity (for real-time scoring)."""
    watch = {}
    for _, a in alerts.iterrows():
        watch[str(a["ip_address_hash"])] = {
            "severity": a["severity"],
            "risk_score": int(a["risk_score"]),
        }
    return watch


def run(df=None, save=True):
    if df is None:
        from data_loader import load_raw_transactions
        df = load_raw_transactions()

    alerts = detect_ip_repetition(df)
    watch = build_ip_watchlist(alerts)

    if save:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        alerts.to_csv(config.IP_REPETITION_ALERTS_FILE, index=False)
        with open(config.IP_REPETITION_LOOKUP_FILE, "w") as f:
            json.dump({"ips": watch}, f, indent=2)
    return alerts, watch


if __name__ == "__main__":
    a, w = run()
    print(f"IP repetitive alerts: {len(a)}  |  IPs on watchlist: {len(w)}")
    if len(a):
        print(a.head(10).to_string(index=False))
