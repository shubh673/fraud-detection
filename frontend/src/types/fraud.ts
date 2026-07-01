// Shared types for the fraud-detection dashboard.
// These mirror the JSON files produced by scripts/prepare_dashboard_data.py.

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type TriageAction = "approve" | "step_up" | "decline";

export interface ScoredTransaction {
  transaction_id: string;
  cardholder_id: string;
  merchant_id: string;
  Txn_Amt: number;
  fraud_probability: number;
  rule_risk_score: number;
  final_risk_score: number;
  recommended_action: TriageAction;
  reason_codes: string | null;
  actual_is_fraud: number;
  dataset_recommended_action: string;
  fraud_scenario: string;
}

export interface BinAttackAlert {
  alert_id: string;
  SubBIN: number;
  alert_start_time: string;
  alert_end_time: string;
  transaction_count: number;
  unique_cards: number;
  unique_merchants: number;
  unique_ips: number;
  unique_devices: number;
  avg_amount: number;
  decline_rate: number;
  max_ip_txn_count_1h: number;
  risk_score: number;
  severity: Severity;
  recommended_control: string;
  reason_codes: string;
}

export interface IpRepetitionAlert {
  alert_id: string;
  ip_address_hash: string;
  alert_start_time: string;
  alert_end_time: string;
  transaction_count: number;
  unique_cardholders: number;
  unique_merchants: number;
  unique_subbins: number;
  unique_devices: number;
  total_amount: number;
  max_transactions_per_10_seconds: number;
  max_ip_txn_count_1h: number;
  risk_score: number;
  severity: Severity;
  recommended_control: string;
  reason_codes: string;
}

export interface MerchantSuggestion {
  merchant_id: string;
  Merch_ID_DE42: string;
  merchant_name: string;
  merchant_risk_segment: string;
  laundering_risk_score: number;
  fraud_rate: number;
  chargeback_rate_30d: number;
  volume_spike_rate: number;
  blacklist_recommendation: string;
  recommended_action: string;
  reason_codes: string;
}

export interface ManualBlacklistEntry {
  merchant_id: string;
  Merch_ID_DE42: string;
  blacklist_reason: string;
  effective_date: string;
  action: string;
}

export interface QueueAlert {
  alert_type: "BIN_ATTACK" | "IP_REPETITIVE" | "MERCHANT_BLACKLIST";
  entity_id: string;
  severity: Severity;
  risk_score: number;
  recommended_action: string;
  reason_codes: string;
  detail: Record<string, number>;
  status: string;
}

export interface ScoreResult {
  fraud_probability: number;
  rule_risk_score: number;
  final_risk_score: number;
  recommended_action: TriageAction;
  reason_codes: string[];
}

export interface OverlayScenario {
  id: string;
  label: string;
  transaction: {
    transaction_id: string;
    merchant_id: string;
    SubBIN: string;
    ip_address_hash: string;
    Txn_Amt: number;
    Txn_Ctry: string;
    is_online: number;
    fraud_scenario: string;
    actual_is_fraud: number;
  };
  base: ScoreResult;
  final: ScoreResult;
  overlay_reason_codes: string[];
}

export interface DashboardSummary {
  transactions_scanned: number;
  fraud_rate: number;
  best_model: string;
  triage_thresholds: { step_up: number; decline: number; ml_weight: number };
  test_set_size: number;
  action_counts: Record<string, number>;
  fraud_rate_by_action: Record<string, number>;
  fraud_caught_step_up_or_decline: number | null;
  recommended_action_agreement: number | null;
  kpis: {
    transactions_scanned: number;
    fraud_rate: number;
    approve: number;
    step_up: number;
    decline: number;
    bin_attack_alerts: number;
    ip_repetitive_alerts: number;
    manual_blacklist: number;
    dynamic_suggestions: number;
    critical_alerts: number;
    high_alerts: number;
  };
  charts: {
    action_distribution: Record<string, number>;
    fraud_scenario_distribution: Record<string, number>;
    risk_score_distribution: { band: string; count: number }[];
    severity_distribution: Record<string, number>;
    top_reason_codes: { code: string; count: number }[];
  };
}

export interface ModelMetrics {
  best_model: string;
  n_rows: number;
  fraud_rate: number;
  split: { train: number; val: number; test: number };
  model_results: Record<
    string,
    {
      validation: ModelEval;
      test: ModelEval;
    }
  >;
  triage_thresholds: { step_up: number; decline: number; ml_weight: number };
  triage_test_evaluation: {
    action_counts: Record<string, number>;
    fraud_rate_by_action: Record<string, number>;
    fraud_caught_step_up_or_decline: number;
  };
  recommended_action_agreement: number;
}

export interface ModelEval {
  model: string;
  roc_auc: number;
  pr_auc: number;
  precision: number;
  recall: number;
  f1: number;
  confusion_matrix: number[][];
}
