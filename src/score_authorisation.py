"""
Real-time scoring entry point for Step 1.

Exposes:

    score_transaction(transaction: dict) -> dict

Returns:
    {
      "fraud_probability": float,
      "rule_risk_score": int,
      "final_risk_score": int,
      "recommended_action": "approve" | "step_up" | "decline",
      "reason_codes": list[str]
    }

The trained model bundle (ML pipeline + tuned thresholds) is loaded once and
cached. Missing feature fields are tolerated: the model's imputers fill numeric
gaps and unknown categories are ignored by the OneHotEncoder.
"""

import json

import joblib
import pandas as pd

import config
import rules_engine as rules
import merchant_blacklist as mbl

_BUNDLE = None
_OVERLAYS = None


def _load_bundle():
    global _BUNDLE
    if _BUNDLE is None:
        if not config.MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at {config.MODEL_PATH}. "
                "Run: python src/train_step1_model.py first."
            )
        _BUNDLE = joblib.load(config.MODEL_PATH)
    return _BUNDLE


def _read_json(path, key, default):
    if path.exists():
        try:
            return json.load(open(path)).get(key, default)
        except (ValueError, OSError):
            return default
    return default


def _load_overlays():
    """
    Load the client-requirement lookups consumed at scoring time:
      - manual merchant blacklist (config/merchant_blacklist.csv)
      - dynamic suggested-blacklist merchant set (suggestions CSV)
      - BIN-attack SubBIN watchlist (lookup JSON)
      - repetitive-IP watchlist (lookup JSON)
    All are optional; scoring degrades gracefully if a file is missing.
    """
    global _OVERLAYS
    if _OVERLAYS is None:
        suggested = set()
        if config.MERCHANT_BLACKLIST_SUGGESTIONS_FILE.exists():
            sug = pd.read_csv(config.MERCHANT_BLACKLIST_SUGGESTIONS_FILE, dtype=str)
            suggested = mbl.build_suggested_set(sug)
        _OVERLAYS = {
            "manual_blacklist": mbl.load_manual_blacklist(),
            "suggested_blacklist": suggested,
            "bin_watch": _read_json(config.BIN_ATTACK_LOOKUP_FILE, "subbins", {}),
            "ip_watch": _read_json(config.IP_REPETITION_LOOKUP_FILE, "ips", {}),
        }
    return _OVERLAYS


def reload_overlays():
    """Clear the overlay cache (call after re-running the detection pipeline)."""
    global _OVERLAYS
    _OVERLAYS = None


def _apply_overlays(transaction):
    """
    Apply the client-requirement overlays (blacklist + Step 3 watchlists).
    Returns (extra_rule_score, reason_codes, forced_action) where forced_action
    is None / "step_up" / "decline".
    """
    ov = _load_overlays()
    w = config.OVERLAY_WEIGHTS
    extra = 0
    reasons = []
    forced_action = None  # None < step_up < decline

    merchant_id = str(transaction.get("merchant_id", ""))
    subbin = str(transaction.get("SubBIN", ""))
    ip_hash = str(transaction.get("ip_address_hash", ""))

    # --- Manual merchant blacklist (authoritative) ---
    entry = ov["manual_blacklist"].get(merchant_id)
    if entry:
        reasons.append("BLACKLISTED_MERCHANT")
        if entry["action"] == "decline":
            forced_action = "decline"
        elif entry["action"] in ("step_up", "review"):
            forced_action = "step_up"

    # --- Dynamic suggested blacklist (advisory) ---
    if merchant_id in ov["suggested_blacklist"]:
        reasons.append("HIGH_RISK_MERCHANT_BLACKLIST_SUGGESTED")
        extra += w["blacklist_suggested"]

    # --- BIN attack pattern (SubBIN watchlist) ---
    if subbin in ov["bin_watch"]:
        reasons.append("BIN_ATTACK_PATTERN")
        extra += w["bin_attack_pattern"]

    # --- Same-IP repetitive authorisation (IP watchlist) ---
    if ip_hash in ov["ip_watch"]:
        reasons.append("SAME_IP_REPETITIVE_AUTH")
        extra += w["same_ip_repetitive"]

    return extra, reasons, forced_action


def _ml_probability(bundle, transaction):
    """Build a one-row frame with the expected feature columns and predict."""
    row = {}
    for col in bundle["all_features"]:
        row[col] = transaction.get(col, None)
    X = pd.DataFrame([row], columns=bundle["all_features"])
    if "MCC_Code" in X.columns:
        X["MCC_Code"] = X["MCC_Code"].astype("string")
    proba = bundle["model"].predict_proba(X)[:, 1][0]
    return float(proba)


def score_transaction(transaction):
    """Score a single authorisation transaction (dict) in real time."""
    bundle = _load_bundle()
    thr = bundle["thresholds"]

    # 1. ML fraud probability
    fraud_probability = _ml_probability(bundle, transaction)

    # 2. Deterministic transaction-level rule overlay (Step 1)
    rule_risk_score, reason_codes = rules.apply_rules(transaction)

    # 3. Client-requirement overlays: blacklist + Step 3 watchlists
    extra_score, overlay_reasons, forced_action = _apply_overlays(transaction)
    rule_risk_score = int(min(1000, rule_risk_score + extra_score))
    reason_codes = reason_codes + overlay_reasons

    # 4. Blend ML + rules into a single 0-1000 score
    final_risk_score = rules.combine_scores(
        fraud_probability, rule_risk_score, ml_weight=thr.get("ml_weight")
    )

    # 5. Map to an action using tuned thresholds
    recommended_action = rules.decide_action(
        final_risk_score, thr["step_up"], thr["decline"]
    )

    # 6. Apply blacklist forcing (manual blacklist is authoritative).
    #    - decline action: force decline
    #    - step_up/review action: ensure at least step_up
    rank = {"approve": 0, "step_up": 1, "decline": 2}
    if forced_action and rank[forced_action] > rank[recommended_action]:
        recommended_action = forced_action
        floor = thr["decline"] if forced_action == "decline" else thr["step_up"]
        final_risk_score = max(final_risk_score, floor)

    # Add an ML reason code when the model itself is the main driver
    if fraud_probability >= 0.5 and "ML_HIGH_FRAUD_PROBABILITY" not in reason_codes:
        reason_codes = ["ML_HIGH_FRAUD_PROBABILITY"] + reason_codes

    return {
        "fraud_probability": round(fraud_probability, 4),
        "rule_risk_score": int(rule_risk_score),
        "final_risk_score": int(final_risk_score),
        "recommended_action": recommended_action,
        "reason_codes": reason_codes,
    }


if __name__ == "__main__":
    import json

    # Example: an obviously risky card-not-present / ATO transaction
    example = {
        "Txn_Amt": 1450.0,
        "is_online": 1,
        "cnp_channel": "ecommerce",
        "is_international": 1,
        "high_risk_country": 1,
        "card_network": "VISA",
        "card_type": "CREDIT",
        "cvv_result": "N",
        "avs_result": "N",
        "3ds_result": "failed",
        "3ds_authenticated": 0,
        "velocity_1h": 7,
        "velocity_24h": 20,
        "velocity_7d": 40,
        "amount_vs_avg_ratio": 6.5,
        "new_country": 1,
        "new_merchant": 1,
        "device_fingerprint_match": 0,
        "ip_country_match": 0,
        "password_reset_last_7d": 1,
        "email_changed_last_7d": 1,
        "login_failed_count_24h": 5,
        "ip_card_count_1h": 14,
        "ip_txn_count_1h": 22,
        "Txn_Ctry": "NGA",
        "ip_country": "RUS",
        "MCC_Code": 5999,
        "risk_segment": "HIGH",
        "merchant_risk_segment": "HIGH",
    }
    print(json.dumps(score_transaction(example), indent=2))
