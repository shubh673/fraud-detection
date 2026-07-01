"""
Rule-based overlay for Step 1.

This is a deterministic, explainable layer that runs alongside the ML model.
It inspects raw authorisation signals and returns:
  - rule_risk_score : int (sum of triggered rule weights, capped 0-1000)
  - reason_codes    : list[str] explaining which rules fired

The rules target the fraud patterns called out for Step 1:
  card-not-present, account takeover, counterfeit, lost/stolen,
  behavioural anomaly, and transaction-level BIN attack signals.
"""

import config

W = config.RULE_WEIGHTS
T = config.RULE_THRESHOLDS


def _num(txn, key, default=0):
    """Safe numeric getter (handles missing / None / NaN)."""
    val = txn.get(key, default)
    if val is None:
        return default
    try:
        f = float(val)
        if f != f:  # NaN check
            return default
        return f
    except (TypeError, ValueError):
        return default


def _str(txn, key, default=""):
    val = txn.get(key, default)
    if val is None:
        return default
    return str(val)


def _is_online(txn):
    """Online / card-not-present transaction?"""
    if _num(txn, "is_online", 0) >= 1:
        return True
    return _str(txn, "cnp_channel", "not_cnp") not in ("", "not_cnp", "nan")


def apply_rules(txn):
    """
    Apply all rules to one transaction dict.
    Returns (rule_risk_score:int, reason_codes:list[str]).
    """
    score = 0
    reasons = []

    online = _is_online(txn)
    device_match = _num(txn, "device_fingerprint_match", 1)
    ip_match = _num(txn, "ip_country_match", 1)

    # 1. High velocity + new device / IP mismatch
    if _num(txn, "velocity_1h") >= T["velocity_1h_high"] and (
        device_match == 0 or ip_match == 0
    ):
        score += W["high_velocity_new_device"]
        reasons.append("HIGH_VELOCITY_NEW_DEVICE")

    # 2. CVV mismatch in an online / CNP transaction
    if online and _str(txn, "cvv_result").upper() == "N":
        score += W["cvv_mismatch_online"]
        reasons.append("CVV_MISMATCH_ONLINE")

    # 3. AVS mismatch in an online / CNP transaction (N = no match)
    if online and _str(txn, "avs_result").upper() == "N":
        score += W["avs_mismatch_online"]
        reasons.append("AVS_MISMATCH_ONLINE")

    # 4. Account takeover signals
    if _num(txn, "password_reset_last_7d") >= 1:
        score += W["ato_password_reset"]
        reasons.append("ATO_PASSWORD_RESET_7D")
    if _num(txn, "email_changed_last_7d") >= 1:
        score += W["ato_email_changed"]
        reasons.append("ATO_EMAIL_CHANGED_7D")
    if _num(txn, "login_failed_count_24h") >= T["login_failed_count_24h_high"]:
        score += W["ato_login_failures"]
        reasons.append("ATO_LOGIN_FAILURES_24H")

    # 5. BIN attack style signals (transaction-level)
    if _num(txn, "ip_card_count_1h") >= T["ip_card_count_1h_high"]:
        score += W["bin_attack_ip_cards"]
        reasons.append("BIN_ATTACK_IP_MANY_CARDS")
    if _num(txn, "ip_txn_count_1h") >= T["ip_txn_count_1h_high"]:
        score += W["bin_attack_ip_txns"]
        reasons.append("BIN_ATTACK_IP_HIGH_TXN_RATE")

    # 6. Large amount vs cardholder average + new country / new merchant
    if _num(txn, "amount_vs_avg_ratio") >= T["amount_vs_avg_ratio_high"] and (
        _num(txn, "new_country") == 1 or _num(txn, "new_merchant") == 1
    ):
        score += W["amount_anomaly_new_context"]
        reasons.append("AMOUNT_ANOMALY_NEW_CONTEXT")

    # 7. Online + high-risk country with no 3DS authentication
    if online and _num(txn, "high_risk_country") == 1 and _num(txn, "3ds_authenticated") == 0:
        score += W["no_3ds_online_highrisk"]
        reasons.append("ONLINE_HIGHRISK_NO_3DS")

    # 8. IP country mismatch in a high-risk geography (counterfeit/lost-stolen hint)
    if ip_match == 0 and _num(txn, "high_risk_country") == 1:
        score += W["high_risk_geo_mismatch"]
        reasons.append("HIGH_RISK_GEO_IP_MISMATCH")

    # Cap to the 0-1000 scale used by the final score.
    score = int(min(score, 1000))
    return score, reasons


def combine_scores(fraud_probability, rule_risk_score, ml_weight=None):
    """
    Blend the ML probability and the rule score into a single 0-1000 score.

        final = ml_weight * (proba * 1000) + rule_risk_score   (capped 0-1000)
    """
    if ml_weight is None:
        ml_weight = config.ML_WEIGHT
    ml_component = ml_weight * (float(fraud_probability) * 1000.0)
    final = int(round(ml_component + rule_risk_score))
    return max(0, min(final, 1000))


def decide_action(final_risk_score, step_up_threshold=None, decline_threshold=None):
    """Map a final 0-1000 score to approve / step_up / decline."""
    step_up_threshold = step_up_threshold if step_up_threshold is not None else config.THRESHOLD_STEP_UP
    decline_threshold = decline_threshold if decline_threshold is not None else config.THRESHOLD_DECLINE
    if final_risk_score >= decline_threshold:
        return "decline"
    if final_risk_score >= step_up_threshold:
        return "step_up"
    return "approve"


if __name__ == "__main__":
    demo = {
        "is_online": 1,
        "cnp_channel": "ecommerce",
        "cvv_result": "N",
        "avs_result": "N",
        "velocity_1h": 6,
        "device_fingerprint_match": 0,
        "password_reset_last_7d": 1,
        "ip_card_count_1h": 12,
        "amount_vs_avg_ratio": 4.0,
        "new_country": 1,
        "high_risk_country": 1,
        "3ds_authenticated": 0,
        "ip_country_match": 0,
    }
    s, r = apply_rules(demo)
    print("rule_risk_score:", s)
    print("reason_codes:", r)
