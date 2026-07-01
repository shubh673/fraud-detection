"""
Prepare frontend-friendly JSON data for the fraud-detection dashboard.

Reads the existing pipeline outputs (Step 1 + client add-on) and converts them
into JSON files under frontend/public/data/. Also builds:
  - dashboard_summary.json  : all KPI counts + chart-ready distributions
  - combined_alert_queue.json
  - overlay_simulator.json   : real before/after scoring scenarios for page 6

This script does NOT modify any existing pipeline file. Run from project root:

    python scripts/prepare_dashboard_data.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
OUTPUTS = PROJECT_ROOT / "outputs"
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_PACK = PROJECT_ROOT / "fraud_detection_enriched_dataset_pack"
DEST = PROJECT_ROOT / "frontend" / "public" / "data"

sys.path.insert(0, str(SRC_DIR))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def records(df):
    """DataFrame -> list[dict] with numpy types coerced via pandas JSON."""
    return json.loads(df.to_json(orient="records"))


def write_json(name, obj):
    path = DEST / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    print(f"  wrote {path.relative_to(PROJECT_ROOT)}")


def read_csv_safe(path):
    if not path.exists():
        print(f"  WARNING: missing {path.relative_to(PROJECT_ROOT)} -> skipped")
        return None
    return pd.read_csv(path)


def split_codes(series):
    """Flatten a '|'-joined reason_codes column into a Counter."""
    counter = Counter()
    for val in series.dropna():
        for code in str(val).split("|"):
            code = code.strip()
            if code:
                counter[code] += 1
    return counter


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"Preparing dashboard data -> {DEST.relative_to(PROJECT_ROOT)}")

    # ---- raw tables ----
    sample = read_csv_safe(OUTPUTS / "sample_scored_transactions.csv")
    bin_alerts = read_csv_safe(OUTPUTS / "bin_attack_alerts.csv")
    ip_alerts = read_csv_safe(OUTPUTS / "ip_repetitive_authorisation_alerts.csv")
    suggestions = read_csv_safe(OUTPUTS / "merchant_blacklist_suggestions.csv")
    manual = read_csv_safe(CONFIG_DIR / "merchant_blacklist.csv")

    metrics = {}
    if (OUTPUTS / "model_metrics.json").exists():
        metrics = json.load(open(OUTPUTS / "model_metrics.json"))
    client_summary = {}
    if (OUTPUTS / "client_requirement_summary.json").exists():
        client_summary = json.load(open(OUTPUTS / "client_requirement_summary.json"))

    # ---- copy through the simple tables ----
    if sample is not None:
        write_json("sample_scored_transactions.json", records(sample))
    if bin_alerts is not None:
        write_json("bin_attack_alerts.json", records(bin_alerts))
    if ip_alerts is not None:
        write_json("ip_repetitive_authorisation_alerts.json", records(ip_alerts))
    if suggestions is not None:
        write_json("merchant_blacklist_suggestions.json", records(suggestions))
    if manual is not None:
        write_json("manual_merchant_blacklist.json", records(manual))
    write_json("model_metrics.json", metrics)

    # ---- fraud scenario distribution from the full dataset (true distribution) ----
    scenario_dist = {}
    auth_file = DATA_PACK / "ehi_authorisation_transactions_enriched.csv"
    if auth_file.exists():
        scen = pd.read_csv(auth_file, usecols=["fraud_scenario"])["fraud_scenario"]
        scenario_dist = {k: int(v) for k, v in scen.value_counts().items()}

    # ---- combined alert queue ----
    queue = []
    if bin_alerts is not None:
        for _, a in bin_alerts.iterrows():
            queue.append({
                "alert_type": "BIN_ATTACK",
                "entity_id": f"SubBIN {a['SubBIN']}",
                "severity": a["severity"],
                "risk_score": int(a["risk_score"]),
                "recommended_action": a["recommended_control"],
                "reason_codes": a["reason_codes"],
                "detail": {
                    "transaction_count": int(a["transaction_count"]),
                    "unique_cards": int(a["unique_cards"]),
                    "decline_rate": float(a["decline_rate"]),
                },
                "status": "open",
            })
    if ip_alerts is not None:
        for _, a in ip_alerts.iterrows():
            queue.append({
                "alert_type": "IP_REPETITIVE",
                "entity_id": str(a["ip_address_hash"]),
                "severity": a["severity"],
                "risk_score": int(a["risk_score"]),
                "recommended_action": a["recommended_control"],
                "reason_codes": a["reason_codes"],
                "detail": {
                    "transaction_count": int(a["transaction_count"]),
                    "unique_cardholders": int(a["unique_cardholders"]),
                    "max_ip_txn_count_1h": int(a["max_ip_txn_count_1h"]),
                },
                "status": "open",
            })
    if suggestions is not None:
        flagged = suggestions[suggestions["blacklist_recommendation"] == "blacklist"]
        for _, m in flagged.iterrows():
            sev = "HIGH" if m["recommended_action"] == "decline" else "MEDIUM"
            queue.append({
                "alert_type": "MERCHANT_BLACKLIST",
                "entity_id": f"{m['merchant_id']} ({m['merchant_name']})",
                "severity": sev,
                "risk_score": int(round(float(m["laundering_risk_score"]) * 10)),
                "recommended_action": m["recommended_action"],
                "reason_codes": m["reason_codes"],
                "detail": {
                    "laundering_risk_score": float(m["laundering_risk_score"]),
                    "fraud_rate": float(m["fraud_rate"]),
                    "chargeback_rate_30d": float(m["chargeback_rate_30d"]),
                },
                "status": "open",
            })
    write_json("combined_alert_queue.json", queue)

    # ---- top reason codes (across all detection sources) ----
    reason_counter = Counter()
    for tbl, col in [(bin_alerts, "reason_codes"), (ip_alerts, "reason_codes"),
                     (suggestions, "reason_codes"), (sample, "reason_codes")]:
        if tbl is not None and col in tbl.columns:
            reason_counter.update(split_codes(tbl[col]))
    top_reasons = [{"code": c, "count": n} for c, n in reason_counter.most_common(12)]

    # ---- severity distribution (BIN + IP alerts) ----
    severity_counter = Counter()
    for tbl in [bin_alerts, ip_alerts]:
        if tbl is not None and "severity" in tbl.columns:
            severity_counter.update(tbl["severity"].tolist())
    severity_dist = {k: int(v) for k, v in severity_counter.items()}

    # ---- risk-score distribution from the scored sample ----
    risk_bins = []
    if sample is not None and "final_risk_score" in sample.columns:
        bands = [(0, 190, "Approve (0-189)"), (190, 430, "Step-up (190-429)"),
                 (430, 1001, "Decline (430+)")]
        for lo, hi, label in bands:
            n = int(((sample["final_risk_score"] >= lo) & (sample["final_risk_score"] < hi)).sum())
            risk_bins.append({"band": label, "count": n})

    # ---- action distribution from the held-out test triage ----
    action_counts = {}
    fraud_rate_by_action = {}
    if metrics:
        te = metrics.get("triage_test_evaluation", {})
        action_counts = te.get("action_counts", {})
        fraud_rate_by_action = te.get("fraud_rate_by_action", {})

    # ---- KPI summary ----
    n_bin = 0 if bin_alerts is None else len(bin_alerts)
    n_ip = 0 if ip_alerts is None else len(ip_alerts)
    n_manual = 0 if manual is None else len(manual)
    n_suggest = 0
    if suggestions is not None:
        n_suggest = int((suggestions["blacklist_recommendation"] == "blacklist").sum())
    n_critical = severity_dist.get("CRITICAL", 0)
    n_high = severity_dist.get("HIGH", 0)

    summary = {
        "transactions_scanned": client_summary.get("transactions_scanned",
                                                    metrics.get("n_rows", 0)),
        "fraud_rate": metrics.get("fraud_rate", 0.0),
        "best_model": metrics.get("best_model", "n/a"),
        "triage_thresholds": metrics.get("triage_thresholds", {}),
        "test_set_size": metrics.get("split", {}).get("test", 0),
        "action_counts": action_counts,
        "fraud_rate_by_action": fraud_rate_by_action,
        "fraud_caught_step_up_or_decline":
            metrics.get("triage_test_evaluation", {}).get("fraud_caught_step_up_or_decline"),
        "recommended_action_agreement": metrics.get("recommended_action_agreement"),
        "kpis": {
            "transactions_scanned": client_summary.get("transactions_scanned",
                                                        metrics.get("n_rows", 0)),
            "fraud_rate": metrics.get("fraud_rate", 0.0),
            "approve": action_counts.get("approve", 0),
            "step_up": action_counts.get("step_up", 0),
            "decline": action_counts.get("decline", 0),
            "bin_attack_alerts": n_bin,
            "ip_repetitive_alerts": n_ip,
            "manual_blacklist": n_manual,
            "dynamic_suggestions": n_suggest,
            "critical_alerts": n_critical,
            "high_alerts": n_high,
        },
        "charts": {
            "action_distribution": action_counts,
            "fraud_scenario_distribution": scenario_dist,
            "risk_score_distribution": risk_bins,
            "severity_distribution": severity_dist,
            "top_reason_codes": top_reasons,
        },
    }
    write_json("dashboard_summary.json", summary)

    # ---- overlay simulator (real before/after scoring) ----
    build_overlay_simulator()

    print("Done.")


def build_overlay_simulator():
    """
    Produce genuine before/after (Step 1 only vs Step 1 + overlays) scoring for
    a curated set of transactions, so the dashboard simulator is accurate.
    Degrades gracefully if the trained model is unavailable.
    """
    try:
        import joblib
        import config
        import rules_engine as rules
        import score_authorisation as scorer
        from data_loader import load_enriched_dataset
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  overlay_simulator skipped (import failed: {exc})")
        write_json("overlay_simulator.json", [])
        return

    if not config.MODEL_PATH.exists():
        print("  overlay_simulator skipped (model not trained yet)")
        write_json("overlay_simulator.json", [])
        return

    bundle = joblib.load(config.MODEL_PATH)
    thr = bundle["thresholds"]
    df = load_enriched_dataset()

    # watchlists / blacklists for picking demonstrative rows
    bin_watch = json.load(open(config.BIN_ATTACK_LOOKUP_FILE)).get("subbins", {}) \
        if config.BIN_ATTACK_LOOKUP_FILE.exists() else {}
    ip_watch = json.load(open(config.IP_REPETITION_LOOKUP_FILE)).get("ips", {}) \
        if config.IP_REPETITION_LOOKUP_FILE.exists() else {}
    manual = scorer.mbl.load_manual_blacklist()

    def base_score(txn):
        """Step 1 only (no client overlays)."""
        row = {c: txn.get(c) for c in bundle["all_features"]}
        X = pd.DataFrame([row], columns=bundle["all_features"])
        if "MCC_Code" in X.columns:
            X["MCC_Code"] = X["MCC_Code"].astype("string")
        proba = float(bundle["model"].predict_proba(X)[:, 1][0])
        rscore, reasons = rules.apply_rules(txn)
        final = rules.combine_scores(proba, rscore, ml_weight=thr.get("ml_weight"))
        action = rules.decide_action(final, thr["step_up"], thr["decline"])
        return {
            "fraud_probability": round(proba, 4),
            "rule_risk_score": int(rscore),
            "final_risk_score": int(final),
            "recommended_action": action,
            "reason_codes": reasons,
        }

    overlay_codes = {
        "BLACKLISTED_MERCHANT", "HIGH_RISK_MERCHANT_BLACKLIST_SUGGESTED",
        "BIN_ATTACK_PATTERN", "SAME_IP_REPETITIVE_AUTH",
    }

    # A pool of genuinely clean transactions (no overlay would fire as-is) so the
    # what-if scenarios below show a clear before/after on the same baseline.
    suggested_ids = set()
    if (OUTPUTS / "merchant_blacklist_suggestions.csv").exists():
        sug = pd.read_csv(OUTPUTS / "merchant_blacklist_suggestions.csv", dtype=str)
        suggested_ids = set(sug.loc[sug["blacklist_recommendation"] == "blacklist", "merchant_id"])
    clean = df[
        (df["fraud_scenario"] == "none")
        & (df["amount_vs_avg_ratio"] < 1.2)
        & (~df["SubBIN"].astype(str).isin(bin_watch))
        & (~df["ip_address_hash"].astype(str).isin(ip_watch))
        & (~df["merchant_id"].astype(str).isin(set(manual) | suggested_ids))
    ].reset_index(drop=True)

    def clean_row(i):
        return clean.iloc[i % len(clean)].to_dict()

    def pick(mask, label):
        sub = df[mask]
        return None if len(sub) == 0 else {"label": label, "txn": sub.iloc[0].to_dict()}

    picks = []
    # 1. clean / low risk -> approve, no overlay
    if len(clean):
        picks.append({"label": "Normal low-risk purchase", "txn": clean_row(0)})
    # 2. ML-driven fraud (ATO)
    picks.append(pick(df["fraud_scenario"] == "account_takeover", "Account-takeover pattern (ML-driven)"))
    # 3. CNP fraud
    picks.append(pick(df["fraud_scenario"] == "card_not_present", "Card-not-present fraud (ML + rules)"))
    # 4. what-if: clean txn routed through an attacked SubBIN
    if bin_watch and len(clean):
        picks.append({"label": "Clean txn on a SubBIN under BIN attack (what-if)",
                      "txn": {**clean_row(1), "SubBIN": int(list(bin_watch)[0])}})
    # 5. what-if: clean txn from a repetitive-auth IP
    if ip_watch and len(clean):
        picks.append({"label": "Clean txn from a repetitive-auth IP (what-if)",
                      "txn": {**clean_row(2), "ip_address_hash": list(ip_watch)[0]}})
    # 6. blacklisted merchant -> decline
    decl = [m for m, v in manual.items() if v["action"] == "decline"]
    if decl and len(clean):
        picks.append({"label": "Merchant on manual blacklist (decline)",
                      "txn": {**clean_row(3), "merchant_id": decl[0]}})
    # 7. blacklisted merchant -> step_up
    su = [m for m, v in manual.items() if v["action"] == "step_up"]
    if su and len(clean):
        picks.append({"label": "Merchant on manual blacklist (step-up)",
                      "txn": {**clean_row(4), "merchant_id": su[0]}})

    picks = [p for p in picks if p]

    scenarios = []
    for i, item in enumerate(picks):
        txn = item["txn"]
        base = base_score(txn)
        full = scorer.score_transaction(txn)
        # overlays are precisely the four client-add-on reason codes that fired
        overlay_reasons = [r for r in full["reason_codes"] if r in overlay_codes]
        scenarios.append({
            "id": f"SIM-{i:02d}",
            "label": item["label"],
            "transaction": {
                "transaction_id": str(txn.get("transaction_id", f"SIM-{i:02d}")),
                "merchant_id": str(txn.get("merchant_id", "")),
                "SubBIN": str(txn.get("SubBIN", "")),
                "ip_address_hash": str(txn.get("ip_address_hash", "")),
                "Txn_Amt": float(txn.get("Txn_Amt", 0) or 0),
                "Txn_Ctry": str(txn.get("Txn_Ctry", "")),
                "is_online": int(txn.get("is_online", 0) or 0),
                "fraud_scenario": str(txn.get("fraud_scenario", "")),
                "actual_is_fraud": int(txn.get("is_fraud", 0) or 0),
            },
            "base": base,
            "final": full,
            "overlay_reason_codes": overlay_reasons,
        })

    write_json("overlay_simulator.json", scenarios)


if __name__ == "__main__":
    main()
