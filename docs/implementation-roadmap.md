# Implementation Roadmap — Adaptive Anti-Doping Defense Engine
### From empty repository to deployed, judge-ready prototype in 6 days (2 workstreams)

Architecture, stack, features, schema and API contract are exactly as previously finalized. This document is execution only.

**Developer 1 (Main Dev):** one person, one PC, Claude Code, owns the entire core application — frontend, backend, DB, ML integration, recommendation engine, deployment.
**Developer 2 (Support Dev):** independent, free tools only (Cursor free / VS Code / Python), owns data generation, ML experimentation/validation, evaluation, documentation. Produces file-based deliverables Developer 1 pulls in — never blocks, never touches Developer 1's live repo directly except via PR.

---

## SECTION 1 — Build Order

| Stage | What gets built | Why here | Depends on | "Done" means |
|---|---|---|---|---|
| 1. Repo + scaffolding | GitHub repo, folder structure, `README.md`, `CLAUDE.md`, `.env.example`, empty FastAPI + Vite apps | Everything else needs a place to live and a shared contract doc | Nothing | `npm run dev` and `uvicorn` both boot to a blank page/health check |
| 2. API contract + mock fixtures | `docs/api-contract.md` finalized, `mock/*.json` matching it | Frontend must not wait on backend or ML | Stage 1 | Frontend can render real-looking screens off static JSON |
| 3. Database schema | SQLite tables from the finalized schema, seed script | Everything backend needs data to exist first | Stage 1 | `athletes`/`samples` tables exist, seed script runs without error |
| 4. Synthetic data (Dev 2, parallel from Day 1) | Generator script, v0 → v1 dataset | ML and DB both need real-shaped data ASAP | Stage 1 schema agreed | `athletes.json` + `samples.json` validate against schema |
| 5. Backend CRUD | `GET /athletes`, `GET /athletes/{id}`, DB-backed | Frontend's first real (non-mock) endpoint | Stage 3, 4 | Postman hits return real seeded data |
| 6. ML: baseline + anomaly | `ml/baseline.py`, `ml/anomaly.py` | Core intelligence the rest of the system depends on | Stage 4 (real data), Stage 3 (DB to persist scores) | Unit tests pass against hand-computed values |
| 7. Frontend vertical slice | Dashboard → Athlete Profile → Trajectory, wired to real backend | Prove the full path works before adding more | Stage 5, 6 | User can click through dashboard → profile → chart on real data |
| **8. DAY 3 MVP FREEZE** | — | — | Stages 1–7 | See §6 |
| 9. Uncertainty + Action Engine + Explanation | `ml/uncertainty.py`, `ml/action_engine.py`, `ml/explain.py` | Builds on baseline/anomaly, is the project's differentiator | Stage 6 | Recommendation endpoint returns ranked action + text |
| 10. Cases/audit | `cases`, `audit_logs` tables + endpoints + decision UI | Human-in-the-loop closes the story | Stage 5 | Investigator can log a decision, see it in timeline |
| 11. CUSUM + evasion sim, budget allocator | `ml/cusum.py`, `/simulation/evasion`, `/recommendations/budget` | P1 novelty features, safe to build after core works | Stage 9 | Endpoint + screen show before/after detection comparison |
| 12. Polish + deploy hardening | Loading/error states, cold-start mitigation, final QA | Judge-facing quality | Everything above | Full demo runs twice without error |

Deploy **continuously from Day 2**, not once at the end — deployment is stage-agnostic and runs alongside every stage above.

---

## SECTION 2 — Project Structure

```
/frontend
  /src
    /pages          Dashboard.tsx, AthleteProfile.tsx        (Dev 1)
    /components      TrajectoryChart.tsx, ExplanationPanel.tsx,
                     RecommendationPanel.tsx, DecisionPanel.tsx,
                     AuditTimeline.tsx, EvasionSim.tsx         (Dev 1)
    /api            client.ts (fetch wrapper), mock/*.json     (Dev 1)
    /types          shared TS types mirroring API contract     (Dev 1)
/backend
  /app
    /routes         athletes.py, cases.py, recommendations.py,
                     simulation.py                             (Dev 1)
    /db             models.py, seed.py, session.py             (Dev 1)
    /ml             baseline.py, anomaly.py, uncertainty.py,
                     action_engine.py, explain.py, cusum.py     (Dev 1, ports Dev 2's validated logic)
  /tests            test_athletes.py, test_ml.py               (Dev 1)
  requirements.txt
/ml                                                             (Dev 2 — standalone, not imported live)
  generate_data.py
  evaluation.ipynb
  cohort_stats.py
/data                                                           (Dev 2 output, Dev 1 consumes)
  athletes.json, samples.json, ground_truth.json (hidden), cohort_stats.json
/docs
  api-contract.md    ← SHARED CONTRACT, do not edit without flagging in chat/commit message
  schema.md          ← SHARED CONTRACT, same rule
CLAUDE.md            ← ownership + instructions for Claude Code, read at start of every session
README.md
.env.example
```

**Do not casually modify:** `docs/api-contract.md`, `docs/schema.md`, `/data/*.json` schema shape (field names/types) — any change here breaks the other side silently. Announce changes before making them.

---

## SECTION 3 — Day-by-Day Roadmap (summary)

| Day | Developer 1 focus | Developer 2 focus | Integration event |
|---|---|---|---|
| 1 | Repo, scaffolding, DB schema, API contract, mock fixtures | Data schema agreement, generator v0 (1 biomarker) | Merge scaffolds, confirm contract |
| 2 | DB seeding, `/athletes` CRUD, baseline math ported to `ml/baseline.py` | Full 5-biomarker generator with correlation, v1 dataset | Dev 1 pulls Dev 2's `data/*.json` into seed script |
| 3 | Anomaly detection, Dashboard/Profile/Trajectory screens wired to real API | Inject anomaly patterns (transfusion, micro-dosing), extend to 80 athletes | **MVP FREEZE** — full demo path live |
| 4 | Uncertainty, Action Engine, Explanation, recommendation endpoint + panel, cases/audit | Validation notebook (precision/recall vs. hidden ground truth) | Dev 1 pulls Dev 2's evaluation numbers into demo notes |
| 5 | CUSUM + evasion sim, budget allocator, audit timeline screen, full deploy hardening | Cohort stats, README/docs, final data lock | Full end-to-end test on deployed URLs |
| 6 | Bug fixes, UI polish, mock login, deployment stability | Final QA pass against test plan, demo talking points | Rehearsal, code freeze, demo freeze |

Detailed hour blocks are in Sections 4–9.

---

## SECTION 4 — Day 1 (Foundation)

**Goal by end of day:** empty repo → both apps boot, DB schema exists, API contract is written and agreed, mock JSON lets the frontend start rendering tomorrow.

| Time | Developer | Task | Files/Module | Output | Dependency | Tool | Priority |
|---|---|---|---|---|---|---|---|
| 09:00–09:30 | Both | Create GitHub repo, agree on branch strategy (`main`, `dev1/*`, `dev2/*`), create folder skeleton from §2 | repo root | Empty repo with folders + `README.md` | — | GitHub | P0 |
| 09:30–11:00 | Dev 1 | Scaffold FastAPI app: `main.py`, `/health` endpoint, `requirements.txt`, venv setup | `backend/app/main.py` | `curl localhost:8000/health` returns 200 | repo created | Claude Code | P0 |
| 09:30–11:00 | Dev 2 | Write `docs/schema.md` draft from the finalized schema (§8 of spec), review with Dev 1 async | `docs/schema.md` | Agreed schema doc | repo created | none | P0 |
| 11:00–13:00 | Dev 1 | Scaffold Vite+React+TS+Tailwind app, routing shell (`/`, `/athlete/:id`), deploy blank app to Vercel | `frontend/src/*` | Live Vercel URL showing routed blank pages | scaffold | Claude Code | P0 |
| 11:00–13:00 | Dev 2 | Start `ml/generate_data.py`: config dict (n_athletes, seed), random-walk generator for **1 biomarker (Hb) only**, output `data/athletes.json` v0 | `ml/generate_data.py` | v0 JSON, 10 fake athletes, 1 biomarker | schema.md | Cursor free | P0 |
| 14:00–16:00 | Dev 1 | Write `docs/api-contract.md` (all endpoints from spec §9), then create matching `frontend/mock/*.json` fixtures by hand | `docs/api-contract.md`, `frontend/mock/*.json` | Contract doc + fixtures frontend can import | schema.md | Claude Code | P0 |
| 14:00–16:00 | Dev 2 | Extend generator: proper correlated random walk for Hb (autocorrelated noise), write to config-driven output | `ml/generate_data.py` v0.5 | Realistic-looking single-biomarker series, visually checked in a quick matplotlib plot | v0 | Cursor free | P1 |
| 16:00–18:00 | Dev 1 | Create SQLite schema via SQLAlchemy models matching `schema.md`: `athletes`, `samples` tables (Day 3 tables only for now) | `backend/app/db/models.py`, `session.py` | `alembic`/create-all runs, empty tables exist | schema.md | Claude Code | P0 |
| 16:00–18:00 | Dev 2 | Draft `evaluation.ipynb` skeleton (empty sections: load data, compute anomaly stats, precision/recall) — not filled yet | `ml/evaluation.ipynb` | Skeleton notebook | — | none | P2 |
| 19:00–21:00 | Both | Write `CLAUDE.md` (ownership map from §2, "never touch X without asking" rules), commit everything to `main`, sanity-check both apps still boot | `CLAUDE.md` | Clean `main`, both apps run locally | all above | — | P0 |

**End of Day 1 — must be runnable:** `uvicorn` serves `/health`; Vite dev server + deployed Vercel URL show routed blank pages; SQLite file exists with empty `athletes`/`samples` tables; `docs/api-contract.md` and `docs/schema.md` committed; Dev 2 has a v0.5 single-biomarker generator producing plausible-looking output.

---

## SECTION 5 — Day 2 (First Vertical Slice)

**Goal:** prove `USER → FRONTEND → API → BACKEND → DATA → BASIC INTELLIGENCE → RESULT` works end to end, even simplified.

| Time | Developer | Task | Files/Module | Output | Dependency | Tool | Priority |
|---|---|---|---|---|---|---|---|
| 09:00–11:00 | Dev 1 | Write DB seed script that reads a JSON file into `athletes`/`samples` tables | `backend/app/db/seed.py` | `python seed.py` populates DB from any conforming JSON | models.py | Claude Code | P0 |
| 09:00–11:00 | Dev 2 | Finish full generator: all 5 biomarkers (Hb, HCT, RET%, OFF-score, T/E ratio) with realistic correlation, 80 athletes, no anomalies injected yet | `ml/generate_data.py` v1 | `data/athletes.json`, `data/samples.json` — full shape, no anomalies | v0.5 | Cursor free | P0 |
| 11:00–13:00 | Dev 1 | Run seed script against Dev 2's v1 data (hand off via `/data` folder or PR); implement `GET /athletes`, `GET /athletes/{id}` reading straight from DB (no ML yet) | `backend/app/routes/athletes.py` | Real endpoints return real seeded athletes | seed.py, v1 data | Claude Code | P0 |
| 11:00–13:00 | Dev 2 | Prototype Bayesian update math in a plain Python script (not the app) — Normal-Normal conjugate update — test on 1 athlete's Hb series by hand | `ml/prototype_baseline.py` | Printed proof it converges toward true mean with shrinking variance | v1 data | Cursor free | P0 |
| 14:00–16:00 | Dev 1 | Wire frontend Dashboard to real `/athletes` endpoint (replace mock JSON with fetch call) | `frontend/src/pages/Dashboard.tsx`, `api/client.ts` | Dashboard shows real 80 athletes from DB | `/athletes` live | Claude Code | P0 |
| 14:00–16:00 | Dev 2 | Add basic anomaly archetype #1 (blood-transfusion pattern) to generator for ~6% of athletes | `ml/generate_data.py` v1.1 | New `data/samples.json` with visible anomaly spikes in a plotted example | prototype_baseline validated | Cursor free | P1 |
| 16:00–18:00 | Dev 1 | Port Dev 2's validated Bayesian math into `backend/app/ml/baseline.py` as a proper module with `update_posterior()`, plus a simple z-score "basic intelligence" placeholder for anomaly scoring for today | `backend/app/ml/baseline.py` | Importable module, one unit test against hand-computed value | prototype_baseline.py | Claude Code | P0 |
| 16:00–18:00 | Dev 2 | Start `ml/evaluation.ipynb`: load v1.1 data, plot a few athlete trajectories to visually sanity-check anomaly injection looks realistic | `ml/evaluation.ipynb` | 3–4 plots showing normal vs. anomalous trajectories | v1.1 data | none | P1 |
| 19:00–21:00 | Dev 1 | Add `GET /athletes/{id}/trajectory` returning observed samples + baseline mean (simple version, full CI band comes Day 3), deploy backend to Render | `backend/app/routes/athletes.py`, Render config | Endpoint live on Render, returns real trajectory | baseline.py | Claude Code | P0 |

**Integration checkpoint (end of Day 2):** Dev 1 pulls latest `/data/*.json` from Dev 2, re-seeds DB, confirms dashboard shows 80 real athletes and one athlete's trajectory endpoint returns non-trivial baseline vs. observed values. This is the "vertical slice" — commit and tag `v0.2-vertical-slice`.

---

## SECTION 6 — Day 3 (MVP — Hard Deadline)

**Goal:** dashboard → athlete → trajectory-with-uncertainty → anomaly, fully deployed, demoable to judges today.

| Time | Developer | Task | Files/Module | Output | Dependency | Tool | Priority |
|---|---|---|---|---|---|---|---|
| 09:00–11:00 | Dev 1 | Implement Mahalanobis anomaly scoring in `ml/anomaly.py`, wire into `/athletes/{id}/anomalies`, store scores in `anomalies` table | `backend/app/ml/anomaly.py`, `routes/athletes.py` | Endpoint returns real anomaly score + contributing biomarkers | baseline.py | Claude Code | P0 |
| 09:00–11:00 | Dev 2 | Add anomaly archetype #2 (EPO micro-dosing) and #3 (steroid micro-dosing) to generator, finalize v1.2 dataset, write hidden `ground_truth.json` | `ml/generate_data.py` v1.2 | Full 3-archetype dataset + hidden labels file | v1.1 | Cursor free | P0 |
| 11:00–13:00 | Dev 1 | Build `TrajectoryChart.tsx` with Recharts: observed points + baseline line + confidence band (basic ± SD band for now, refine later) | `frontend/src/components/TrajectoryChart.tsx` | Chart renders real trajectory + band on Athlete Profile page | trajectory endpoint | Claude Code | P0 |
| 11:00–13:00 | Dev 2 | Re-seed test: run generator v1.2, spot-check 5 athletes' plots against ground truth for realism | `ml/evaluation.ipynb` | Confirmed dataset looks right before it gets frozen | v1.2 | none | P0 |
| 14:00–16:00 | Dev 1 | Build `AthleteProfile.tsx` (header + trajectory + basic anomaly panel), re-seed DB with v1.2 final dataset | `frontend/src/pages/AthleteProfile.tsx` | Full profile page live, real anomaly data shown | anomaly.py, v1.2 data | Claude Code | P0 |
| 14:00–16:00 | Dev 2 | Hand off final `data/athletes.json`, `samples.json`, `ground_truth.json` (hidden — do not wire into frontend/API) via PR to `/data` | `/data/*` | Final MVP dataset frozen | — | Cursor free | P0 |
| 16:00–18:00 | Dev 1 | Add basic "Anomaly Explanation" text (even a simple templated sentence is fine today — full NLG comes Day 4), sort Dashboard by anomaly score (priority) | `Dashboard.tsx`, `ExplanationPanel.tsx` (basic) | Dashboard priority-sorted, profile shows a plain-English flag reason | anomaly.py | Claude Code | P0 |
| 16:00–18:00 | Dev 2 | Prepare a 5-line written summary of the dataset (n athletes, archetypes, sample counts) for later demo narration | `docs/dataset-summary.md` | Ready-to-read stat block | final dataset | none | P1 |
| 19:00–20:00 | Dev 1 | Deploy final MVP build to Vercel + Render, smoke test both live URLs end to end | deployment configs | Public URL, full flow works: Dashboard → Athlete → Trajectory → Anomaly | all above | Claude Code | P0 |
| 20:00–21:00 | Both | **MVP FREEZE** — run the exact judge-facing flow twice, fix only blocking bugs, commit + tag `v0.3-mvp-freeze` | — | Signed-off, demoable MVP | — | — | P0 |

### MVP FREEZE
- **Frozen:** `athletes`/`samples` schema shape, API contract for `/athletes`, `/athletes/{id}`, `/athletes/{id}/trajectory`, `/athletes/{id}/anomalies`, the frozen v1.2 dataset.
- **Must not change:** field names/types in the frozen endpoints — any Day 4+ work adds new endpoints/fields, it does not rename or remove existing ones.
- **Postponed to Day 4+:** uncertainty scoring, recommendation engine, explanation NLG upgrade, cases/audit, CUSUM/evasion sim, budget allocator, cohort view, login.
- **How development continues safely:** all Day 4+ work happens in new files/new endpoints or additive fields, branched off `v0.3-mvp-freeze`; the frozen flow is re-tested at the end of every subsequent day before merging further changes to `main`.

---

## SECTION 7 — Day 4 (Upgrade the MVP: mocks → real)

**Goal:** replace placeholder logic with the real intelligence layer; add human-in-the-loop.

| Time | Developer | Task | Files/Module | Output | Dependency | Tool | Priority |
|---|---|---|---|---|---|---|---|
| 09:00–11:00 | Dev 1 | Implement `ml/uncertainty.py` (posterior variance → normalized 0–1 score, CI width for chart band), upgrade `TrajectoryChart.tsx` band from ± SD placeholder to real posterior CI | `backend/app/ml/uncertainty.py`, chart component | Real, distinct uncertainty score visible on profile | baseline.py | Claude Code | P0 |
| 09:00–11:00 | Dev 2 | Run `evaluation.ipynb` fully: compute precision/recall of current anomaly detector against hidden `ground_truth.json`; record numbers | `ml/evaluation.ipynb` | Metrics table (e.g. "82% recall at 15% FPR on injected anomalies") | frozen dataset | none | P0 |
| 11:00–13:00 | Dev 1 | Implement `ml/action_engine.py` (Value Score = anomaly × uncertainty × sensitivity ÷ cost) + `GET /athletes/{id}/recommendation` | `backend/app/ml/action_engine.py`, route | Endpoint returns ranked recommended action | uncertainty.py, anomaly.py | Claude Code | P0 |
| 11:00–13:00 | Dev 2 | Start IsolationForest secondary check as a standalone script; compare its flags against the Mahalanobis-only results | `ml/isoforest_check.py` | Comparison notebook cell/plot | evaluation.ipynb | Cursor free | P1 |
| 14:00–16:00 | Dev 1 | Implement `ml/explain.py` (template NLG from top contributing biomarkers), replace Day 3's placeholder explanation text; build `RecommendationPanel.tsx` | `backend/app/ml/explain.py`, `RecommendationPanel.tsx` | Real reasoning text shown next to recommended action | action_engine.py | Claude Code | P0 |
| 14:00–16:00 | Dev 2 | Package IsolationForest result as an optional secondary signal Dev 1 can call from `anomaly.py` (function signature agreed via `docs/api-contract.md` notes, not live-coupled) | `ml/isoforest_export.py` → hands function/logic to Dev 1 via PR | Reusable snippet Dev 1 can port into `backend/app/ml/anomaly.py` | isoforest_check.py | Cursor free | P1 |
| 16:00–18:00 | Dev 1 | Add `cases`, `audit_logs` tables; implement `POST /cases`, `POST /cases/{id}/decision`; build `DecisionPanel.tsx` (accept/reject/log) | `db/models.py` (additive), `routes/cases.py`, component | Investigator can log a decision on real data | action_engine.py | Claude Code | P0 |
| 16:00–18:00 | Dev 2 | Port IsolationForest snippet from earlier into `backend/app/ml/anomaly.py` alongside Dev 1 (pairing for 30 min if needed), then continue writing `docs/dataset-summary.md` into full documentation | `docs/data-methodology.md` | Documentation draft | — | — | P2 |
| 19:00–20:00 | Dev 1 | Deploy Day 4 changes, re-run the frozen MVP flow to confirm nothing broke, then test new recommendation + decision flow live | deployment | Updated public URL, both old and new flows work | all above | Claude Code | P0 |
| 20:00–21:00 | Both | Integration checkpoint — merge to `main`, tag `v0.4` | — | Clean state going into Day 5 | — | — | P0 |

---

## SECTION 8 — Day 5 (End-to-End Integration + Novelty Features)

**Goal:** full pipeline `DATA → DB → ML → ANOMALY/UNCERTAINTY → DECISION SUPPORT → API → FRONTEND → INVESTIGATOR` working, plus the adversarial simulation and budget allocator if on schedule.

| Time | Developer | Task | Files/Module | Output | Dependency | Tool | Priority |
|---|---|---|---|---|---|---|---|
| 09:00–11:00 | Dev 1 | Implement `ml/cusum.py` (cumulative sum detector), `GET /simulation/evasion` comparing single-sample vs. cumulative detection on the micro-dosing athletes | `backend/app/ml/cusum.py`, route | Endpoint returns before/after detection comparison data | anomaly.py, micro-dosing data | Claude Code | P1 |
| 09:00–11:00 | Dev 2 | Precompute `cohort_stats.json` (population mean/std per biomarker per sport) from frozen dataset | `ml/cohort_stats.py` | `data/cohort_stats.json` | frozen dataset | Cursor free | P1 |
| 11:00–13:00 | Dev 1 | Build `EvasionSim.tsx` (before/after chart), implement `ml/budget_allocator.py` (greedy knapsack) + `GET /recommendations/budget` | components, route | Evasion screen live, budget-ranked list endpoint works | cusum.py, action_engine.py | Claude Code | P1 |
| 11:00–13:00 | Dev 2 | Finalize documentation: `README.md` build/run instructions, `docs/data-methodology.md`, `docs/model-summary.md` (plain-English description of each model for judges) | docs | Complete, readable docs | — | — | P1 |
| 14:00–16:00 | Dev 1 | Build `AuditTimeline.tsx` + `GET /audit/{athlete_id}`, wire case/decision history into it | component, route | Full chronological view working | cases.py | Claude Code | P1 |
| 14:00–16:00 | Dev 2 | Run full QA pass on data: check no NaNs, check anomaly archetypes are still distinguishable after all pipeline changes, re-verify precision/recall numbers are still accurate against current code | `ml/evaluation.ipynb` (final run) | Final validated metrics for demo | all Dev1 ML changes merged | none | P0 |
| 16:00–18:00 | Dev 1 | Full backend + frontend redeploy, cold-start check on Render, fix any deploy-specific bugs (CORS, env vars) | deployment configs | Both apps stable on public URLs | everything above | Claude Code | P0 |
| 16:00–18:00 | Dev 2 | Write the exact test plan document Dev 1 will run on Day 6 morning (§18 tests, turned into a checklist) | `docs/test-plan.md` | Concrete checklist ready for Day 6 | — | — | P1 |
| 19:00–21:00 | Both | Full end-to-end walkthrough of every screen against the deployed URL, log every bug found into GitHub issues, do NOT fix yet — just log | GitHub issues | Prioritized bug list for Day 6 | all above | — | P0 |

**Integration checkpoint (end of Day 5):** entire pipeline works on the deployed URL, from dataset through decision support to investigator decision, including (if not cut) evasion simulation and budget allocator. Tag `v0.5-e2e`.

---

## SECTION 9 — Day 6 (Stabilize, Polish, Deploy, Present)

**No new features unless a P0 is broken.** Focus entirely on stability and presentation.

| Time | Developer | Task | Files/Module | Output | Dependency | Tool | Priority |
|---|---|---|---|---|---|---|---|
| 09:00–10:30 | Dev 1 | Fix Day 5 bug list in priority order (P0 first) | varies | Bug count near zero on P0/P1 items | Day 5 issue list | Claude Code | P0 |
| 09:00–10:30 | Dev 2 | Run `docs/test-plan.md` checklist against the live deployed URL, log new bugs found | test plan | Confirmed pass/fail list | Day 5 deploy | none | P0 |
| 10:30–12:00 | Dev 1 | UI polish: loading states, empty states (0-sample athlete), error toasts, consistent spacing/typography pass | frontend components | Visually consistent, no jarring blank states | bug fixes | Claude Code | P1 |
| 10:30–12:00 | Dev 2 | Finalize demo talking points doc: dataset stats, precision/recall numbers, one-liner per screen | `docs/demo-script.md` | Ready-to-read demo notes | evaluation results | none | P0 |
| 12:00–13:00 | Dev 1 | Add mock login screen (single hardcoded investigator) if time allows — this is a P2, skip if behind | `Login.tsx` | Optional polish item | — | Claude Code | P2 |
| **13:00** | Both | **CODE FREEZE** — no more feature or logic changes past this point, only critical-bug hotfixes | — | `main` locked | — | — | P0 |
| 14:00–15:30 | Both | Full rehearsal #1 of the 3-minute demo flow on the live deployed URL, timed | — | Timed run, notes on rough spots | code freeze | — | P0 |
| 15:30–16:30 | Dev 1 | Fix only what broke during rehearsal (critical path only) | — | Stable path re-confirmed | rehearsal notes | Claude Code | P0 |
| 16:30–17:30 | Both | Full rehearsal #2, record a backup demo video (screen recording) in case live/wifi fails during judging | — | Backup video saved | rehearsal #1 fixes | — | P0 |
| 17:30–18:30 | Both | Ping Render backend ~5 min before any judging slot from here on to avoid cold-start lag; finalize slides referencing `docs/demo-script.md` | slides | Presentation-ready deck | — | — | P0 |
| **18:30** | Both | **DEMO FREEZE** — nothing changes past this point except re-pinging the backend before you present | — | — | — | — | P0 |

---

## SECTION 10 — How to Use Claude Code (per stage)

Workflow every time: **Inspect → Plan → Implement one module → Run → Test → Review diff → Fix → Commit → Move to next module.** Never ask for the whole project at once; scope every prompt to one file or one tightly related pair.

**Initial scaffolding:**
> "Inspect the empty `/backend` folder. Plan and scaffold a FastAPI app with a `/health` endpoint returning `{status: ok}`, using SQLAlchemy for future DB use. Create `requirements.txt`. Do not create any route files beyond `/health` yet. Run it and confirm it boots before committing."

**Database:**
> "Inspect `docs/schema.md`. Implement SQLAlchemy models for `athletes` and `samples` only, exactly matching the field names and types in the doc — do not add extra fields. Create `backend/app/db/session.py` for the SQLite connection. Do not touch any route files. Run `create_all` and show me the resulting table structure before committing."

**Backend (CRUD):**
> "Inspect `backend/app/db/models.py` and `docs/api-contract.md`. Implement `GET /athletes` and `GET /athletes/{id}` in `backend/app/routes/athletes.py` exactly matching the contract's response shape. Do not modify `models.py`. Write a pytest for both, covering an empty DB case and a populated case. Run the tests, fix failures, show me the diff before committing."

**ML — baseline:**
> "Inspect `ml/prototype_baseline.py` (a validated standalone script). Port its Normal-Normal Bayesian update logic into `backend/app/ml/baseline.py` as a clean function `update_posterior(prior_mean, prior_var, obs, obs_var) -> (mean, var)`. Add a docstring with the math. Write 3 unit tests against hand-computed values from the prototype script. Do not modify any route or DB files."

**ML — anomaly / evidence engine:**
> "Inspect `backend/app/ml/baseline.py`. Implement Mahalanobis distance scoring in `backend/app/ml/anomaly.py` using each athlete's current posterior mean/covariance vs. their latest sample. Do not modify `baseline.py`. Write a unit test with a synthetic 2-biomarker case where the expected distance is known. Wire the result into `GET /athletes/{id}/anomalies` in `routes/athletes.py` only after the unit test passes."

**Decision-support engine:**
> "Inspect `backend/app/ml/anomaly.py` and `backend/app/ml/uncertainty.py`. Implement `ml/action_engine.py` with `compute_value_score(anomaly_score, uncertainty_score, test_sensitivity, cost) -> float` exactly as `Value Score = anomaly × uncertainty × sensitivity ÷ cost`. Do not change the anomaly or uncertainty modules. Add a unit test with 2 hand-computed cases."

**Frontend:**
> "Inspect `frontend/mock/trajectory.json` and the live `/athletes/{id}/trajectory` endpoint response shape in `docs/api-contract.md`. Implement `TrajectoryChart.tsx` using Recharts: observed points, baseline line, shaded confidence band from `ci_lower`/`ci_upper` fields. Do not modify any other component. Start with the mock JSON, then swap to the live fetch call only after visually confirming the mock renders correctly."

**Integration:**
> "Inspect `AthleteProfile.tsx`, currently using `mock/trajectory.json`. Replace the mock import with a real fetch to `/athletes/{id}/trajectory` using `api/client.ts`. Do not change the component's rendering logic, only the data source. Confirm it still renders correctly against a real athlete ID before committing."

**Testing:**
> "Inspect `backend/app/routes/*.py`. Write a pytest smoke test file `tests/test_api_smoke.py` that hits every endpoint in `docs/api-contract.md` against the seeded test DB and asserts a 200 status and expected top-level JSON keys. Do not modify route logic, only add tests."

**Debugging:**
> "Here is the error: [paste]. Inspect only the file(s) in the traceback. Do not modify unrelated files. Explain the root cause before fixing it, then show the diff."

**Deployment:**
> "Inspect `backend/requirements.txt` and `main.py`. Create a `render.yaml` (or Render web-service config) for deploying this FastAPI app, including the `PORT` env var Render expects. Do not modify application code, only add deployment config."

---

## SECTION 11 — Developer 2 Workflow

Independent, file-handoff based — never requires access to Dev 1's live app.

**Task: Synthetic Data Generator**
- INPUT: config dict (n_athletes, n_sports, anomaly_rate, seed) — no external input.
- WORK: correlated random-walk per biomarker, per-sport population priors, inject 3 anomaly archetypes.
- OUTPUT: `data/athletes.json`, `data/samples.json`, `data/ground_truth.json` (hidden), matching `docs/schema.md` exactly.
- INTEGRATION: Dev 1's `db/seed.py` reads these files directly at DB-seed time. Hand off via PR to `/data`; Dev 1 re-runs seed script whenever a new version lands.

**Task: Bayesian Baseline Prototype**
- INPUT: `data/samples.json`.
- WORK: hand-validate the Normal-Normal conjugate update math in a standalone script, prove convergence.
- OUTPUT: `ml/prototype_baseline.py`, printed/plotted proof.
- INTEGRATION: Dev 1 ports the validated function into `backend/app/ml/baseline.py` (copy-paste + unit test, not a live import).

**Task: IsolationForest Secondary Check**
- INPUT: `data/samples.json`.
- WORK: train/score IsolationForest as a standalone comparison against Mahalanobis-only flags.
- OUTPUT: `ml/isoforest_check.py` + comparison notes.
- INTEGRATION: Dev 1 ports the scoring function into `backend/app/ml/anomaly.py` as a secondary signal.

**Task: Evaluation / Validation**
- INPUT: `data/ground_truth.json` (hidden) + live anomaly scores exported from Dev 1's DB (Dev 1 exports a CSV on request).
- WORK: compute precision/recall/false-positive rate of the detector against known injected anomalies.
- OUTPUT: `ml/evaluation.ipynb` with a metrics table.
- INTEGRATION: numbers go into `docs/demo-script.md`, not into the running app.

**Task: Cohort Stats**
- INPUT: `data/samples.json`.
- WORK: compute population mean/std per biomarker per sport.
- OUTPUT: `data/cohort_stats.json`.
- INTEGRATION: Dev 1 loads this file directly for the (P2) cohort comparison view.

**Task: Documentation**
- INPUT: everything above.
- WORK: write methodology, model summary, demo script.
- OUTPUT: `docs/*.md`.
- INTEGRATION: read directly by the team for presentation; no code integration needed.

---

## SECTION 12 — Mock → Real Transition

| Component | Mock version (Day 1–2) | Real version (from) | Replacement trigger |
|---|---|---|---|
| Athlete list | `frontend/mock/athletes.json` | `GET /athletes` DB-backed | End of Day 2, once seed script + endpoint exist |
| Trajectory | `frontend/mock/trajectory.json` | `GET /athletes/{id}/trajectory` with real baseline | Day 3, once `baseline.py` is ported and endpoint returns real CI |
| Anomaly score | Hardcoded placeholder number in mock JSON | Mahalanobis-based `/athletes/{id}/anomalies` | Day 3 |
| Explanation text | One static sentence per mock athlete | `ml/explain.py` template NLG | Day 4 |
| Recommendation | Not present in mock at all | `ml/action_engine.py` + `/recommendation` | Day 4 |
| Uncertainty | Flat placeholder value | `ml/uncertainty.py` posterior variance | Day 4 |
| Cases/decisions | Not present in mock | `POST /cases`, `/decision`, real DB | Day 4 |
| Evasion simulation | Not present in mock | `ml/cusum.py` + `/simulation/evasion` | Day 5 |
| Budget allocator | Not present in mock | `ml/budget_allocator.py` + `/recommendations/budget` | Day 5 |
| Dataset | 10 fake athletes, 1 biomarker | 80 athletes, 5 biomarkers, 3 anomaly archetypes | Fully real by Day 3 (frozen at MVP), only bugfixed after |

Rule: a screen is allowed to consume mock JSON for at most one day past when its backing endpoint is scheduled — if the endpoint is late, the screen stays on mock rather than blocking, and gets swapped the moment the endpoint lands.

---

## SECTION 13 — ML Implementation Order

| Step | Model/Algorithm | Input | Output | File | Test method | Integration point |
|---|---|---|---|---|---|---|
| 1 | Data generation | config | `athletes.json`, `samples.json` | `ml/generate_data.py` | Visual plot check + schema validation | `db/seed.py` reads it |
| 2 | Dataset validation | generated data | pass/fail checks (no NaNs, ranges sane) | `ml/evaluation.ipynb` (early cells) | Assert statements | Gate before Day 2 seeding |
| 3 | Bayesian baseline (Normal-Normal) | per-athlete sample series | posterior mean + variance per biomarker | `backend/app/ml/baseline.py` | Unit test vs. hand-computed values | `/athletes/{id}/trajectory` |
| 4 | Mahalanobis anomaly scoring | posterior + latest sample | anomaly score, contributing biomarkers | `backend/app/ml/anomaly.py` | Unit test with known-distance synthetic case | `/athletes/{id}/anomalies` |
| 5 | IsolationForest (secondary) | full sample matrix | secondary flag/score | `backend/app/ml/anomaly.py` (ported from Dev 2) | Compare against Mahalanobis on frozen dataset | Combined into anomaly score |
| 6 | Uncertainty scoring | posterior variance | normalized 0–1 uncertainty | `backend/app/ml/uncertainty.py` | Unit test: known variance → known score | `/athletes/{id}/trajectory` (CI band), recommendation |
| 7 | Value Score / action engine | anomaly, uncertainty, cost table | ranked recommended action | `backend/app/ml/action_engine.py` | Unit test: 2 hand-computed cases | `/athletes/{id}/recommendation` |
| 8 | Explanation NLG | top contributing biomarkers | plain-English text | `backend/app/ml/explain.py` | Manual read-through for coherence on 5 cases | Attached to recommendation response |
| 9 | CUSUM cumulative detector | micro-dosing sample series | cumulative vs. single-sample detection comparison | `backend/app/ml/cusum.py` | Unit test on a known synthetic drift | `/simulation/evasion` |
| 10 | Budget allocator (greedy) | list of Value Scores, budget N | ranked, budget-constrained action list | `backend/app/ml/budget_allocator.py` | Unit test: known small list, known optimal ranking | `/recommendations/budget` |
| 11 | Evaluation | detector outputs vs. hidden ground truth | precision/recall/FPR | `ml/evaluation.ipynb` | Standard sklearn metrics | Demo script numbers only, not the live app |

---

## SECTION 14 — Database Implementation

1. **Create database:** SQLite file, created on first `session.py` import (Day 1).
2. **Create tables:** `athletes`, `samples` first (Day 1–2); `anomalies`, `recommendations` (Day 3); `cases`, `audit_logs`, `evidence` (Day 4); `cohort_stats`, `ground_truth` (Day 5, ground_truth is write-once from Dev 2's file, never read by the API).
3. **Insert seed data:** `db/seed.py` reads `/data/*.json`, run manually whenever Dev 2 hands off a new dataset version; re-run automatically on backend startup for deploy reproducibility (Render's disk is ephemeral, so startup seeding is required, not optional).
4. **Create relationships:** foreign keys `samples.athlete_id → athletes.id`, `anomalies.athlete_id/sample_id`, `cases.athlete_id`, `audit_logs.case_id`.
5. **Indexes:** add index on `samples.athlete_id`, `anomalies.athlete_id` once the dataset is at full 80-athlete scale (Day 3) — not needed before, adds no value on 10 fake rows.
6. **Connect backend:** SQLAlchemy session dependency injected into every route (Day 1–2).
7. **CRUD:** athlete read (Day 2), sample write / case create/update (Day 4).
8. **Analytics queries:** "latest anomaly per athlete" join for the priority-sorted dashboard (Day 3).
9. **API integration:** every table above maps 1:1 to the corresponding endpoint(s) in §15 below.

**MVP database (Day 3):** `athletes`, `samples`, `anomalies`, `recommendations`.
**Final database (Day 5):** adds `cases`, `audit_logs`, `evidence`, `cohort_stats`.

---

## SECTION 15 — API Implementation Order

| Order | Method | Endpoint | Purpose | Implementation file | Frontend consumer | Test | Day |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/health` | Boot check | `main.py` | — | curl | 1 |
| 2 | GET | `/athletes` | Priority-sorted list | `routes/athletes.py` | `Dashboard.tsx` | pytest + curl | 2 |
| 3 | GET | `/athletes/{id}` | Profile detail | `routes/athletes.py` | `AthleteProfile.tsx` | pytest + curl | 2 |
| 4 | GET | `/athletes/{id}/trajectory` | Baseline vs observed + CI | `routes/athletes.py` | `TrajectoryChart.tsx` | pytest + curl | 2–3 |
| 5 | GET | `/athletes/{id}/anomalies` | Anomaly score + drivers | `routes/athletes.py` | `ExplanationPanel.tsx` | pytest + curl | 3 |
| 6 | GET | `/athletes/{id}/recommendation` | Recommended action + reasoning | `routes/recommendations.py` | `RecommendationPanel.tsx` | pytest + curl | 4 |
| 7 | POST | `/athletes/{id}/samples` | Add new sample, trigger re-scoring | `routes/athletes.py` | (admin/testing use) | pytest | 4 |
| 8 | POST | `/cases` | Open investigation case | `routes/cases.py` | `DecisionPanel.tsx` | pytest + curl | 4 |
| 9 | POST | `/cases/{id}/decision` | Log investigator decision | `routes/cases.py` | `DecisionPanel.tsx` | pytest + curl | 4 |
| 10 | GET | `/audit/{athlete_id}` | Full timeline | `routes/cases.py` | `AuditTimeline.tsx` | pytest + curl | 5 |
| 11 | GET | `/simulation/evasion` | Micro-dosing detection comparison | `routes/simulation.py` | `EvasionSim.tsx` | pytest + curl | 5 |
| 12 | GET | `/recommendations/budget` | Budget-constrained ranking | `routes/recommendations.py` | (P2 view or dashboard widget) | pytest + curl | 5 |

**Mocked first (Day 1), replaced per §12:** every GET endpoint above has a corresponding static fixture in `frontend/mock/` created before the real backend exists, so frontend work is never blocked.

---

## SECTION 16 — Frontend Implementation Order

| Screen | 1. Create page | 2. Components | 3. Mock data | 4. Style | 5. Real API | 6. Test | Needed by |
|---|---|---|---|---|---|---|---|
| Dashboard | Day 1 | list item component | Day 1 | Day 2 | Day 2 | Day 3 | Day 3 (MVP) |
| Athlete Profile | Day 1 | header component | Day 1 | Day 2–3 | Day 2 | Day 3 | Day 3 (MVP) |
| Trajectory chart | Day 2 | `TrajectoryChart.tsx` | Day 2 | Day 3 | Day 3 | Day 3 | Day 3 (MVP) |
| Anomaly/Explanation panel | Day 3 | `ExplanationPanel.tsx` | Day 3 | Day 3 | Day 3–4 | Day 4 | Day 3 (basic), Day 4 (real NLG) |
| Recommendation panel | Day 4 | `RecommendationPanel.tsx` | — (built real from start) | Day 4 | Day 4 | Day 4 | Day 4 |
| Decision panel | Day 4 | `DecisionPanel.tsx` | — | Day 4 | Day 4 | Day 4 | Day 4 |
| Audit timeline | Day 5 | `AuditTimeline.tsx` | — | Day 5 | Day 5 | Day 5 | Day 5 (can wait) |
| Evasion simulation | Day 5 | `EvasionSim.tsx` | — | Day 5 | Day 5 | Day 5 | Day 5 (can wait) |
| Cohort view | Day 6 (if time) | `CohortView.tsx` | — | Day 6 | Day 6 | Day 6 | Optional |
| Login | Day 6 (if time) | `Login.tsx` | — | Day 6 | mock session only | Day 6 | Optional |

---

## SECTION 17 — Integration Checkpoints

**Checkpoint 1 — End Day 1:** Must work: both apps boot locally and deployed (blank), DB schema exists empty, contract docs committed. Can still be broken: everything downstream. Must be committed: `main` with scaffolds. Must be tested: `/health` curl, blank Vercel URL loads.

**Checkpoint 2 — End Day 2:** Must work: `/athletes` and `/athletes/{id}` return real seeded data, Dashboard renders it. Can still be broken: trajectory chart styling, ML accuracy. Must be committed: tag `v0.2-vertical-slice`. Must be tested: pytest on both endpoints, manual click-through of Dashboard.

**Checkpoint 3 — End Day 3 (MVP):** Must work: full Dashboard → Profile → Trajectory → Anomaly flow, deployed, on frozen dataset. Can still be broken: recommendation, cases, audit, simulation (not built yet). Must be committed: tag `v0.3-mvp-freeze`. Must be tested: full manual walkthrough twice on the live URL.

**Checkpoint 4 — End Day 4:** Must work: recommendation + explanation + case/decision logging, all real, on top of the untouched frozen MVP flow. Can still be broken: CUSUM/evasion, budget allocator, cohort view. Must be committed: tag `v0.4`. Must be tested: pytest on new endpoints + manual re-check of the Day 3 flow still works.

**Checkpoint 5 — End Day 5:** Must work: entire pipeline including evasion simulation and budget allocator (if not cut), deployed and stable. Can still be broken: nothing load-bearing — only cosmetic issues should remain. Must be committed: tag `v0.5-e2e`. Must be tested: full `docs/test-plan.md` checklist run against the live deployed URL.

---

## SECTION 18 — Testing (run continuously, not on Day 6)

- **Day 1–2, data tests:** schema validation on every `generate_data.py` run (field presence, no NaNs, value ranges sane).
- **Day 2–3, ML sanity tests:** unit tests for `baseline.py` (hand-computed posterior updates), `anomaly.py` (known-distance synthetic case) — written the same day the module is built, not after.
- **Day 2–5, backend/API tests:** pytest per endpoint the day it's implemented; `tests/test_api_smoke.py` curl-style pass over the full contract, run at every integration checkpoint.
- **Day 3–6, frontend tests:** manual QA checklist per screen — empty athlete (0 samples), single-sample athlete, full-history athlete, error state (backend down).
- **Day 4–5, decision-engine tests:** `action_engine.py` unit tests with hand-computed Value Scores; `evaluation.ipynb` precision/recall against hidden ground truth.
- **Day 5, integration tests:** full pipeline run on deployed URLs, not localhost.
- **Day 6 morning, end-to-end:** `docs/test-plan.md` checklist executed top to bottom on the live URL by Dev 2 (fresh eyes), bugs logged and triaged before code freeze.

---

## SECTION 19 — Deployment

- **First deployment (Day 1):** blank Vite app → Vercel; blank FastAPI `/health` → Render. Purpose: catch platform-specific config issues (env vars, CORS, build settings) while there's nothing to lose.
- **Staging/demo deployment (Day 2 onward):** every merge to `main` redeploys automatically (Vercel auto-deploys on push; configure Render auto-deploy from `main` too) — the deployed URL is always close to current `main`, never a Day 6 surprise.
- **Final deployment (Day 5–6):** freeze deploy config, verify env vars (`DATABASE_URL` if using Supabase fallback, CORS origins matching the final Vercel URL), confirm startup DB seeding runs correctly on a fresh Render instance (simulate a cold deploy once on Day 5 to catch ephemeral-disk issues early).
- **Day 6:** no config changes after code freeze except pinging the backend before each judging slot to avoid cold-start lag.

---

## SECTION 20 — Backup Strategy

| Component | Failure | Fallback |
|---|---|---|
| Bayesian baseline / Mahalanobis | ML underperforms or produces nonsensical scores | Fall back to a simple z-score-from-population-mean threshold — still produces a defensible number, just less personalized |
| CUSUM / evasion sim | Runs out of time or looks unconvincing | Cut per the feature-cutting order — core MVP stands alone without it |
| Budget allocator | Runs out of time | Show per-athlete recommendations only, drop cross-athlete ranking |
| Render backend | Cold start or outage during judging | Local backend running on presenter's laptop + ngrok tunnel, pre-tested Day 5 |
| SQLite persistence | Render ephemeral disk wipes data on redeploy | Startup seeding from committed `/data/*.json` makes this a non-issue — data is always reproducible, not "lost" |
| Vercel frontend | Outage | Backup demo video recorded Day 6, playable offline |
| Live demo generally | Any live failure | Backup screen-recorded video is the ultimate fallback — always have it ready before presenting |
| Dev 2 blocked (free AI tools insufficient) | Complex generator logic stalls | Dev 1 pairs for 30–60 min (already scheduled as a buffer on Day 4); statistics code is often faster hand-written than AI-prompted anyway |

---

## SECTION 21 — Final Master Checklist

**DAY 1 DONE**
- [ ] Repo created, folder structure in place
- [ ] `README.md`, `CLAUDE.md`, `.env.example` committed
- [ ] Backend `/health` boots locally and on Render
- [ ] Frontend boots locally and on Vercel (blank)
- [ ] `docs/api-contract.md`, `docs/schema.md` written and agreed
- [ ] `athletes`, `samples` tables created (empty)
- [ ] Dev 2 generator v0.5 producing a plausible single-biomarker series

**DAY 2 DONE**
- [ ] Full 5-biomarker, 80-athlete, no-anomaly dataset generated
- [ ] `db/seed.py` working
- [ ] `GET /athletes`, `GET /athletes/{id}` live, DB-backed
- [ ] Dashboard shows real seeded athletes
- [ ] Bayesian baseline math prototyped and validated
- [ ] `/athletes/{id}/trajectory` returns basic baseline vs. observed

**DAY 3 MVP DONE**
- [ ] All 3 anomaly archetypes injected into final frozen dataset
- [ ] Mahalanobis anomaly scoring live via `/athletes/{id}/anomalies`
- [ ] Trajectory chart with confidence band rendering real data
- [ ] Dashboard priority-sorted by anomaly score
- [ ] Basic explanation text shown per flagged athlete
- [ ] Full flow deployed and smoke-tested twice
- [ ] MVP tagged (`v0.3-mvp-freeze`) and frozen per §6

**DAY 4 DONE**
- [ ] Uncertainty scoring live, real CI band on trajectory chart
- [ ] Precision/recall computed against hidden ground truth
- [ ] Value Score action engine + `/recommendation` endpoint live
- [ ] Real explanation NLG replacing Day 3 placeholder
- [ ] `cases`/`audit_logs` tables + decision logging working
- [ ] Day 3 MVP flow re-verified unbroken

**DAY 5 DONE**
- [ ] CUSUM + evasion simulation live (or explicitly cut per §24 of prior spec)
- [ ] Budget allocator live (or explicitly cut)
- [ ] Audit timeline screen working
- [ ] Cohort stats file generated
- [ ] Full pipeline tested end-to-end on deployed URLs
- [ ] All bugs logged to GitHub issues, triaged

**DAY 6 DONE**
- [ ] P0/P1 bugs from Day 5 fixed
- [ ] UI polish pass complete (loading/empty/error states)
- [ ] Code freeze executed at scheduled time
- [ ] Two full rehearsals completed
- [ ] Backup demo video recorded

**DEPLOYMENT DONE**
- [ ] Frontend stable on Vercel
- [ ] Backend stable on Render, cold-start mitigated
- [ ] Fresh-deploy DB seeding verified working

**DEMO DONE**
- [ ] Demo script finalized (`docs/demo-script.md`)
- [ ] Slides finalized
- [ ] Backend pinged before judging slot
- [ ] Backup video ready as fallback
