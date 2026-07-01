// Display formatting helpers.

export const fmtInt = (n: number | null | undefined): string =>
  n == null ? "—" : Math.round(n).toLocaleString("en-US");

export const fmtMoney = (n: number | null | undefined): string =>
  n == null ? "—" : "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmtPct = (n: number | null | undefined, digits = 1): string =>
  n == null ? "—" : (n * 100).toFixed(digits) + "%";

export const fmtNum = (n: number | null | undefined, digits = 3): string =>
  n == null ? "—" : n.toFixed(digits);

export const splitReasonCodes = (codes: string | null | undefined): string[] =>
  !codes ? [] : String(codes).split("|").map((c) => c.trim()).filter(Boolean);

export const titleCase = (s: string): string =>
  s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const shortHash = (s: string, head = 10): string =>
  s.length > head + 4 ? `${s.slice(0, head)}…${s.slice(-4)}` : s;

// Map a final risk score (0-1000) to a triage band label.
export function riskBand(score: number, stepUp = 190, decline = 430): {
  label: string;
  action: "approve" | "step_up" | "decline";
} {
  if (score >= decline) return { label: "Decline", action: "decline" };
  if (score >= stepUp) return { label: "Step-up", action: "step_up" };
  return { label: "Approve", action: "approve" };
}
