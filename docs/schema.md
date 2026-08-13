# Database Schema — Adaptive Anti-Doping Defense Engine

This is the **shared contract** for the full database schema — every
table the project is scoped to have, including ones not built yet.
Like `docs/api-contract.md`, changes here must be flagged in chat/commit
message before editing (see `CLAUDE.md`).

> ### ⚠️ `ground_truth` IS NEVER EXPOSED
> The `ground_truth` table (bottom of this doc) is
> **internal-evaluation-only**. It must never be returned by any API
> endpoint, shown on the dashboard, or included in any query result
> handed to the frontend — regardless of how the rest of this schema
> evolves. See the same warning in `docs/api-contract.md`.

> ### ⚠️ Known doc drift — `off_score` formula
> The correct convention (agreed, but not yet propagated everywhere) is:
> **`off_score = (hb_g_dL * 10) - 60 * sqrt(ret_pct)`** — `hb` is stored
> in the `hb` column in g/dL (spec §8's raw unit), but must be
> **converted to g/L (×10) before applying the OFF-score formula**.
> Applying the formula directly to the raw g/dL value (as
> `docs/api-contract.md`'s Conventions section and `frontend/mock/*.json`
> currently still do) produces unrealistic negative scores instead of
> the clinical ~80–105 range. **`docs/api-contract.md` and the mock
> fixtures have not been updated to match yet** — treat this doc as
> authoritative on the formula until that follow-up pass happens, don't
> silently re-derive the uncorrected version.

---

## Roadmap overview

| Table | Status | Stage |
|---|---|---|
| `athletes` | ✅ Implemented | Day 3 MVP |
| `samples` | ✅ Implemented | Day 3 MVP |
| `anomalies` | Planned | Day 3 MVP |
| `recommendations` | Planned | Day 3 MVP |
| `cases` | Planned | Day 6 |
| `audit_logs` | Planned | Day 6 |
| `evidence` | Planned | Day 6 |
| `cohort_stats` | Planned | Optional |
| `ground_truth` | Planned, **hidden** | Optional |

---

## `athletes` — implemented (Day 3 MVP)

Source of truth: `backend/app/db/models.py::Athlete`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `Integer` | No | **PK**, autoincrement |
| `name` | `String` | No | |
| `sport` | `String` | No | Plain string column, not an enum |
| `age` | `Integer` | Yes | |
| `baseline_prior_json` | `Text` | Yes | JSON string, shape `{biomarker: {mean, std}}`; population prior used to seed the Bayesian model before any samples exist |

---

## `samples` — implemented (Day 3 MVP)

Source of truth: `backend/app/db/models.py::Sample`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `Integer` | No | **PK**, autoincrement |
| `athlete_id` | `Integer` | No | **FK → `athletes.id`** |
| `date` | `Date` | No | Day-granularity, no time component |
| `hb` | `Float` | No | g/dL |
| `hct` | `Float` | No | % |
| `ret_pct` | `Float` | No | % |
| `off_score` | `Float` | No | **Derived, server-computed — see the drift warning above for the formula.** Never client-supplied. |
| `te_ratio` | `Float` | No | |
| `competition_flag` | `Boolean` | No | Default `False` |
| `altitude_flag` | `Boolean` | No | Default `False` |
| `injury_flag` | `Boolean` | No | Default `False` |

---

## `anomalies` — planned (Day 3 MVP)

Not yet implemented. Types below follow the same conventions as the
two tables above (integer PK/FK, `DateTime` for timestamp-granularity
columns) — confirm before implementing.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `Integer` | No | **PK**, autoincrement |
| `athlete_id` | `Integer` | No | **FK → `athletes.id`** |
| `sample_id` | `Integer` | No | **FK → `samples.id`** |
| `anomaly_score` | `Float` | No | Normalized 0–1 |
| `mahalanobis_distance` | `Float` | No | ≥ 0, unbounded |
| `method` | `String` | No | Detection method identifier, e.g. `"mahalanobis_baseline"`; free text, not a fixed enum |
| `created_at` | `DateTime` | No | |

---

## `recommendations` — planned (Day 3 MVP)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `Integer` | No | **PK**, autoincrement |
| `athlete_id` | `Integer` | No | **FK → `athletes.id`** |
| `action_type` | `String` | No | See `docs/api-contract.md` for the working enum (`no_action`, `increase_monitoring`, `target_test`, `biological_passport_review`, `open_case`) |
| `value_score` | `Float` | No | 0–1 |
| `uncertainty_score` | `Float` | No | 0–1 |
| `anomaly_score` | `Float` | No | Copied from the triggering `anomalies` row at creation time |
| `cost` | `Float` | No | Abstract resource-cost unit, not currency |
| `explanation_text` | `Text` | No | |
| `created_at` | `DateTime` | No | |

---

## `cases` — planned (Day 6)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `Integer` | No | **PK**, autoincrement |
| `athlete_id` | `Integer` | No | **FK → `athletes.id`** |
| `status` | `String` | No | `"open"` \| `"closed"` |
| `opened_at` | `DateTime` | No | |
| `closed_at` | `DateTime` | Yes | Set when `status` becomes `"closed"` |
| `investigator_notes` | `Text` | Yes | |

---

## `audit_logs` — planned (Day 6)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `Integer` | No | **PK**, autoincrement |
| `case_id` | `Integer` | Yes | **FK → `cases.id`**; nullable — not every logged action is tied to a case |
| `athlete_id` | `Integer` | No | **FK → `athletes.id`** |
| `actor` | `String` | No | Who/what performed the action |
| `action` | `String` | No | Free text, e.g. `"target_test_ordered"` |
| `timestamp` | `DateTime` | No | |
| `details_json` | `Text` | Yes | JSON string, arbitrary structured detail for the action |

---

## `evidence` — planned (Day 6)

No endpoint reads or writes this table yet per `docs/api-contract.md`
(flagged there as a schema table with no corresponding route). Column
types are provisional pending Day 6 design.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `Integer` | No | **PK**, autoincrement |
| `case_id` | `Integer` | No | **FK → `cases.id`** |
| `sample_id` | `Integer` | Yes | **FK → `samples.id`**; nullable — *assumption*, in case a piece of evidence isn't tied to a specific sample (e.g. an interview note) |
| `note` | `Text` | No | |
| `added_at` | `DateTime` | No | |

---

## `cohort_stats` — planned, optional

No surrogate `id` in the given schema — `(sport, biomarker)` is the
natural composite key, one row per sport/biomarker pair. Not exposed
via any endpoint; used server-side to compute
`contributing_biomarkers` z-scores in `GET /athletes/{id}/anomalies`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `sport` | `String` | No | **PK (composite, part 1)** |
| `biomarker` | `String` | No | **PK (composite, part 2)**; one of `hb`, `hct`, `ret_pct`, `off_score`, `te_ratio` |
| `population_mean` | `Float` | No | |
| `population_std` | `Float` | No | |

---

## `ground_truth` — planned, optional, **HIDDEN**

> Internal-evaluation-only. Never exposed via any API endpoint,
> dashboard, or query result returned to the frontend. See the warning
> at the top of this document and in `docs/api-contract.md`.

`athlete_id` is the primary key directly (one row per athlete), not a
separate surrogate `id`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `athlete_id` | `Integer` | No | **PK**, **FK → `athletes.id`** |
| `is_synthetic_anomaly` | `Boolean` | No | |
| `pattern_type` | `String` | Yes | Null when `is_synthetic_anomaly` is false; e.g. `"micro_dosing"` when true |
