"""
Client-requirement pipeline.

Runs the three client-requested capabilities in one go:
  1. BIN attack detection                 (Step 3)
  2. Same-IP repetitive authorisation     (Step 3)
  3. Merchant blacklist suggestions       (Step 1 enhancement)

It writes the alert CSVs plus the small lookup files that the Step 1 real-time
scorer consumes, and a summary JSON. Run from the project root:

    venv/Scripts/python.exe src/client_requirement_pipeline.py
"""

import json

import bin_attack_detection as bin_det
import config
import ip_repetition_detection as ip_det
import merchant_blacklist as mbl
from data_loader import load_raw_transactions


def _severity_counts(df):
    if "severity" not in df.columns or df.empty:
        return {}
    return df["severity"].value_counts().to_dict()


def main():
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading enriched authorisation transactions...")
    tx = load_raw_transactions()
    print(f"  rows={len(tx):,}")

    # 1. BIN attack detection
    print("\n[1/3] Detecting BIN / SubBIN attacks...")
    bin_alerts, bin_watch = bin_det.run(df=tx, save=True)
    print(f"  alerts={len(bin_alerts)}  SubBINs on watchlist={len(bin_watch)}")

    # 2. Same-IP repetitive authorisation
    print("\n[2/3] Detecting same-IP repetitive authorisations...")
    ip_alerts, ip_watch = ip_det.run(df=tx, save=True)
    print(f"  alerts={len(ip_alerts)}  IPs on watchlist={len(ip_watch)}")

    # 3. Merchant blacklist suggestions
    print("\n[3/3] Generating merchant blacklist suggestions...")
    suggestions = mbl.run(save=True)
    manual = mbl.load_manual_blacklist()
    n_suggested = int((suggestions["blacklist_recommendation"] == "blacklist").sum())
    print(f"  manual blacklist entries={len(manual)}  dynamic suggestions={n_suggested}")

    # Summary
    summary = {
        "transactions_scanned": int(len(tx)),
        "bin_attack": {
            "alerts": int(len(bin_alerts)),
            "subbins_on_watchlist": len(bin_watch),
            "severity_counts": _severity_counts(bin_alerts),
        },
        "ip_repetitive_auth": {
            "alerts": int(len(ip_alerts)),
            "ips_on_watchlist": len(ip_watch),
            "severity_counts": _severity_counts(ip_alerts),
        },
        "merchant_blacklist": {
            "manual_entries": len(manual),
            "dynamic_suggestions": n_suggested,
            "merchants_evaluated": int(len(suggestions)),
        },
        "outputs": {
            "bin_attack_alerts": str(config.BIN_ATTACK_ALERTS_FILE.relative_to(config.PROJECT_ROOT)),
            "ip_repetitive_alerts": str(config.IP_REPETITION_ALERTS_FILE.relative_to(config.PROJECT_ROOT)),
            "merchant_blacklist_suggestions": str(config.MERCHANT_BLACKLIST_SUGGESTIONS_FILE.relative_to(config.PROJECT_ROOT)),
            "bin_watchlist_lookup": str(config.BIN_ATTACK_LOOKUP_FILE.relative_to(config.PROJECT_ROOT)),
            "ip_watchlist_lookup": str(config.IP_REPETITION_LOOKUP_FILE.relative_to(config.PROJECT_ROOT)),
        },
    }
    with open(config.CLIENT_REQ_SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved summary -> {config.CLIENT_REQ_SUMMARY_FILE}")
    print("Step 1 scoring will pick up the new lookups on next run "
          "(call score_authorisation.reload_overlays() in a live process).")
    return summary


if __name__ == "__main__":
    main()
