"""
Train + evaluate the Step 1 real-time fraud triage model.

Pipeline:
  1. Load enriched authorisation data (+ joined baselines/profiles).
  2. Build non-leaky features and the target (is_fraud).
  3. Train/val/test split (stratified).
  4. Train Logistic Regression and Random Forest.
  5. Evaluate both (ROC AUC, PR AUC, precision/recall/F1, confusion matrix,
     classification report) and pick the best by PR AUC.
  6. Tune triage thresholds on the validation set.
  7. Save the model bundle (joblib) + metrics + feature list + sample scores.
"""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

import config
import features as feat
import rules_engine as rules
from data_loader import load_enriched_dataset


def _build_models():
    """Return the candidate models wrapped in a preprocessing pipeline each."""
    return {
        "logistic_regression": Pipeline(steps=[
            ("pre", feat.build_preprocessor()),
            ("clf", LogisticRegression(
                max_iter=2000,
                class_weight="balanced",
                random_state=config.RANDOM_STATE,
            )),
        ]),
        "random_forest": Pipeline(steps=[
            ("pre", feat.build_preprocessor()),
            ("clf", RandomForestClassifier(
                n_estimators=300,
                max_depth=None,
                min_samples_leaf=2,
                class_weight="balanced",
                n_jobs=-1,
                random_state=config.RANDOM_STATE,
            )),
        ]),
    }


def _evaluate(name, model, X, y):
    """Compute the full metric set for a fitted model on (X, y)."""
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    return {
        "model": name,
        "roc_auc": float(roc_auc_score(y, proba)),
        "pr_auc": float(average_precision_score(y, proba)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y, pred).tolist(),
        "classification_report": classification_report(y, pred, zero_division=0, output_dict=True),
    }


def _rule_scores_for_frame(df):
    """Run the rules engine across a DataFrame, return array of rule_risk_scores."""
    records = df.to_dict(orient="records")
    return np.array([rules.apply_rules(r)[0] for r in records], dtype=float)


def _tune_thresholds(proba, rule_scores, y_true):
    """
    Pick step_up / decline thresholds on the validation set.

    Strategy (practical, not exhaustive): sweep candidate decline thresholds and
    choose the one maximising F1 of (action==decline) vs is_fraud. Then pick a
    step_up threshold that captures additional fraud at reasonable precision.
    Falls back to config defaults if the sweep finds nothing useful.
    """
    final = np.array([
        rules.combine_scores(p, r) for p, r in zip(proba, rule_scores)
    ])

    best = {"decline": config.THRESHOLD_DECLINE, "f1": -1.0}
    for thr in range(300, 1001, 10):
        decline_pred = (final >= thr).astype(int)
        if decline_pred.sum() == 0:
            continue
        f1 = f1_score(y_true, decline_pred, zero_division=0)
        if f1 > best["f1"]:
            best = {"decline": thr, "f1": f1}

    decline_thr = best["decline"]

    # step_up threshold: lower band that recovers more fraud before outright decline.
    best_su = {"step_up": config.THRESHOLD_STEP_UP, "recall": -1.0}
    for thr in range(150, decline_thr, 10):
        flagged = (final >= thr).astype(int)
        rec = recall_score(y_true, flagged, zero_division=0)
        prec = precision_score(y_true, flagged, zero_division=0)
        # require a minimum precision so we don't step-up everything
        if prec >= 0.30 and rec > best_su["recall"]:
            best_su = {"step_up": thr, "recall": rec}

    step_up_thr = min(best_su["step_up"], decline_thr - 10)
    return int(step_up_thr), int(decline_thr)


def _triage_eval(proba, rule_scores, y_true, step_up_thr, decline_thr):
    """Report how the final triage actions line up with actual fraud."""
    final = np.array([rules.combine_scores(p, r) for p, r in zip(proba, rule_scores)])
    actions = [rules.decide_action(f, step_up_thr, decline_thr) for f in final]
    actions = np.array(actions)

    def rate(mask):
        return float(y_true[mask].mean()) if mask.sum() > 0 else 0.0

    return {
        "step_up_threshold": step_up_thr,
        "decline_threshold": decline_thr,
        "action_counts": {a: int((actions == a).sum()) for a in ["approve", "step_up", "decline"]},
        "fraud_rate_by_action": {
            "approve": rate(actions == "approve"),
            "step_up": rate(actions == "step_up"),
            "decline": rate(actions == "decline"),
        },
        "fraud_caught_step_up_or_decline": float(
            y_true[(actions != "approve")].sum() / max(y_true.sum(), 1)
        ),
    }


def main():
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading enriched dataset...")
    df = load_enriched_dataset()
    print(f"  rows={len(df):,}  fraud_rate={df[config.TARGET].mean():.4f}")

    X, y = feat.build_xy(df)

    # Stratified split: 60% train / 20% val / 20% test
    X_train, X_test, y_train, y_test, df_train, df_test = train_test_split(
        X, y, df, test_size=config.TEST_SIZE, stratify=y, random_state=config.RANDOM_STATE
    )
    val_fraction = config.VAL_SIZE / (1.0 - config.TEST_SIZE)
    X_tr, X_val, y_tr, y_val, df_tr, df_val = train_test_split(
        X_train, y_train, df_train, test_size=val_fraction,
        stratify=y_train, random_state=config.RANDOM_STATE
    )
    print(f"  train={len(X_tr):,}  val={len(X_val):,}  test={len(X_test):,}")

    # Train + evaluate candidate models
    results = {}
    fitted = {}
    for name, model in _build_models().items():
        print(f"\nTraining {name}...")
        model.fit(X_tr, y_tr)
        fitted[name] = model
        results[name] = {
            "validation": _evaluate(name, model, X_val, y_val),
            "test": _evaluate(name, model, X_test, y_test),
        }
        v = results[name]["test"]
        print(f"  TEST  roc_auc={v['roc_auc']:.4f}  pr_auc={v['pr_auc']:.4f}  "
              f"precision={v['precision']:.4f}  recall={v['recall']:.4f}  f1={v['f1']:.4f}")

    # Select best model by validation PR AUC
    best_name = max(results, key=lambda n: results[n]["validation"]["pr_auc"])
    best_model = fitted[best_name]
    print(f"\nBest model (by validation PR AUC): {best_name}")

    # ---- Tune triage thresholds on validation, using the ML+rules blend ----
    print("Tuning triage thresholds on validation set...")
    val_proba = best_model.predict_proba(X_val)[:, 1]
    val_rule_scores = _rule_scores_for_frame(df_val)
    step_up_thr, decline_thr = _tune_thresholds(val_proba, val_rule_scores, y_val.values)
    print(f"  step_up>={step_up_thr}  decline>={decline_thr}")

    # ---- Triage evaluation on the held-out test set ----
    test_proba = best_model.predict_proba(X_test)[:, 1]
    test_rule_scores = _rule_scores_for_frame(df_test)
    triage_test = _triage_eval(test_proba, test_rule_scores, y_test.values, step_up_thr, decline_thr)
    print("Triage on TEST set:")
    print(f"  action_counts={triage_test['action_counts']}")
    print(f"  fraud_rate_by_action={ {k: round(v,3) for k,v in triage_test['fraud_rate_by_action'].items()} }")
    print(f"  fraud caught (step_up+decline)={triage_test['fraud_caught_step_up_or_decline']:.3f}")

    # ---- Compare against the dataset's own recommended_action (eval only) ----
    action_agreement = None
    if config.COMPARISON_COL in df_test.columns:
        final_scores = np.array([
            rules.combine_scores(p, r) for p, r in zip(test_proba, test_rule_scores)
        ])
        our_actions = np.array([rules.decide_action(f, step_up_thr, decline_thr) for f in final_scores])
        baseline_actions = df_test[config.COMPARISON_COL].values
        action_agreement = float((our_actions == baseline_actions).mean())
        print(f"Agreement with dataset recommended_action: {action_agreement:.3f}")

    # ---- Refit best model on train+val for the final saved artefact ----
    print("Refitting best model on train+val for deployment...")
    X_fit = pd.concat([X_tr, X_val])
    y_fit = pd.concat([y_tr, y_val])
    best_model.fit(X_fit, y_fit)

    thresholds = {
        "step_up": step_up_thr,
        "decline": decline_thr,
        "ml_weight": config.ML_WEIGHT,
    }

    bundle = {
        "model": best_model,
        "model_name": best_name,
        "numeric_features": config.NUMERIC_FEATURES,
        "categorical_features": config.CATEGORICAL_FEATURES,
        "all_features": config.ALL_FEATURES,
        "thresholds": thresholds,
    }
    joblib.dump(bundle, config.MODEL_PATH)
    print(f"Saved model bundle -> {config.MODEL_PATH}")

    # ---- Write metrics + feature list ----
    metrics = {
        "best_model": best_name,
        "n_rows": int(len(df)),
        "fraud_rate": float(df[config.TARGET].mean()),
        "split": {"train": len(X_tr), "val": len(X_val), "test": len(X_test)},
        "model_results": results,
        "triage_thresholds": thresholds,
        "triage_test_evaluation": triage_test,
        "recommended_action_agreement": action_agreement,
    }
    with open(config.METRICS_FILE, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved metrics -> {config.METRICS_FILE}")

    with open(config.FEATURE_LIST_FILE, "w") as f:
        json.dump(feat.get_feature_metadata(), f, indent=2)
    print(f"Saved feature list -> {config.FEATURE_LIST_FILE}")

    # ---- Sample scored transactions (from test set, leakage-free scoring) ----
    _write_sample_scores(df_test, test_proba, test_rule_scores, step_up_thr, decline_thr)

    print("\nDone.")
    return metrics


def _write_sample_scores(df_test, proba, rule_scores, step_up_thr, decline_thr, n=200):
    """Write a sample of scored transactions for inspection."""
    n = min(n, len(df_test))
    sample = df_test.head(n).copy().reset_index(drop=True)
    p = proba[:n]
    rs = rule_scores[:n]

    final = [rules.combine_scores(pi, ri) for pi, ri in zip(p, rs)]
    actions = [rules.decide_action(fi, step_up_thr, decline_thr) for fi in final]
    reasons = [rules.apply_rules(r)[1] for r in sample.to_dict(orient="records")]

    out = pd.DataFrame({
        "transaction_id": sample.get("transaction_id"),
        "cardholder_id": sample.get("cardholder_id"),
        "merchant_id": sample.get("merchant_id"),
        "Txn_Amt": sample.get("Txn_Amt"),
        "fraud_probability": np.round(p, 4),
        "rule_risk_score": rs.astype(int),
        "final_risk_score": final,
        "recommended_action": actions,
        "reason_codes": ["|".join(r) for r in reasons],
        # comparison-only columns (NOT model inputs)
        "actual_is_fraud": sample.get(config.TARGET),
        "dataset_recommended_action": sample.get(config.COMPARISON_COL),
        "fraud_scenario": sample.get("fraud_scenario"),
    })
    out.to_csv(config.SAMPLE_SCORED_FILE, index=False)
    print(f"Saved sample scored transactions -> {config.SAMPLE_SCORED_FILE}")


if __name__ == "__main__":
    main()
