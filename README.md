# Adaptive Anti-Doping Defense Engine

A monitoring and triage system for athlete biological data. It tracks
blood biomarkers (Hb, HCT, RET%, OFF-score, T/E ratio) per athlete over
time, flags statistical anomalies against a per-athlete Bayesian
baseline and sport-level cohort statistics, and produces
budget-constrained investigation recommendations for human
investigators.

## Structure

```
backend/    FastAPI + SQLAlchemy + SQLite API
frontend/   Vite + React + TypeScript + Tailwind CSS dashboard
docs/       Shared API contract (source of truth for both sides)
ml/         (Dev 2, not yet in the repo) anomaly detection / recommendation models
data/       (Dev 2, not yet in the repo) model output consumed by the backend
```

`docs/api-contract.md` is the binding contract between the frontend
and backend/ML — response shapes, endpoint list, and error formats.
`frontend/src/types/api.ts` and `frontend/mock/*.json` mirror it
exactly so the frontend can be built against realistic fixtures ahead
of the live backend.

## Getting started

### Backend

```
cd backend
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
cp .env.example .env             # then edit if you need a different DATABASE_URL
python -m app.db.init_db         # creates SQLite tables (app.db), no seed data
uvicorn app.main:app --reload
```

API runs at `http://127.0.0.1:8000`. Check `GET /health` for a
liveness probe.

### Frontend

```
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:5173`.

## Project status

**Day 1 (done):** repo scaffolding for both frontend and backend, the
API contract and matching mock fixtures, and the first two database
models (`Athlete`, `Sample`).

**Day 2 (in progress):** database seeding and the first real CRUD
endpoints, replacing the static mocks.

See `CLAUDE.md` for the current ownership split between developers and
the day-by-day build plan.

## Deployment

The frontend deploys to Vercel (root directory `frontend`, framework
preset "Vite"). The backend does not yet have a deployment target
configured.
