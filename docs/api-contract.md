# API Contract — Adaptive Anti-Doping Defense Engine

This is the **shared contract** between backend/ML and frontend. Response
shapes here are binding — do not add, rename, or remove fields without
updating this file, `/frontend/src/types/api.ts`, and the fixtures in
`/frontend/mock/` together in the same change.

> ### ⚠️ `ground_truth` IS NEVER EXPOSED
> The `ground_truth(athlete_id, is_synthetic_anomaly, pattern_type)` table
> is an **internal-evaluation-only** table used to score the detection
> pipeline against known synthetic injects. It must **never** appear in
> any response shape, query param, or field in this document, in
> `api.ts`, or in any mock fixture — not even behind a flag, debug mode,
> or admin-only field. If a future change seems to need
> `is_synthetic_anomaly` or `pattern_type` on the wire, stop and raise it
> instead of adding it here.

---

## Conventions

These apply to every endpoint below unless stated otherwise.

- **Base path**: all routes are relative to the API root (e.g. `/athletes` →
  `http://localhost:8000/athletes` in dev).
- **IDs**: all `id` / `*_id` fields are **integers** (auto-increment
  primary keys). *Assumption — the schema didn't specify a type; flagged
  below.*
- **Dates**: `date` fields (day-granularity, e.g. `samples.date`) are
  `"YYYY-MM-DD"` strings. `*_at` / `timestamp` fields (datetime-granularity)
  are ISO 8601 UTC strings with a `Z` suffix, e.g.
  `"2026-07-30T09:15:00Z"`.
- **JSON field casing**: `snake_case`, matching the DB column names
  exactly (the backend is FastAPI/Pydantic; this avoids an
  alias-generator layer for MVP).
- **List responses**: endpoints whose spec description says "list of X"
  return a bare JSON array (`[...]`), not an envelope object. Composite
  responses (profile + samples, trajectory, timeline) return a single
  JSON object.
- **No pagination in MVP.** All list endpoints return the full result
  set. *Assumption — flagged below; revisit if athlete/sample counts
  grow large.*
- **Errors**: standard FastAPI shapes.
  - `404` — `{"detail": "<human-readable message>"}`
  - `422` — FastAPI/Pydantic validation error shape:
    ```json
    {
      "detail": [
        { "type": "missing", "loc": ["body", "hb"], "msg": "Field required", "input": {} }
      ]
    }
    ```
  - `404` is used only for a missing path-parameter resource (unknown
    `athlete_id`, `case_id`). `422` is used for malformed/invalid
    request bodies or query params.
- **Biomarker keys**: wherever a biomarker is named generically, the key
  is one of `"hb" | "hct" | "ret_pct" | "off_score" | "te_ratio"`.
- **OFF-score formula**: `off_score = (hb_g_dL * 10) - 60 * sqrt(ret_pct)`,
  computed server-side. The raw `hb` field is stored and displayed in
  g/dL everywhere (matches spec §8's raw biomarker unit) — but the
  OFF-score formula itself requires Hb in g/L, so the stored g/dL value
  is converted (×10) before applying the formula. *Corrected
  assumption, not a literal reading of spec §8 — see item 9 below.*
  Example: `hb=15.0, ret_pct=1.0` → `off_score = 150 - 60*sqrt(1.0) =
  90.0`, within the realistic clinical OFF-score range (~80–105) rather
  than the large negative values a literal g/dL reading of spec §8
  would produce (e.g. `hb=15.0, ret_pct=1.0` → `15.0 - 60 = -45.0`).

---

## Day 3 MVP — live-priority endpoints

These four are the only endpoints that should be assumed to exist
against a real backend during Day 3. Everything else below is
documented for contract-lock purposes but is **not yet implemented** —
see the "Day 4/5" section.

### `GET /athletes`

List athletes with their latest anomaly/uncertainty score, for the
triage dashboard.

**Query params**

| Param | Type | Required | Notes |
|---|---|---|---|
| `sport` | string | no | Exact match filter, e.g. `?sport=Cycling`. Omit for all sports. |
| `sort` | string enum | no | Only `"priority"` is supported today (also the default if omitted). Any other value → `422`. |

**Response `200`** — `AthleteListItem[]`, sorted descending by
`priority_score` (highest-priority athlete first).

```ts
interface AthleteListItem {
  id: number;
  name: string;
  sport: string;
  age: number;
  latest_anomaly_score: number | null;   // most recent anomalies.anomaly_score for this athlete, null if none yet
  latest_uncertainty_score: number | null; // most recent recommendations.uncertainty_score, null if none yet
  priority_score: number;                // see "priority_score definition" below
  last_sample_date: string | null;       // "YYYY-MM-DD", null if no samples yet
  scored: boolean;                       // true if latest_anomaly_score is non-null; false means never scored — NOT "confirmed low-risk"
}
```

**`priority_score` definition** *(assumption — flagged below)*: equal to
`latest_anomaly_score` (0 if no anomalies recorded yet). This is the
single ranking key for `sort=priority`; ties are broken by
`latest_uncertainty_score` descending. **Note**: this collapses "never
scored" and "scored, found low-risk" into the same `0` value for ranking
purposes — that ambiguity is intentional for sorting (an unscored athlete
shouldn't outrank a confirmed low-risk one, or vice versa) but must not be
read as "this athlete is low-risk." Use `scored` to distinguish the two
cases; `priority_score` alone cannot.

**Example response**

```json
[
  {
    "id": 1,
    "name": "Elena Marchetti",
    "sport": "Cycling",
    "age": 27,
    "latest_anomaly_score": 0.82,
    "latest_uncertainty_score": 0.35,
    "priority_score": 0.82,
    "last_sample_date": "2026-07-30",
    "scored": true
  }
]
```

**Errors**: `422` if `sort` is not `"priority"`.

---

### `GET /athletes/{id}`

Full profile plus complete sample history for one athlete.

**Path params**: `id` (integer, athlete id)

**Response `200`** — `AthleteDetail`

```ts
interface BaselinePrior {
  hb: { mean: number; std: number };
  hct: { mean: number; std: number };
  ret_pct: { mean: number; std: number };
  off_score: { mean: number; std: number };
  te_ratio: { mean: number; std: number };
}

interface Sample {
  id: number;
  athlete_id: number;
  date: string;            // "YYYY-MM-DD"
  hb: number;               // g/dL
  hct: number;               // %
  ret_pct: number;           // %
  off_score: number;         // derived, see OFF-score formula above
  te_ratio: number;
  competition_flag: boolean;
  altitude_flag: boolean;
  injury_flag: boolean;
}

interface AthleteDetail {
  id: number;
  name: string;
  sport: string;
  age: number;
  baseline_prior: BaselinePrior;  // parsed baseline_prior_json
  samples: Sample[];              // full history, ascending by date
}
```

**Example response**: see `/frontend/mock/athlete-detail.json`.

**Errors**: `404` — `{"detail": "Athlete 999 not found"}`.

---

### `GET /athletes/{id}/trajectory`

Expected (baseline) vs. observed biomarker series with confidence
bands, for the trend chart on the athlete detail page.

**Path params**: `id` (integer, athlete id)

**Response `200`** — `TrajectoryResponse`

```ts
interface TrajectoryPoint {
  date: string;             // "YYYY-MM-DD", one per sample date
  observed: number;         // the actual sample value on that date
  expected: number;         // baseline model's expected value
  ci_lower: number;         // lower confidence bound
  ci_upper: number;         // upper confidence bound
}

interface BiomarkerTrajectory {
  biomarker: "hb" | "hct" | "ret_pct" | "off_score" | "te_ratio";
  unit: string;              // "g/dL" | "%" | "score" | "ratio"
  points: TrajectoryPoint[];
}

interface TrajectoryResponse {
  athlete_id: number;
  ci_level: number;          // confidence level the bands represent, e.g. 0.95
  series: BiomarkerTrajectory[]; // one entry per biomarker, fixed order: hb, hct, ret_pct, off_score, te_ratio
}
```

*Assumption — flagged below*: MVP baseline model is treated as static
per biomarker (flat `expected`/`ci_lower`/`ci_upper` across all dates,
equal to `baseline_prior[biomarker].mean` ± `1.96 * std` for a 95% CI).
A time-varying/adaptive baseline can replace this later without
changing the response shape.

**Example response**: see `/frontend/mock/trajectory.json`.

**Errors**: `404` — unknown athlete id.

---

### `GET /athletes/{id}/anomalies`

Anomaly score history for the athlete, each with the biomarkers that
drove it.

**Path params**: `id` (integer, athlete id)

**Response `200`** — `AnomalyDetail[]`, descending by `created_at`
(most recent first).

```ts
interface ContributingBiomarker {
  biomarker: "hb" | "hct" | "ret_pct" | "off_score" | "te_ratio";
  observed_value: number;
  posterior_mean: number;     // athlete's own Bayesian posterior mean for this biomarker, not a population/cohort value
  z_score_squared: number;    // (observed_value - posterior_mean)^2 / posterior_var
  deviation_direction: "above" | "below"; // observed_value relative to posterior_mean
}

interface AnomalyDetail {
  id: number;
  athlete_id: number;
  sample_id: number;
  anomaly_score: number;          // normalized 0–1
  mahalanobis_distance: number;   // >= 0, unbounded
  method: string;                 // e.g. "mahalanobis_baseline"; detection method used, ML-defined, not a fixed enum in this contract
  created_at: string;
  contributing_biomarkers: ContributingBiomarker[]; // ordered by z_score_squared descending
}
```

**Example response**: see `/frontend/mock/anomalies.json`.

**Errors**: `404` — unknown athlete id. Returns `[]` (not `404`) if the
athlete exists but has no anomalies yet.

---

## Day 4/5 — not yet implemented

Everything below is contract-locked so both sides can build against it,
but **there is no live backend route for these yet.** Do not wire real
`fetch`/`axios` calls to these paths until they're confirmed live —
use the corresponding mock fixture (where one exists) instead.

### `GET /athletes/{id}/recommendation`

Latest recommended action for one athlete.

**Path params**: `id` (integer, athlete id)

**Response `200`** — `Recommendation`

```ts
type RecommendationActionType =
  | "no_action"
  | "increase_monitoring"
  | "target_test"
  | "biological_passport_review"
  | "open_case";
// Assumption — flagged below: this enum isn't in the spec, only the
// column `action_type` (free text). Treat as the working set for MVP.

interface Recommendation {
  id: number;
  athlete_id: number;
  action_type: RecommendationActionType;
  value_score: number;         // expected information/investigative value of acting, 0–1
  uncertainty_score: number;   // model's uncertainty about the anomaly, 0–1
  anomaly_score: number;       // anomaly score this recommendation was generated from
  cost: number;                // abstract testing/investigation cost unit, not currency
  explanation_text: string;    // human-readable rationale
  created_at: string;
}
```

**Example response**: see `/frontend/mock/recommendation.json`.

**Errors**: `404` — unknown athlete id, or athlete exists but has no
recommendation yet (same 404 message either way is acceptable —
frontend should not need to distinguish).

---

### `GET /recommendations/budget`

Ranked, budget-constrained recommendation list across all athletes —
"if we can only afford N cost units of testing, who do we test?"

**Query params**

| Param | Type | Required | Notes |
|---|---|---|---|
| `budget` | number | yes | Total cost budget available. `422` if missing or negative. |

**Response `200`** — `BudgetRecommendationsResponse`

```ts
interface BudgetRecommendationItem extends Recommendation {
  athlete_name: string;
  sport: string;
  rank: number;   // 1-indexed, order of selection by value/cost
}

interface BudgetRecommendationsResponse {
  budget: number;
  total_cost_used: number;      // sum of cost across `selected`, <= budget
  selected: BudgetRecommendationItem[]; // knapsack-style selection maximizing total value_score within budget
}
```

*Assumption — flagged below*: selection algorithm (e.g. greedy
value/cost ratio vs. exact knapsack) is left to the ML side; the
contract only fixes the response shape.

**Errors**: `422` — missing/invalid `budget`.

*No mock fixture provided — not requested for this pass.*

---

### `POST /athletes/{id}/samples`

Ingest a new sample for an athlete; triggers baseline update and a new
anomaly score.

**Path params**: `id` (integer, athlete id)

**Request body** — `NewSampleInput`

```ts
interface NewSampleInput {
  date: string;               // "YYYY-MM-DD"
  hb: number;
  hct: number;
  ret_pct: number;
  te_ratio: number;
  competition_flag: boolean;
  altitude_flag: boolean;
  injury_flag: boolean;
  // off_score is NOT sent by the client — it is always server-derived.
}
```

**Response `201`** — `NewSampleResponse`

```ts
interface NewSampleResponse {
  sample: Sample;                  // as stored, including computed off_score
  updated_baseline: BaselinePrior; // athlete's baseline_prior after incorporating this sample
  anomaly: Anomaly;                // newly computed anomaly record for this sample
}

interface Anomaly {
  id: number;
  athlete_id: number;
  sample_id: number;
  anomaly_score: number;
  mahalanobis_distance: number;
  method: string;
  created_at: string;
}
```

**Errors**: `404` — unknown athlete id. `422` — missing/invalid field
(e.g. `hb` missing, negative `ret_pct`), or `off_score` present in the
body (reject rather than silently ignore, so clients don't assume it's
honored).

*No mock fixture provided — not requested for this pass.*

---

### `POST /cases`

Open a new investigation case for an athlete.

**Request body**

```ts
interface NewCaseInput {
  athlete_id: number;
  notes?: string;   // optional initial investigator_notes
}
```

**Response `201`** — `Case`

```ts
interface Case {
  id: number;
  athlete_id: number;
  status: "open" | "closed";
  opened_at: string;
  closed_at: string | null;
  investigator_notes: string | null;
}
```

New cases are always created with `status: "open"`, `opened_at: now`,
`closed_at: null`.

**Errors**: `404` — unknown `athlete_id`. `422` — missing `athlete_id`.

*No mock fixture provided — not requested for this pass.*

---

### `POST /cases/{id}/decision`

Log an investigator decision against a case. There is no dedicated
"decisions" table in the schema (§8), so a decision is recorded as an
`audit_logs` row and may update the case's `status`/`closed_at`.
*Assumption — flagged below.*

**Path params**: `id` (integer, case id)

**Request body**

```ts
type DecisionAction =
  | "escalate"
  | "clear"
  | "request_more_testing"
  | "close_case";
// Assumption — flagged below: enum not in spec.

interface DecisionInput {
  action: DecisionAction;
  investigator: string;   // becomes audit_logs.actor
}
```

**Response `201`** — `DecisionResponse`

```ts
interface AuditLog {
  id: number;
  case_id: number | null;
  athlete_id: number;
  actor: string;
  action: string;
  timestamp: string;
  details: Record<string, unknown>;  // parsed details_json
}

interface DecisionResponse {
  case: Case;          // updated; status becomes "closed" (with closed_at set) only if action === "close_case", otherwise unchanged
  audit_log: AuditLog;
}
```

**Errors**: `404` — unknown case id. `422` — invalid `action` or
missing `investigator`.

*No mock fixture provided — not requested for this pass.*

---

### `GET /audit/{athlete_id}`

Full chronological timeline of everything recorded for an athlete:
samples, anomalies, recommendations, case lifecycle, and decisions.

**Path params**: `athlete_id` (integer)

**Response `200`** — `AuditTimelineResponse`

```ts
type AuditEvent =
  | { type: "sample";         timestamp: string; data: Sample }
  | { type: "anomaly";        timestamp: string; data: Anomaly }
  | { type: "recommendation"; timestamp: string; data: Recommendation }
  | { type: "case_opened";    timestamp: string; data: Case }
  | { type: "case_closed";    timestamp: string; data: Case }
  | { type: "decision";       timestamp: string; data: AuditLog };

interface AuditTimelineResponse {
  athlete_id: number;
  events: AuditEvent[];   // ascending by timestamp, oldest first
}
```

For `type: "sample"` events, `timestamp` is the sample's `date` at
midnight UTC (`"<date>T00:00:00Z"`), since `samples.date` has no time
component. All other event types use their own native `*_at`/
`timestamp` column value.

**Example response**: see `/frontend/mock/audit.json`.

**Errors**: `404` — unknown `athlete_id`. If the athlete exists but has
no events yet, returns `200` with `events: []`.

---

### `GET /simulation/evasion`

Runs the evasion-detection comparison against a **real seeded athlete's**
sample series: single-sample Mahalanobis threshold detection (reusing
`anomaly.py`'s existing scoring, unmodified) against CUSUM cumulative
detection (`app/ml/cusum.py`, actual defaults `k=0.5, h=5.0` — not tuned
per-request), on whichever single biomarker the requested `pattern`
targets.

> Note: `pattern` selects a **detection archetype** (which single
> biomarker's drift to run CUSUM against), not a value read from the
> hidden `ground_truth.pattern_type` column. This endpoint queries real
> `Athlete`/`Sample` rows for `athlete_id` but never touches
> `ground_truth` — see the warning banner at the top of this document.

**Query params**

| Param | Type | Required | Notes |
|---|---|---|---|
| `athlete_id` | integer | yes | `404` if unknown. |
| `pattern` | string enum | no | `"micro_dosing"` (default) → biomarker `hb` (EPO). `"steroid_micro_dosing"` → biomarker `te_ratio`. `422` for anything else. |

**Response `200`** — `EvasionSimulationResponse`

```ts
interface CusumResult {
  cusum_upper: number[];       // C+_i per sample, same length/order as single_sample_scores
  cusum_lower: number[];       // C-_i per sample
  flagged: boolean;            // true if either sum ever exceeded threshold
  flagged_at_index: number | null; // index of first crossing, else null
  threshold: number;           // echoes h
}

interface EvasionSimulationResponse {
  athlete_id: number;
  biomarker: "hb" | "te_ratio";        // which biomarker `pattern` selected
  pattern: "micro_dosing" | "steroid_micro_dosing";
  sample_count: number;
  single_sample_scores: number[];      // normalized 0-1 anomaly_score per sample, ascending by date
  single_sample_flagged_any: boolean;  // true if any single_sample_scores entry >= 0.55 (the same "moderate" cutoff ExplanationPanel.tsx already uses)
  cusum_result: CusumResult;
  cusum_flagged: boolean;              // echoes cusum_result.flagged
}
```

**Errors**:
- `404` — unknown `athlete_id`.
- `422` — unsupported `pattern`, or the athlete has no valid
  `baseline_prior_json` (posterior can't be computed).

*No mock fixture provided — not requested for this pass.*

**Known limitation, not a bug**: with the current seeded dataset (5
samples per athlete, uniformly — see the Day 5 evaluation note), CUSUM's
default `h=5.0` does not flag either seeded micro-dosing athlete yet; the
cumulative sum gets close (peaks around 4.3 on `hb` for the EPO case) but
5 samples isn't enough series length to cross threshold at the untuned
default. This is a dataset-length finding, not a reason to lower `h` for
this endpoint specifically.

---

## Schema tables with no corresponding endpoint (yet)

- `evidence(id, case_id, sample_id, note, added_at)` — no endpoint in
  §9 reads or writes this table. Not in this contract.
- `cohort_stats(sport, biomarker, population_mean, population_std)` —
  not exposed directly; used server-side to compute
  `contributing_biomarkers` in `GET /athletes/{id}/anomalies`.
- `ground_truth` — see the warning banner at the top of this document.
  Never exposed.

---

## Assumptions requiring sign-off

None of these are in spec §8/§9 explicitly. Flagging per your request —
please confirm or correct before we lock the contract:

1. **ID type**: integers for all primary keys. (Could be UUIDs/strings instead.)
2. **`priority_score` definition**: equals `latest_anomaly_score`, ties
   broken by `latest_uncertainty_score`. The spec only says "sort by
   priority" without defining the metric.
3. **`baseline_prior_json` shape**: `{ [biomarker]: { mean, std } }` per
   athlete. Spec only says the column is JSON.
4. **Trajectory CI/baseline model**: static per-biomarker
   mean/±1.96·std band (95% CI) rather than a time-varying curve, for
   MVP.
5. **No pagination** anywhere yet.
6. **`RecommendationActionType` and `DecisionAction` enums**: both
   invented for this pass (schema only has free-text columns).
7. **Decision → case mapping**: `POST /cases/{id}/decision` writes an
   `audit_logs` row and only flips `case.status` to `"closed"` when
   `action === "close_case"`. There's no separate decisions table in
   the schema, so this mapping is inferred.
8. **`cost` units**: abstract resource-cost unit, not real currency.
9. **OFF-score formula corrected** to convert Hb from g/dL to g/L
   before applying the formula (`off_score = hb_g_dL*10 -
   60*sqrt(ret_pct)`), giving the standard clinical OFF-score range
   (~80–105) instead of the large negative values a literal g/dL
   reading of spec §8 produces. This diverges from a literal reading of
   spec §8's raw formula but was confirmed as the intended convention;
   `docs/schema.md` is the authoritative statement of it.
10. **404 vs empty-list**: `404` is reserved for "athlete/case id
    doesn't exist"; an existing athlete with zero anomalies/events
    returns `200` with an empty array, not `404`.
