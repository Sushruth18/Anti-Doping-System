# CLAUDE.md

Instructions for Claude Code when working in this repository. This is
read at the start of every session — keep it accurate as the project
moves through its daily stages, don't let it drift from reality.

## Project summary

The Adaptive Anti-Doping Defense Engine is a monitoring and triage
system for athlete biological data. It tracks blood biomarkers (Hb,
HCT, RET%, OFF-score, T/E ratio) per athlete over time, flags
statistical anomalies against a per-athlete Bayesian baseline and
sport-level cohort stats, and produces budget-constrained
investigation recommendations for human investigators. It is built in
daily stages by two developers working in parallel against a locked
API contract: a FastAPI + SQLAlchemy + SQLite backend, a
Vite + React + TypeScript + Tailwind frontend, and a separate ML
component that produces the anomaly-detection/recommendation logic
consumed by the backend.

## Ownership map

- **Developer 1** owns `/frontend`, `/backend` (all folders/files
  under it), and deployment config (e.g. Vercel settings for the
  frontend). This is the primary scope Claude Code should be operating
  in for most sessions.
- **Developer 2** owns `/ml` (standalone scripts — `generate_data.py`,
  `evaluation.ipynb`, throwaway check/plot scripts) and the outputs
  written to `/data` (`athletes.json`, `samples.json`, and later
  `ground_truth.json`, `cohort_stats.json`). Dev 1 **consumes** `/data`
  outputs via the seed script — reads them, never edits them. Dev 2
  also owns Dev-2-authored docs under `/docs` when they land
  (e.g. `dataset-summary.md`, `data-methodology.md`).

## Developer 2 scope and conventions

**Primary workspace:** `/ml` for generation/evaluation scripts;
`/data` for JSON output Dev 1 seeds from. Do not edit `/backend` or
`/frontend`.

**Shared contracts — read, don't rewrite unilaterally:**

- `docs/schema.md` is **Dev 1–authored and locked**. Dev 2 **verifies**
  it against generator output and live models; only propose edits (in
  chat/PR) when a genuine field/type mismatch is found — never
  restructure or "clean up" spec docs.
- `docs/api-contract.md` — same rule: flag before editing.
- `/data/*.json` **field names and types** must match `docs/schema.md`
  exactly. Shape changes require Dev 1 review before the seed script
  depends on them.

**Locked OFF-score formula** (use wherever `off_score` is computed):

```
off_score = (hb_g_dL * 10) - 60 * sqrt(ret_pct)
```

`hb` is stored in g/dL; `ret_pct` is a **percentage** (e.g. 0.8–2.5,
not a fraction). Convert Hb to g/L (×10) before applying the formula.

**`/data` handoff:** Dev 1's seed script currently reads whatever is
in `/data`. Early `/data` may be Dev 1 hand-written placeholder; Dev 2
overwrites with generator output — ping Dev 1 when a new dataset is
ready so they can re-run the seed script.

**Not Dev 2 blockers on Day 1–2:** `anomalies` / `recommendations`
tables, live anomaly scoring, and the trajectory endpoint's real
posterior CI band are **Day 3+** (Dev 1). Dev 2 focuses on dataset
generation and offline evaluation (`ml/evaluation.ipynb`).

**Key commands** (from repo root):

```
python ml/generate_data.py          # regenerate data/athletes.json + data/samples.json
python ml/_visual_check_v05.py      # save Hb trajectory plot (optional sanity)
python -m nbconvert --execute ml/evaluation.ipynb --inplace   # run sanity checks
```

**`/backend/app/ml/` vs Dev 2's `/ml/`:** `/backend/app/ml/` holds
**ported** versions of validated Dev 2 logic for the live FastAPI app.
Do not import from `/ml` at runtime in the backend; translate and port
after offline validation.

## Never touch without asking

Changing any of these requires flagging it in chat (or the commit
message) **before** the edit, even if the change looks obviously
correct — these are shared contracts other people's code depends on
matching exactly:

- `docs/api-contract.md`
- `docs/schema.md` — Dev 1–authored; Dev 2 verifies, does not rewrite
  unless flagging a confirmed mismatch in chat/PR first
- Field names/types inside `/data/*.json` (Dev 2's output files —
  shape changes need Dev 1 review before merge)

If a change to any of these seems necessary, say so and wait for
confirmation rather than editing and mentioning it after the fact.

## Standing guardrail: `ground_truth` is never exposed

The `ground_truth(athlete_id, is_synthetic_anomaly, pattern_type)`
table is internal-evaluation-only. It must never appear in any API
response, frontend type, mock fixture, or UI — in this or any future
session. See the warning banner at the top of `docs/api-contract.md`
for the full rationale before adding anything that touches it.

## Developer 2 — Day 1 complete

Generator v0.5 (`ml/generate_data.py`): autocorrelated Hb random walk,
placeholder constants for hct/ret_pct/te_ratio, schema-conformant
`data/athletes.json` (10 athletes) + `data/samples.json` (50 samples).
`ml/evaluation.ipynb` skeleton with functional load + sanity checks;
trajectory plots, anomaly stats, and precision/recall sections stubbed
for Day 2–4.

**Day 2 starts (Dev 2):** full 5-biomarker correlated generator, 80
athletes, no anomalies yet (v1); extend `evaluation.ipynb` trajectory
plots.

## Current stage

**Day 1 complete:** frontend scaffold (Vite/React/TS/Tailwind),
backend scaffold (FastAPI, CORS open for dev), `docs/api-contract.md`
locked (with the corrected OFF-score formula), matching
`frontend/src/types/api.ts` and `frontend/mock/*.json` fixtures, and
the first two SQLAlchemy models (`Athlete`, `Sample`) with a working
`init_db.py`.

**Day 2 starts:** DB seeding and real CRUD endpoints (`GET /athletes`,
`GET /athletes/{id}`, and the rest of the Day 3 MVP live-priority
routes per the contract) — replacing the static mocks with a real
backend, one endpoint at a time.

## Key commands

**Backend** (from `/backend`, venv already created):
```
venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
uvicorn app.main:app --reload    # http://127.0.0.1:8000, /health to check
```

**Frontend** (from `/frontend`):
```
npm install
npm run dev                       # http://localhost:5173
```

**DB init** (from `/backend`, creates tables in `app.db`, no seed data):
```
python -m app.db.init_db
```

## `/backend/app/ml/` vs Dev 2's `/ml/`

`/backend/app/ml/` doesn't exist yet — it will later hold **ported**
versions of Dev 2's detection/recommendation logic, adapted to run
inside the FastAPI app. Do not have the live backend import directly
from Dev 2's `/ml` folder; treat `/ml` as a reference implementation
that gets translated into `/backend/app/ml/`, not a runtime dependency.
