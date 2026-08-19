// Mirrors /docs/api-contract.md exactly. Keep both in sync.
//
// NOTE: `ground_truth` (is_synthetic_anomaly, pattern_type) is a hidden
// internal-evaluation-only table and must NEVER be typed or referenced
// here. See the warning banner at the top of the contract doc.

export type Biomarker = "hb" | "hct" | "ret_pct" | "off_score" | "te_ratio";

// ---------------------------------------------------------------------------
// Shared / composite types
// ---------------------------------------------------------------------------

export interface BaselinePrior {
  hb: { mean: number; std: number };
  hct: { mean: number; std: number };
  ret_pct: { mean: number; std: number };
  off_score: { mean: number; std: number };
  te_ratio: { mean: number; std: number };
}

export interface Sample {
  id: number;
  athlete_id: number;
  date: string; // "YYYY-MM-DD"
  hb: number; // g/dL
  hct: number; // %
  ret_pct: number; // %
  off_score: number; // derived: hb - 60 * sqrt(ret_pct)
  te_ratio: number;
  competition_flag: boolean;
  altitude_flag: boolean;
  injury_flag: boolean;
}

export interface Anomaly {
  id: number;
  athlete_id: number;
  sample_id: number;
  anomaly_score: number; // normalized 0-1
  mahalanobis_distance: number; // >= 0, unbounded
  method: string;
  created_at: string; // ISO 8601 UTC
}

export interface ContributingBiomarker {
  biomarker: Biomarker;
  observed_value: number;
  posterior_mean: number; // athlete's own Bayesian posterior mean, not a population/cohort value
  z_score_squared: number; // (observed_value - posterior_mean)^2 / posterior_var
  deviation_direction: "above" | "below"; // observed_value relative to posterior_mean
}

export interface AnomalyDetail extends Anomaly {
  contributing_biomarkers: ContributingBiomarker[]; // ordered by z_score_squared descending
}

export type RecommendationActionType =
  | "no_action"
  | "increase_monitoring"
  | "target_test"
  | "biological_passport_review"
  | "open_case";

export interface Recommendation {
  id: number;
  athlete_id: number;
  action_type: RecommendationActionType;
  value_score: number; // 0-1
  uncertainty_score: number; // 0-1
  anomaly_score: number;
  cost: number; // abstract cost unit, not currency
  explanation_text: string;
  created_at: string;
}

export type CaseStatus = "open" | "closed";

export interface Case {
  id: number;
  athlete_id: number;
  status: CaseStatus;
  opened_at: string;
  closed_at: string | null;
  investigator_notes: string | null;
}

export interface AuditLog {
  id: number;
  case_id: number | null;
  athlete_id: number;
  actor: string;
  action: string;
  timestamp: string;
  details: Record<string, unknown>; // parsed details_json
}

// ---------------------------------------------------------------------------
// Day 3 MVP — live-priority endpoints
// ---------------------------------------------------------------------------

/** GET /athletes */
export interface AthleteListItem {
  id: number;
  name: string;
  sport: string;
  age: number;
  latest_anomaly_score: number | null;
  latest_uncertainty_score: number | null;
  priority_score: number; // collapses "never scored" and "scored, low-risk" to 0 — use `scored` to distinguish
  last_sample_date: string | null;
  scored: boolean; // true if latest_anomaly_score is non-null; false means never scored, NOT "confirmed low-risk"
}

export type AthletesResponse = AthleteListItem[];

/** GET /athletes/{id} */
export interface AthleteDetail {
  id: number;
  name: string;
  sport: string;
  age: number;
  baseline_prior: BaselinePrior;
  samples: Sample[]; // ascending by date
}

/** GET /athletes/{id}/trajectory */
export interface TrajectoryPoint {
  date: string;
  observed: number;
  expected: number;
  ci_lower: number;
  ci_upper: number;
}

export interface BiomarkerTrajectory {
  biomarker: Biomarker;
  unit: string; // "g/dL" | "%" | "score" | "ratio"
  points: TrajectoryPoint[];
}

export interface TrajectoryResponse {
  athlete_id: number;
  ci_level: number; // e.g. 0.95
  series: BiomarkerTrajectory[]; // fixed order: hb, hct, ret_pct, off_score, te_ratio
}

/** GET /athletes/{id}/anomalies */
export type AnomaliesResponse = AnomalyDetail[];

// ---------------------------------------------------------------------------
// Day 4/5 — not yet implemented (types locked for contract purposes;
// mocks provided only where requested — see /frontend/mock/)
// ---------------------------------------------------------------------------

/** GET /athletes/{id}/recommendation */
export type RecommendationResponse = Recommendation;

/** GET /recommendations/budget?budget=N */
export interface BudgetSelectedItem {
  athlete_id: number;
  name: string;
  action_type: RecommendationActionType;
  value_score: number;
  cost: number;
  cumulative_cost_after: number; // running total of selected cost, in selection order
  explanation_text: string;
}

export interface BudgetAllocationResponse {
  budget: number;
  selected: BudgetSelectedItem[]; // knapsack-style selection by value_score/cost ratio, descending
  total_cost: number; // sum of cost across `selected`, <= budget
  total_value: number; // sum of value_score across `selected`
  athletes_evaluated: number; // every athlete compute_recommendation could score at all, INCLUDING no_action
  candidates_considered: number; // subset of athletes_evaluated eligible for the budget pool (excludes no_action)
  candidates_selected: number; // subset of candidates_considered the budget could afford; == selected.length
}

/** POST /athletes/{id}/samples */
export interface NewSampleInput {
  date: string;
  hb: number;
  hct: number;
  ret_pct: number;
  te_ratio: number;
  competition_flag: boolean;
  altitude_flag: boolean;
  injury_flag: boolean;
  // off_score is NOT sent by the client - always server-derived.
}

export interface NewSampleResponse {
  sample: Sample;
  updated_baseline: BaselinePrior;
  anomaly: Anomaly;
}

/** POST /cases */
export interface NewCaseInput {
  athlete_id: number;
  notes?: string;
}

/** POST /cases/{id}/decision */
export type DecisionAction =
  | "escalate"
  | "clear"
  | "request_more_testing"
  | "close_case";

export interface DecisionInput {
  action: DecisionAction;
  investigator: string;
}

export interface DecisionResponse {
  case: Case;
  audit_log: AuditLog;
}

/** GET /audit/{athlete_id} */
export type AuditEvent =
  | { type: "sample"; timestamp: string; data: Sample }
  | { type: "anomaly"; timestamp: string; data: Anomaly }
  | { type: "recommendation"; timestamp: string; data: Recommendation }
  | { type: "case_opened"; timestamp: string; data: Case }
  | { type: "case_closed"; timestamp: string; data: Case }
  | { type: "decision"; timestamp: string; data: AuditLog };

export interface AuditTimelineResponse {
  athlete_id: number;
  events: AuditEvent[]; // ascending by timestamp
}

/** GET /simulation/evasion?athlete_id={id}&pattern=micro_dosing */
export type EvasionPattern = "micro_dosing" | "steroid_micro_dosing";

export interface CusumResult {
  cusum_upper: number[]; // C+_i per sample, same length/order as single_sample_scores
  cusum_lower: number[]; // C-_i per sample
  flagged: boolean;
  flagged_at_index: number | null;
  threshold: number; // echoes h
}

export interface EvasionSimulationResponse {
  athlete_id: number;
  biomarker: "hb" | "te_ratio"; // which biomarker `pattern` selected
  pattern: EvasionPattern;
  sample_count: number;
  single_sample_scores: number[]; // normalized 0-1 anomaly_score per sample, ascending by date
  single_sample_flagged_any: boolean; // true if any entry >= 0.55, the same "moderate" cutoff ExplanationPanel.tsx uses
  cusum_result: CusumResult;
  cusum_flagged: boolean; // echoes cusum_result.flagged
  baseline_window_used: number; // earliest N samples held out to establish the CUSUM baseline mean/std
  detection_sample_count: number; // sample_count - baseline_window_used; length of cusum_result's arrays
}

// ---------------------------------------------------------------------------
// Error shapes
// ---------------------------------------------------------------------------

export interface NotFoundError {
  detail: string;
}

export interface ValidationErrorItem {
  type: string;
  loc: (string | number)[];
  msg: string;
  input: unknown;
}

export interface ValidationError {
  detail: ValidationErrorItem[];
}
