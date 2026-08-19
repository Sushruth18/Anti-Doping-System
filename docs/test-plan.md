# Test Plan — Adaptive Anti-Doping Defense Engine
## Day 6 QA Checklist

Run this against the **live deployed Render URL** before sign-off.
Replace `{BASE_URL}` with the actual deployed root (e.g.
`https://anti-doping-system.onrender.com`). Replace `{ATHLETE_ID_*}`
with real IDs from the live database as noted.

> **Do not edit `docs/api-contract.md` based on findings here.** If
> a response shape differs from the contract, raise it in the team
> channel — the contract is the source of truth.

---

## Prerequisites

- [ ] Confirm the deployed URL is reachable (`curl {BASE_URL}/athletes` returns HTTP 200)
- [ ] Identify the following test athlete IDs from the live data:
  - `{ATHLETE_ID_ZERO_SAMPLES}` — an athlete with 0 samples (if one exists; skip section if not)
  - `{ATHLETE_ID_ONE_SAMPLE}` — an athlete with exactly 1 sample
  - `{ATHLETE_ID_FULL}` — an athlete with a full sample history (≥5 samples)
  - `{ATHLETE_ID_VALID}` — any valid athlete ID for general endpoint tests
  - `{CASE_ID_VALID}` — a valid open case ID (create one via `POST /cases` if needed)

---

## Section 1 — Athlete list (`GET /athletes`)

### 1.1 Default request

```
GET {BASE_URL}/athletes
```

- [ ] Returns HTTP **200**
- [ ] Response is a JSON **array** (not an object/envelope)
- [ ] Each item has keys: `id`, `name`, `sport`, `age`, `latest_anomaly_score`, `latest_uncertainty_score`, `priority_score`, `last_sample_date`, `scored`
- [ ] Array is sorted descending by `priority_score` (highest first)
- [ ] Athletes with `scored: false` have `latest_anomaly_score: null`

### 1.2 Sport filter

```
GET {BASE_URL}/athletes?sport=Cycling
```

- [ ] Returns HTTP **200**
- [ ] All returned athletes have `sport == "Cycling"`
- [ ] Omit filter → all sports returned

### 1.3 Sort parameter

```
GET {BASE_URL}/athletes?sort=priority
```

- [ ] Returns HTTP **200**, same result as 1.1

```
GET {BASE_URL}/athletes?sort=invalid_value
```

- [ ] Returns HTTP **422**

---

## Section 2 — Athlete detail (`GET /athletes/{id}`)

### 2.1 Full-history athlete

```
GET {BASE_URL}/athletes/{ATHLETE_ID_FULL}
```

- [ ] Returns HTTP **200**
- [ ] Response has keys: `id`, `name`, `sport`, `age`, `baseline_prior`, `samples`
- [ ] `baseline_prior` has keys for all five biomarkers: `hb`, `hct`, `ret_pct`, `off_score`, `te_ratio`, each with `mean` and `std`
- [ ] `samples` is an array sorted **ascending** by `date`
- [ ] Each sample has: `id`, `athlete_id`, `date`, `hb`, `hct`, `ret_pct`, `off_score`, `te_ratio`, `competition_flag`, `altitude_flag`, `injury_flag`
- [ ] `off_score` is present and numeric (server-derived, not null)

### 2.2 Single-sample athlete

```
GET {BASE_URL}/athletes/{ATHLETE_ID_ONE_SAMPLE}
```

- [ ] Returns HTTP **200**
- [ ] `samples` array has exactly 1 entry
- [ ] `baseline_prior` is present (seeded from population prior even with 1 sample)

### 2.3 Zero-sample athlete *(skip if no such athlete exists)*

```
GET {BASE_URL}/athletes/{ATHLETE_ID_ZERO_SAMPLES}
```

- [ ] Returns HTTP **200**
- [ ] `samples` is an empty array `[]`
- [ ] `baseline_prior` is present (population prior, not null)

### 2.4 Unknown athlete

```
GET {BASE_URL}/athletes/99999
```

- [ ] Returns HTTP **404**
- [ ] Response body is `{"detail": "Athlete 99999 not found"}` (or equivalent message)

---

## Section 3 — Trajectory (`GET /athletes/{id}/trajectory`)

```
GET {BASE_URL}/athletes/{ATHLETE_ID_FULL}/trajectory
```

- [ ] Returns HTTP **200**
- [ ] Response has keys: `athlete_id`, `ci_level`, `series`
- [ ] `ci_level` is a number (e.g. `0.95`)
- [ ] `series` is an array with **5 entries** — one per biomarker (`hb`, `hct`, `ret_pct`, `off_score`, `te_ratio`)
- [ ] Each series entry has: `biomarker`, `unit`, `points`
- [ ] Each point has: `date`, `observed`, `expected`, `ci_lower`, `ci_upper`
- [ ] `ci_lower < expected < ci_upper` for all points

```
GET {BASE_URL}/athletes/99999/trajectory
```

- [ ] Returns HTTP **404**

---

## Section 4 — Anomaly history (`GET /athletes/{id}/anomalies`)

### 4.1 Athlete with anomalies

```
GET {BASE_URL}/athletes/{ATHLETE_ID_FULL}/anomalies
```

- [ ] Returns HTTP **200**
- [ ] Response is a JSON **array**
- [ ] If non-empty: items sorted **descending** by `created_at` (newest first)
- [ ] Each item has: `id`, `athlete_id`, `sample_id`, `anomaly_score`, `mahalanobis_distance`, `method`, `created_at`, `contributing_biomarkers`
- [ ] `anomaly_score` is between 0 and 1 inclusive
- [ ] `contributing_biomarkers` is an array; each entry has: `biomarker`, `observed_value`, `posterior_mean`, `z_score_squared`, `deviation_direction`
- [ ] `contributing_biomarkers` is sorted **descending** by `z_score_squared`

### 4.2 Athlete with zero anomalies

```
GET {BASE_URL}/athletes/{ATHLETE_ID_ZERO_SAMPLES}/anomalies
```

*(or any athlete known to have no anomalies yet)*

- [ ] Returns HTTP **200** with `[]` — **not** 404

### 4.3 Unknown athlete

```
GET {BASE_URL}/athletes/99999/anomalies
```

- [ ] Returns HTTP **404**

---

## Section 5 — Recommendation (`GET /athletes/{id}/recommendation`)

> **Status:** Day 4/5 endpoint — confirm it is live before running.

```
GET {BASE_URL}/athletes/{ATHLETE_ID_FULL}/recommendation
```

- [ ] Returns HTTP **200**
- [ ] Response has keys: `id`, `athlete_id`, `action_type`, `value_score`, `uncertainty_score`, `anomaly_score`, `cost`, `explanation_text`, `created_at`
- [ ] `action_type` is one of: `no_action`, `increase_monitoring`, `target_test`, `biological_passport_review`, `open_case`
- [ ] `value_score` and `uncertainty_score` are between 0 and 1

```
GET {BASE_URL}/athletes/99999/recommendation
```

- [ ] Returns HTTP **404**

---

## Section 6 — Budget recommendations (`GET /recommendations/budget`)

> **Status:** Day 4/5 endpoint — confirm it is live before running.

```
GET {BASE_URL}/recommendations/budget?budget=5
```

- [ ] Returns HTTP **200**
- [ ] Response has keys: `budget`, `total_cost_used`, `selected`
- [ ] `total_cost_used <= budget`
- [ ] Each item in `selected` has: all `Recommendation` fields plus `athlete_name`, `sport`, `rank`
- [ ] `rank` values are 1-indexed and sequential

```
GET {BASE_URL}/recommendations/budget
```

*(missing budget param)*

- [ ] Returns HTTP **422**

```
GET {BASE_URL}/recommendations/budget?budget=-1
```

- [ ] Returns HTTP **422**

---

## Section 7 — Ingest new sample (`POST /athletes/{id}/samples`)

> **Status:** Day 4/5 endpoint — confirm it is live before running.

### 7.1 Valid ingest

```
POST {BASE_URL}/athletes/{ATHLETE_ID_VALID}/samples
Content-Type: application/json

{
  "date": "2026-06-01",
  "hb": 14.8,
  "hct": 43.5,
  "ret_pct": 1.1,
  "te_ratio": 1.05,
  "competition_flag": false,
  "altitude_flag": false,
  "injury_flag": false
}
```

- [ ] Returns HTTP **201**
- [ ] Response has keys: `sample`, `updated_baseline`, `anomaly`
- [ ] `sample.off_score` is present and numeric (server-computed)
- [ ] `off_score` is **not** present in the request body — server derives it
- [ ] `updated_baseline` has all five biomarkers with `mean` and `std`

### 7.2 Reject client-supplied `off_score`

Same body as 7.1, adding `"off_score": 90.0`:

- [ ] Returns HTTP **422**

### 7.3 Missing required field

```json
{ "date": "2026-06-01", "hb": 14.8 }
```

- [ ] Returns HTTP **422**

### 7.4 Unknown athlete

```
POST {BASE_URL}/athletes/99999/samples
```

- [ ] Returns HTTP **404**

---

## Section 8 — Cases (`POST /cases`, `POST /cases/{id}/decision`)

> **Status:** Day 4/5 endpoint — confirm it is live before running.

### 8.1 Open a case

```
POST {BASE_URL}/cases
Content-Type: application/json

{"athlete_id": {ATHLETE_ID_VALID}}
```

- [ ] Returns HTTP **201**
- [ ] Response has keys: `id`, `athlete_id`, `status`, `opened_at`, `closed_at`, `investigator_notes`
- [ ] `status == "open"`, `closed_at == null`
- [ ] Note the returned `id` as `{CASE_ID_VALID}` for the next step

### 8.2 Log a decision

```
POST {BASE_URL}/cases/{CASE_ID_VALID}/decision
Content-Type: application/json

{"action": "escalate", "investigator": "QA-tester"}
```

- [ ] Returns HTTP **201**
- [ ] Response has keys: `case`, `audit_log`
- [ ] `case.status` is still `"open"` (only `close_case` closes it)
- [ ] `audit_log` has: `id`, `case_id`, `athlete_id`, `actor`, `action`, `timestamp`, `details`

### 8.3 Close a case

```
POST {BASE_URL}/cases/{CASE_ID_VALID}/decision
Content-Type: application/json

{"action": "close_case", "investigator": "QA-tester"}
```

- [ ] Returns HTTP **201**
- [ ] `case.status == "closed"` and `case.closed_at` is non-null

### 8.4 Invalid action

```
POST {BASE_URL}/cases/{CASE_ID_VALID}/decision
Content-Type: application/json

{"action": "invalid_action", "investigator": "QA-tester"}
```

- [ ] Returns HTTP **422**

---

## Section 9 — Audit timeline (`GET /audit/{athlete_id}`)

> **Status:** Day 4/5 endpoint — confirm it is live before running.

```
GET {BASE_URL}/audit/{ATHLETE_ID_FULL}
```

- [ ] Returns HTTP **200**
- [ ] Response has keys: `athlete_id`, `events`
- [ ] `events` is sorted **ascending** by `timestamp` (oldest first)
- [ ] Each event has: `type`, `timestamp`, `data`
- [ ] `type` values are among: `sample`, `anomaly`, `recommendation`, `case_opened`, `case_closed`, `decision`

```
GET {BASE_URL}/audit/{ATHLETE_ID_ZERO_SAMPLES}
```

- [ ] Returns HTTP **200** with `events: []` — **not** 404

```
GET {BASE_URL}/audit/99999
```

- [ ] Returns HTTP **404**

---

## Section 10 — CUSUM evasion simulation (`GET /simulation/evasion`)

> **Status:** Day 4/5 endpoint — confirm it is live before running.

```
GET {BASE_URL}/simulation/evasion?pattern=micro_dosing
```

- [ ] Returns HTTP **200**
- [ ] Response has keys: `pattern`, `sample_series`, `single_sample_detection`, `cusum_detection`
- [ ] `sample_series` is an array; each item has `day` and `off_score`
- [ ] `single_sample_detection` and `cusum_detection` each have: `method`, `flagged_days`, `first_detection_day`, `detection_rate`
- [ ] `detection_rate` is between 0 and 1

```
GET {BASE_URL}/simulation/evasion?pattern=unsupported_pattern
```

- [ ] Returns HTTP **422**

```
GET {BASE_URL}/simulation/evasion
```

*(missing required `pattern` param)*

- [ ] Returns HTTP **422**

---

## Section 11 — Error state / backend down

- [ ] Kill or pause the backend process (or set DNS to a non-existent host)
- [ ] Confirm the frontend dashboard shows a user-visible error state (not a blank screen or unhandled exception)
- [ ] Confirm no sensitive internal data (stack traces, DB connection strings) is exposed in the error UI
- [ ] Restore the backend and confirm the dashboard recovers without a hard refresh

---

## Sign-off

| Check | Pass / Fail | Notes |
|---|---|---|
| Sections 1–4 (Day 3 MVP endpoints) | | |
| Sections 5–10 (Day 4/5 endpoints, if live) | | |
| Section 11 (error state) | | |
| All 200 responses have expected top-level keys | | |
| All error responses use correct HTTP status codes | | |

Completed by: _________________________ Date: _____________
