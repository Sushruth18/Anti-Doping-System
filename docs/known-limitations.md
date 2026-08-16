# Known Limitations

Backend/API-side known limitations and deferred decisions (Dev 1 scope —
`/backend`, `/frontend`). See `docs/dataset-summary.md`'s own "Known
limitations" section for the ML/data-generation-side biomarker-independence
assumption in `anomaly.py`'s Mahalanobis scoring (Dev 2 scope).

## `latest_uncertainty_score` is computed live, not read from a persisted column

`latest_uncertainty_score` (in `GET /athletes`) is currently computed live
on every request via `_compute_latest_uncertainty_score()`, not read from a
persisted `recommendations.uncertainty_score` column as
`docs/api-contract.md` describes — because the `recommendations` table
doesn't exist yet (pending `ml/action_engine.py`, Day 4).

Once that table and the `/recommendation` endpoint exist, a decision is
needed: keep the live recomputation in `/athletes`, or switch to reading
the persisted value written by the recommendation endpoint — and confirm
the two paths can never silently diverge (same class of bug as the earlier
trajectory-route `obs_var` duplication, now fixed).

Also note: `latest_uncertainty_score` is only wired into `AthleteListItem`
(`/athletes`), not `AthleteDetail` (`/athletes/{id}`) — the locked contract
doesn't include it on the detail shape, so it wasn't added there without an
explicit flag/discussion.

## `GET /athletes/{id}/recommendation` returns `id: null`, not a real id

`GET /athletes/{id}/recommendation` currently returns `id: null` (typed
`int | None`), deviating from the locked contract's `id: number`, because
no `recommendations` table exists yet to assign a real primary key from
(`compute_recommendation()` is compute-only, not persisted).

This is the same root cause already noted above for
`latest_uncertainty_score`'s live-vs-persisted question: once the
`recommendations` table + write path exist (tracked as a Day 4
follow-up), both issues should be resolved together — decide then whether
`GET /athletes/{id}/recommendation` reads/writes a persisted row (giving
it a real id) or stays compute-only with `id` remaining nullable by
design.

`GET /audit/{athlete_id}` (Day 5, not yet built) will hit this same issue too — its `AuditEvent` union includes a `recommendation` variant, and without a persisted `recommendations` table there's no real history to show, only the current live-computed recommendation; resolve this as a third symptom of the same root cause when the `recommendations` table lands, not ad-hoc for `/audit` specifically.
