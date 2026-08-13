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
- **Developer 2** owns `/ml` (standalone scripts) and the outputs
  written to `/data`. Dev 1 **consumes** `/data` outputs — reads them,
  never edits them. Neither `/ml` nor `/data` exists in the repo yet as
  of Day 1; they'll appear as Dev 2's work lands.

## Never touch without asking

Changing any of these requires flagging it in chat (or the commit
message) **before** the edit, even if the change looks obviously
correct — these are shared contracts other people's code depends on
matching exactly:

- `docs/api-contract.md`
- `docs/schema.md` (not created yet, but the rule applies as soon as it
  exists)
- Field names/types inside `/data/*.json` (Dev 2's output files)

If a change to any of these seems necessary, say so and wait for
confirmation rather than editing and mentioning it after the fact.

## Standing guardrail: `ground_truth` is never exposed

The `ground_truth(athlete_id, is_synthetic_anomaly, pattern_type)`
table is internal-evaluation-only. It must never appear in any API
response, frontend type, mock fixture, or UI — in this or any future
session. See the warning banner at the top of `docs/api-contract.md`
for the full rationale before adding anything that touches it.

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
