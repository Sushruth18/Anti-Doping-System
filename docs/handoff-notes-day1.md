Here's a report you can share directly with Dev 2 — it covers what's already built, what changed from the original roadmap, and exactly what she needs to know before starting her Day 1 tasks.

---

# Status Report for Dev 2 — Handoff Before Day 1 Data Work

## 1. Where things stand (Dev 1 side)

Day 1 scaffolding + Day 2 vertical slice through Dashboard are done and pushed to `main`:
- Backend boots, `/health` works
- `athletes`/`samples` tables exist, matching `docs/schema.md` exactly
- `GET /athletes` and `GET /athletes/{id}` are live, tested, and working
- Dashboard fetches real data from the backend and renders it
- Seed script (`backend/app/db/seed.py`) is built and working — **it currently seeds from placeholder data I wrote by hand, not your real generator output**

## 2. Critical: what you need to match exactly

Your generator's output (`data/athletes.json`, `data/samples.json`) **must match `docs/schema.md`'s field names and types exactly** — the seed script and both live endpoints already depend on this shape. Specifically:

**`athletes`:** `id`, `name`, `sport` (plain string, not an enum), `age` (nullable), `baseline_prior_json` (nullable, JSON string shaped `{biomarker: {mean, std}}`)

**`samples`:** `id`, `athlete_id`, `date`, `hb`, `hct`, `ret_pct`, `off_score`, `te_ratio`, `competition_flag`, `altitude_flag`, `injury_flag` (three flags default `False`)

**Important — OFF-score formula, confirmed and locked:**
```
off_score = (hb_g_dL * 10) - 60 * sqrt(ret_pct)
```
This is computed server-side in the real app, but since your generator will presumably also compute/validate it, use this exact formula. (We caught and fixed a stale warning in `schema.md` that incorrectly claimed this formula was inconsistent across docs — it wasn't, everything already matches this version. You can ignore that concern entirely.)

## 3. Deviations from the original roadmap you should know about

**a) Placeholder data currently in `/data`**
Since your real generator hadn't started yet, I hand-wrote a tiny fake dataset (3 athletes, ~14 samples total, obviously-fake names like "Test Athlete 1") just to unblock the seed script and endpoint testing. **You'll overwrite `/data/athletes.json` and `/data/samples.json` with your real output** — no code changes needed on my end when you do, the seed script just re-reads whatever's there. Let me know when you're about to hand off v0 so I can re-run the seed script and re-verify.

**b) `latest_anomaly_score` / `latest_uncertainty_score` are hardcoded `null` right now**
These fields exist in the `/athletes` response shape per the contract, but since the `anomalies`/`recommendations` tables don't exist yet (that's Day 3 work), they're currently always `null`, and `priority_score` falls back to `0.0` for every athlete. This is intentional and matches the contract's documented fallback — not a bug. It just means the dashboard's priority sort is currently a no-op until Day 3 lands.

**c) One real gap in the contract we found: undefined tie-break**
`api-contract.md` defines the sort as "descending `priority_score`, tie-break by descending `latest_uncertainty_score`" — but doesn't say what happens when *both* are null/0, which is the current state for every athlete. Right now it silently falls back to DB insertion order. This isn't urgent, but flag it as something to nail down explicitly once your evaluation/anomaly work is closer, so the contract has a real answer instead of an implicit one.

**d) DB path bug fixed (infrastructure only, doesn't affect you)**
Found and fixed a bug where the SQLite path was resolved relative to whatever directory a command was launched from, instead of a fixed location — could've caused duplicate/empty DB files. Fully resolved, verified from both the repo root and `/backend`. No action needed on your side, just mentioning it in case you ever see a stray `app.db` file anywhere and wonder why.

**e) `sort` param on `/athletes` validates strictly**
If you or anyone hits `/athletes?sort=something_invalid`, it returns a clean `422` with `{"detail": "Unsupported sort value: 'X'"}` rather than silently ignoring it. Only `priority` is currently a valid value (more may be added later). Worth knowing if you ever script against the live endpoint directly for validation purposes.

## 4. What's NOT built yet (so you're not surprised)

- `anomalies`, `recommendations` tables — Day 3
- `/athletes/{id}/trajectory` — in progress on my end (Task 7), basic version only, no CI band yet
- Bayesian baseline math — I'm about to prototype this standalone in `ml/prototype_baseline.py` per the roadmap's Task 5/6 split (validate first, port into `backend/app/ml/baseline.py` after). **Since this overlaps with your own `ml/` workspace, let's coordinate** — the roadmap has you doing your own Bayesian prototype work too (Section 11, "Bayesian Baseline Prototype" task). We should sync on whether you're doing this in parallel or whether my version is just a placeholder to unblock the trajectory endpoint until your validated version lands. Worth a quick sync before either of us goes deep on it.

## 5. Immediate next steps for you

1. Read `docs/schema.md` and `docs/api-contract.md` (both committed, both current — no drift).
2. Start your v0 generator (1 biomarker, small athlete count) per the roadmap's Day 1 task.
3. Hand off early and often — even a rough v0 lets me re-verify the seed script against real (not fake) data sooner rather than later.
4. Flag me immediately if anything in `schema.md` doesn't give you enough to build against — I'd rather adjust the doc together than have you guess.

