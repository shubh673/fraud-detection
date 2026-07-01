// Shared colour maps for severities, actions and charts.
// Restricted palette: black / dark grey / white / yellow / gold.
// Distinction is carried by intensity: grey (calm) -> gold (caution) ->
// solid bright-yellow (strongest alert).
import type { Severity } from "../types/fraud";

export const SEVERITY_STYLES: Record<Severity, string> = {
  LOW: "bg-neutral-500/10 text-neutral-300 ring-neutral-500/30",
  MEDIUM: "bg-yellow-500/10 text-yellow-300 ring-yellow-500/30",
  HIGH: "bg-amber-500/15 text-amber-200 ring-amber-500/40",
  CRITICAL: "bg-yellow-400 text-black ring-yellow-300",
};

export const SEVERITY_HEX: Record<string, string> = {
  LOW: "#71717a", // grey
  MEDIUM: "#a16207", // dark gold
  HIGH: "#eab308", // gold
  CRITICAL: "#facc15", // bright yellow
};

export const ACTION_STYLES: Record<string, string> = {
  approve: "bg-neutral-500/10 text-neutral-300 ring-neutral-500/30",
  step_up: "bg-amber-500/15 text-amber-200 ring-amber-500/40",
  decline: "bg-yellow-400 text-black ring-yellow-300",
  review: "bg-neutral-400/10 text-neutral-300 ring-neutral-400/30",
};

export const ACTION_HEX: Record<string, string> = {
  approve: "#a1a1aa", // grey
  step_up: "#eab308", // gold
  decline: "#facc15", // bright yellow
  review: "#71717a", // grey
};

// Reason codes contributed by the client add-on overlay (highlighted in UI).
export const OVERLAY_CODES = new Set([
  "BLACKLISTED_MERCHANT",
  "HIGH_RISK_MERCHANT_BLACKLIST_SUGGESTED",
  "BIN_ATTACK_PATTERN",
  "SAME_IP_REPETITIVE_AUTH",
]);

// Chart series colours — yellows, golds and greys only.
export const CHART_PALETTE = [
  "#facc15",
  "#eab308",
  "#ca8a04",
  "#d4af37",
  "#a16207",
  "#fde047",
  "#d4d4d8",
  "#a1a1aa",
  "#71717a",
  "#854d0e",
];
