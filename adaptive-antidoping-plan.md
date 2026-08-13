# Adaptive Anti-Doping Defense Engine — 6-Day Execution Plan
### SIH260423 — Intelligence & Investigations: Enhancing Anti-Doping Efforts

---

## 0. Critical evaluation of your original concept (read this first)

Your 8-point idea is fundamentally sound and, unusually for a hackathon pitch, already matches how the **real** WADA Athlete Biological Passport (ABP) actually works: individualized Bayesian reference ranges, not population thresholds. That's good — it gives you a legitimate technical story ("we're not inventing anomaly detection, we're building the *decision layer* the ABP program is missing"). I'm keeping the core shape but making three changes:

1. **Cutting the "social media / financial / travel records" data-source idea from the official problem statement.** It's ethically and legally radioactive (surveillance of private individuals), impossible to source for free/legally in 6 days, and adds zero technical credibility. I'm replacing it with synthetic *contextual* data that's actually defensible: competition calendar, altitude-training flags, injury/TUE (therapeutic use exemption) flags, and testing history gaps. Say this explicitly in your demo — judges will respect the ethical reasoning more than the feature.
2. **Replacing "information gain" with a named, defensible heuristic**, not a hand-wavy phrase. True Bayesian expected information gain requires a generative model of test outcomes you don't have time to build. Instead: **Value Score = Anomaly Severity × Current Uncertainty × Test Sensitivity ÷ Test Cost**, which is a standard value-of-information *approximation* used in real decision-support systems. This is honest, explainable in 30 seconds to a judge, and still lets you say "expected value of the next action" truthfully.
3. **Keeping the adversarial simulation but making it small and concrete**: a micro-dosing evader that stays under single-sample thresholds, caught (or not) by a cumulative/sequential detector (CUSUM). This is the single highest-novelty, lowest-cost feature you can add — it turns "we built a detector" into "we stress-tested our own detector," which is a genuinely research-grade move.

Everything below assumes these three changes.

---

## 1. Executive Decision — What We Should Build

**Build:** A per-athlete adaptive monitoring system that (a) maintains a personalized Bayesian baseline for a small set of real ABP-style biomarkers, (b) flags statistically meaningful deviations from that baseline, (c) quantifies how *confident* it is in the athlete's current state, (d) recommends the single most valuable next investigative action under a resource constraint, and (e) explains its reasoning in plain language to a human investigator who makes the final call.

**Not** a doping-detection dashboard. **Not** an LLM chatbot wrapper. **Not** a real ADAMS integration. It is a decision-support prototype over synthetic ABP-style longitudinal data.

---

## 2. Final Feature Set

| # | Feature | Purpose | User Value | Technical Implementation | Novelty | Difficulty | Day | Priority |
|---|---|---|---|---|---|---|---|---|
| 1 | Synthetic ABP dataset generator | Ground the whole system in realistic data | Enables every downstream feature | Python/numpy correlated random-walk per biomarker + injected anomaly patterns | Low (infra) | Medium | 1–2 | P0 |
| 2 | Individual Bayesian baseline model | Personalized "expected" trajectory per athlete | Distinguishes normal individual variation from real deviation | Conjugate Normal-Normal Bayesian update per biomarker, recomputed on each new sample | **High** — this is the ABP's real method, few hackathon teams implement it | Medium | 2–3 | P0 |
| 3 | Anomaly detection (personal + cohort) | Detect unexplained deviation | Core flagging mechanism | Mahalanobis distance from personal posterior + IsolationForest across cohort as secondary signal | Medium | Medium | 3 | P0 |
| 4 | Uncertainty quantification | Avoid false accusation, show confidence | Investigators see *how sure* the system is, not just a score | Posterior variance → confidence interval width → normalized uncertainty score | **High** — almost no hackathon team scores uncertainty separately from risk | Low–Medium | 3 | P0 |
| 5 | Adaptive next-action recommender | Turns detection into an actionable decision | Answers "what do we do now, given limited testing budget?" | Value Score = anomaly × uncertainty × test-sensitivity ÷ cost, ranked greedy allocation | **High** — main differentiator | Medium | 4 | P0 |
| 6 | Plain-language explanation layer | Trust, auditability, human-in-the-loop | Investigator understands *why*, not just *what* | Template-based NLG from feature contributions (no LLM needed — deterministic, explainable, free) | Medium | Low–Medium | 3–4 | P0 |
| 7 | Investigator dashboard (list, profile, trajectory, action, decision) | The demo surface | Lets a human see, question, and act | React + Recharts + FastAPI | Medium (execution matters more than idea) | Medium | 3–5 | P0 |
| 8 | Case log / audit trail | Accountability, human-in-the-loop proof | Shows the system doesn't auto-accuse | Append-only `audit_logs` table, timestamped investigator actions | Low | Low | 4 | P0 |
| 9 | Micro-dosing adversarial simulation + CUSUM cumulative detector | Stress-tests your own system | Shows research maturity | Inject sub-threshold drift over N samples; compare single-sample vs. cumulative detection | **Very High** for a hackathon | Medium | 5 | P1 |
| 10 | Resource-constrained test allocation | Realism — testing budgets are finite in real life | Shows systems thinking, not just ML | Greedy knapsack over Value Scores vs. a fixed weekly "test budget" | Medium–High | Low–Medium | 5 | P1 |
| 11 | Evidence timeline view | Investigation usability | Chronological view of samples/tests/actions/decisions | Simple merged timeline component | Low | Low | 5 | P1 |
| 12 | Cohort/relationship comparison view | "Is this athlete unusual even for their sport?" | Extra context for edge cases | Scatter/box-plot of athlete vs. sport-cohort distribution | Low–Medium | Low | 6 | P2 |
| 13 | Mock login (single hardcoded investigator) | Demo completeness | Looks finished | Local session, no real auth needed | Low | Very Low | 6 | P2 |
| 14 | Real WADA/ADAMS integration | — | — | Requires confidential access we don't have | — | — | — | **P3 — do not build** |
| 15 | Social media / financial / travel scraping | — | — | Ethically & legally out of scope, not free, not feasible | — | — | — | **P3 — do not build** |
| 16 | Deep learning models | — | — | Unjustifiable on CPU/6 days/tabular data this size | — | — | — | **P3 — do not build** |
| 17 | Multi-tenant real authentication | — | — | Zero demo value for the time cost | — | — | — | **P3 — do not build** |

---

## 3. What Makes It Novel

- **Personalized Bayesian baselines**, not population thresholds — mirrors the actual ABP methodology, which almost no hackathon team implements correctly.
- **A separate, visible uncertainty score** — most "AI risk score" projects collapse confidence and risk into one number. You keep them apart, which is the difference between "accusation engine" and "decision-support engine."
- **A resource-constrained recommender**, not just a classifier — real anti-doping agencies have limited testing budgets; you model that constraint explicitly.
- **Self-adversarial testing** — you show your own detector's blind spot (micro-dosing) and how a cumulative detector partially closes it. This is the single most "we did research, not a CRUD app" feature you can show a judge.
- **Explicit ethical scoping** — you removed the surveillance-adjacent data sources from the official brief and can defend why, in front of judges who will ask.

---

## 4. Final ₹0 Tech Stack

| Component | Technology | Purpose | Free/OSS? | Paid dependency? | Free-tier limitation | Backup |
|---|---|---|---|---|---|---|
| Frontend framework | Vite + React + TypeScript | UI | Yes, OSS | None | — | Plain CRA if Vite issues |
| Styling | Tailwind CSS | Fast, consistent UI | Yes, OSS | None | — | — |
| Charts | Recharts | Trajectory/uncertainty visualization | Yes, OSS | None | — | Chart.js |
| Frontend hosting | Vercel (free tier) | Deploy frontend | Yes | None | Fair-use limits, irrelevant at hackathon scale | GitHub Pages |
| Backend | FastAPI + Uvicorn (Python) | API, model serving | Yes, OSS | None | — | Flask |
| Backend hosting | Render (free web service) | Deploy backend | Yes | None | Cold start after inactivity — mitigate by pinging before demo | Fly.io free tier / local + ngrok as day-of backup |
| Database | SQLite (file-based) | Store athletes/samples/cases | Yes, OSS | None | Ephemeral disk on Render free tier — mitigate: seed at startup from JSON/CSV, treat as reproducible | Supabase free Postgres if persistence across restarts is needed |
| ML | NumPy, SciPy, pandas, scikit-learn (IsolationForest) | Baseline model, anomaly detection, CUSUM | Yes, OSS | None | — | — |
| Auth | Hardcoded single investigator session | Demo completeness | Yes | None | Not real security (fine — it's a prototype) | — |
| Version control | GitHub | Collaboration | Yes | None | — | — |
| AI coding (Person 1 & 2) | Claude Code | Accelerate dev | Already available to you | None for this stack | — | — |
| AI coding (Person 3) | Cursor free tier / free models | Accelerate dev | Yes | None | Lower quality completions — mitigate with tighter prompts | Plain VS Code + manual coding |
| Testing | pytest, manual QA checklist, curl/Postman | Verify correctness | Yes, OSS | None | — | — |

**Final stack, one line each:**
Frontend: Vite+React+TS+Tailwind+Recharts, on Vercel.
Backend: FastAPI on Render.
Database: SQLite, seeded from synthetic data at startup.
ML: scikit-learn IsolationForest + custom Bayesian/CUSUM code in NumPy/SciPy.
Analytics: Mahalanobis distance, posterior variance, greedy value-of-information ranking.
Visualization: Recharts trajectory + confidence-band charts.
Data: fully synthetic, generated by Person 3.
Auth: single mock investigator login.
Hosting: Vercel + Render, both free.
Testing: pytest + manual checklist.
AI coding: Claude Code (Person 1/2), Cursor free tier (Person 3).

---

## 5. ML/AI Model Selection

**MUST-HAVE:**
- **Personal Bayesian baseline** — conjugate Normal-Normal update per biomarker per athlete. Prior = population mean/variance for that biomarker; posterior updates with each new sample. Gives you both a prediction (expected value) and uncertainty (posterior variance) for free — this single model powers features 2, 3, and 4.
- **Mahalanobis distance** from the personal posterior for multivariate deviation scoring (accounts for correlated biomarkers, e.g., Hb and reticulocytes move together).
- **IsolationForest** (scikit-learn) trained on the synthetic cohort as a secondary, population-level sanity check — catches things a purely personal model might miss (e.g., a new athlete with too little history).

**OPTIONAL (Day 5, if on schedule):**
- **CUSUM (cumulative sum control chart)** for the adversarial simulation — detects small sustained drifts that single-sample z-scores miss. Simple, well-understood, explainable, and this is exactly what real ABP adaptive models use conceptually.

**FUTURE RESEARCH (say this explicitly in your report/demo, do not build):**
- True Bayesian sequential experimental design for information gain.
- Graph-based cohort/relationship modeling (coaches, labs, shared testing history).
- Learned (rather than heuristic) value-of-information scoring, trained on historical WADA case outcomes — you don't have this data and shouldn't pretend to.

No deep learning anywhere. You have ~60–100 synthetic athletes with ~20–40 samples each — that's a few thousand rows. A neural net would be undertrained, unexplainable, and indefensible under judge questioning. Say this out loud in your presentation; it signals maturity.

---

## 6. Data Strategy

Fully synthetic, generated by Person 3 in Python, no external dataset needed (no free dataset realistically matches ABP-style longitudinal biomarkers at the fidelity you need anyway).

**Scale:** 80 synthetic athletes, 6 sports (to support cohort comparison), 24 months of history, sampled irregularly (8–20 samples/athlete, matching real-world testing frequency) — roughly 1,200–1,500 total biomarker readings.

**Biomarkers** (real ABP parameters — this is your credibility anchor):
- Hemoglobin (Hb, g/dL)
- Hematocrit (HCT, %)
- Reticulocyte percentage (RET%)
- OFF-score (derived: Hb − 60×√RET%)
- Testosterone/Epitestosterone ratio (T/E ratio) — steroid module proxy

**Generation method:** per-athlete random walk with realistic physiological autocorrelation and noise, individual "true" baseline drawn from population distributions per sport. **~18% of athletes** get an injected anomaly pattern from one of three archetypes:
1. **Blood transfusion pattern** — sharp RET% suppression followed by rebound spike, Hb step-change.
2. **EPO micro-dosing** — small sustained upward drift in Hb/HCT below single-sample thresholds (this is your adversarial-simulation target).
3. **Steroid micro-dosing** — gradual T/E ratio drift with unexplained testing gaps.

**Contextual fields per sample:** competition flag, altitude-training flag, injury/TUE flag, days-since-last-test. These replace the removed social/financial/travel data — physiologically relevant, ethically clean, free.

**Tables:** see schema in section 8. Labels (`is_doped`, `pattern_type`) are stored **only** in a hidden ground-truth table used for your own evaluation/demo narration — the system itself never sees or uses these labels, and the dashboard must never expose them as a "confirmed doping" flag. This is an important integrity point: your system detects anomalies, not the label you injected to test it.

---

## 7. System Architecture

```
Synthetic Data Generator (Person 3, Python)
        ↓
Seed script → SQLite (athletes, samples, context, ground_truth[hidden])
        ↓
FastAPI Backend
   ├─ Ingestion/validation layer
   ├─ Bayesian Baseline Engine (per athlete, per biomarker)
   ├─ Anomaly Detector (Mahalanobis + IsolationForest)
   ├─ Uncertainty Module (posterior variance → CI)
   ├─ Adaptive Action Engine (Value Score + budget allocator)
   ├─ Explanation Generator (template NLG)
   └─ REST API (athletes, trajectory, recommendations, cases, audit)
        ↓
React Frontend (Vercel)
   ├─ Dashboard (priority-sorted athlete list)
   ├─ Athlete Profile (trajectory + confidence band chart)
   ├─ Anomaly & Explanation panel
   ├─ Recommended Action panel
   └─ Investigator decision + audit log view
```

---

## 8. Database Schema

**Day 3 tables (MVP):**
- `athletes(id, name, sport, age, baseline_prior_json)`
- `samples(id, athlete_id, date, hb, hct, ret_pct, off_score, te_ratio, competition_flag, altitude_flag, injury_flag)`
- `anomalies(id, athlete_id, sample_id, anomaly_score, mahalanobis_distance, method, created_at)`
- `recommendations(id, athlete_id, action_type, value_score, uncertainty_score, anomaly_score, cost, explanation_text, created_at)`

**Day 6 tables:**
- `cases(id, athlete_id, status, opened_at, closed_at, investigator_notes)`
- `audit_logs(id, case_id, athlete_id, actor, action, timestamp, details_json)`
- `evidence(id, case_id, sample_id, note, added_at)`

**Optional:**
- `cohort_stats(sport, biomarker, population_mean, population_std)` — precomputed for cohort comparison view.
- `ground_truth(athlete_id, is_synthetic_anomaly, pattern_type)` — hidden, used only for internal evaluation/demo narration, never exposed via API to the frontend dashboard.

---

## 9. API Contract

| Method | Endpoint | Input | Output | Owner | Day |
|---|---|---|---|---|---|
| GET | `/athletes` | query: sport?, sort=priority | list of athletes with latest anomaly/uncertainty score | Person 1 | 3 |
| GET | `/athletes/{id}` | — | profile + full sample history | Person 1 | 3 |
| GET | `/athletes/{id}/trajectory` | — | expected (baseline) vs. observed series + CI bands | Person 2 | 3 |
| GET | `/athletes/{id}/anomalies` | — | anomaly scores, contributing biomarkers | Person 2 | 3 |
| GET | `/athletes/{id}/recommendation` | — | recommended action, value score, explanation text | Person 2 | 4 |
| GET | `/recommendations/budget` | budget=N | ranked, budget-constrained list across all athletes | Person 2 | 5 |
| POST | `/athletes/{id}/samples` | new sample JSON | updated baseline + new anomaly score | Person 1 | 4 |
| POST | `/cases` | athlete_id, notes | created case | Person 1 | 4 |
| POST | `/cases/{id}/decision` | action, investigator | logged decision, audit entry | Person 1 | 4 |
| GET | `/audit/{athlete_id}` | — | full timeline of samples/anomalies/actions/decisions | Person 1 | 5 |
| GET | `/simulation/evasion` | pattern=micro_dosing | before/after CUSUM vs. single-sample detection comparison | Person 2 | 5 |

Frontend should be built against a **mock JSON version of this contract from Day 1** so Person 1/2 can work in parallel with the backend.

---

## 10. Frontend Screens

| Screen | Purpose | Data Required | Owner | Day | Priority |
|---|---|---|---|---|---|
| Dashboard | Priority-sorted athlete list | `/athletes` | Person 1 | 3 | P0 |
| Athlete Profile | Overview + latest state | `/athletes/{id}` | Person 1 | 3 | P0 |
| Trajectory View | Expected vs. observed + confidence band | `/athletes/{id}/trajectory` | Person 2 | 3 | P0 |
| Anomaly Explanation panel | Why flagged, which biomarkers | `/athletes/{id}/anomalies` | Person 2 | 3–4 | P0 |
| Recommended Action panel | Next action + reasoning | `/athletes/{id}/recommendation` | Person 2 | 4 | P0 |
| Investigator Decision controls | Accept/reject/log action | POST `/cases/{id}/decision` | Person 1 | 4 | P0 |
| Evidence/Audit Timeline | Full chronological history | `/audit/{athlete_id}` | Person 1 | 5 | P1 |
| Evasion Simulation view | Show detection blind-spot demo | `/simulation/evasion` | Person 2 | 5 | P1 |
| Cohort Comparison | Athlete vs. sport distribution | `cohort_stats` | Either | 6 | P2 |
| Login screen | Demo polish | mock session | Either | 6 | P2 |

---

## 11. 3-Person Responsibility Matrix (ownership overview)

- **Person 1 (Core Dev):** Backend CRUD, ingestion/validation, database, dashboard + profile + decision screens, deployment (backend + DB), GitHub repo admin.
- **Person 2 (Core Dev):** Bayesian baseline engine, anomaly detection, uncertainty module, adaptive action engine, trajectory/explanation/recommendation screens, evasion simulation.
- **Person 3 (Independent):** Synthetic data generator, ground-truth labeling, IsolationForest/CUSUM experiments and validation, cohort stats precomputation, exports data as clean JSON/CSV consumed by the backend at seed time, writes the evaluation notebook that proves the models work, documentation.

Person 1 and 2 work in the same repo but own **different backend modules** and **different frontend components**, so file conflicts are structurally rare (see GitHub section).

---

## 12–17. Day-by-Day Roadmap

| Day | Person | Task | Exact Deliverable | Tool | Dependency | Priority | Est. Time |
|---|---|---|---|---|---|---|---|
| 1 | P1 | Repo scaffold: `/frontend`, `/backend`, `/ml`, `/data`; FastAPI skeleton + SQLite connection | Running `GET /health` endpoint | Claude Code | None | P0 | 3h |
| 1 | P1 | Vite+React+Tailwind scaffold, routing shell | Blank routed app deployed to Vercel | Claude Code | None | P0 | 3h |
| 1 | P2 | Define finalized API contract as OpenAPI/JSON schema + mock JSON fixtures | `api-contract.md` + `mock/*.json` | Claude Code | None | P0 | 3h |
| 1 | P2 | Prototype Bayesian update math in a notebook (not yet wired to app) | `bayesian_baseline.ipynb` proving posterior update works on 1 fake biomarker series | Claude Code | None | P0 | 4h |
| 1 | P3 | Design synthetic data schema, write random-walk generator for 1 biomarker | `generate_samples.py` v0 | Cursor free | None | P0 | 5h |
| 1 | Team | Agree on schema + API contract, set up GitHub branches | Merged `main` with scaffolds | — | — | P0 | 1h |
| 2 | P1 | Implement `athletes`, `samples` tables + seed script from Person 3's JSON | DB seeded with real synthetic data | Claude Code | P3's generator | P0 | 4h |
| 2 | P1 | `GET /athletes`, `GET /athletes/{id}` endpoints | Working, tested endpoints | Claude Code | schema | P0 | 3h |
| 2 | P2 | Port Bayesian baseline notebook into `ml/baseline.py` module (per-biomarker, per-athlete) | Importable, unit-testable module | Claude Code | notebook | P0 | 5h |
| 2 | P2 | Mahalanobis anomaly scoring on top of baseline | `ml/anomaly.py` | Claude Code | baseline.py | P0 | 3h |
| 2 | P3 | Extend generator to all 5 biomarkers with realistic correlation; inject blood-transfusion pattern for 6% of athletes | Full `athletes.json` + `samples.json`, 80 athletes | Cursor free | v0 generator | P0 | 6h |
| 2 | Team | Integration checkpoint: backend serves real DB-backed athlete list to frontend mock | Confirmed data flowing end to end (mock frontend, real backend data) | — | — | P0 | 1h |
| 3 | P1 | Dashboard screen (priority-sorted list) + Athlete Profile screen, wired to real API | `Dashboard.tsx`, `AthleteProfile.tsx` | Claude Code | `/athletes` endpoints | P0 | 5h |
| 3 | P2 | `GET /athletes/{id}/trajectory`, `/anomalies` endpoints + Trajectory chart component with confidence band | `TrajectoryChart.tsx`, working endpoints | Claude Code | anomaly.py | P0 | 5h |
| 3 | P3 | Inject EPO micro-dosing (12%) and steroid micro-dosing patterns into generator; add contextual fields (competition/altitude/injury flags) | Final v1 dataset with 3 anomaly archetypes | Cursor free | — | P0 | 5h |
| 3 | Team | **DAY 3 MVP CHECKPOINT** — full flow: dashboard → athlete → trajectory → anomaly, on real data, deployed | Live demoable MVP (see §14) | — | all above | **P0** | 2h |
| 4 | P1 | `POST /athletes/{id}/samples`, `POST /cases`, `POST /cases/{id}/decision`; investigator decision UI | Working case creation + decision logging | Claude Code | Day 3 backend | P0 | 6h |
| 4 | P2 | Uncertainty module (posterior variance → normalized score) + Adaptive Action Engine (Value Score formula) + `/recommendation` endpoint | `ml/uncertainty.py`, `ml/action_engine.py`, endpoint | Claude Code | baseline.py | P0 | 6h |
| 4 | P2 | Explanation Generator (template NLG from top contributing biomarkers) | `ml/explain.py` | Claude Code | anomaly.py | P0 | 3h |
| 4 | P3 | Validation notebook: run IsolationForest + baseline model against hidden ground truth, report precision/recall on injected anomalies | `evaluation.ipynb` with metrics table | Cursor free | v1 dataset | P0 | 5h |
| 4 | Team | Integration: recommendation + explanation flowing to frontend | Recommendation panel showing real reasoning text | — | — | P0 | 1h |
| 5 | P1 | Evidence/Audit Timeline screen + `GET /audit/{athlete_id}` | `AuditTimeline.tsx` + endpoint | Claude Code | cases table | P1 | 4h |
| 5 | P2 | CUSUM cumulative detector + `/simulation/evasion` endpoint + Evasion Simulation screen (before/after comparison chart) | `ml/cusum.py`, endpoint, `EvasionSim.tsx` | Claude Code | micro-dosing data | P1 | 6h |
| 5 | P2 | Resource-constrained budget allocator (`/recommendations/budget`) | Greedy allocator + endpoint | Claude Code | action_engine.py | P1 | 3h |
| 5 | P3 | Cohort stats precomputation + finalize evaluation report; write documentation/README | `cohort_stats.json`, `README.md`, final report | Cursor free | v1 dataset | P1 | 5h |
| 5 | Team | Full backend + frontend deployment (Render + Vercel), smoke test all endpoints | Publicly reachable demo URL | — | — | P0 | 2h |
| 6 | P1 | UI polish (loading states, error handling, empty states), mock login screen | Polished dashboard | Claude Code | — | P2 | 4h |
| 6 | P2 | Cohort comparison view; bug fixes from Day 5 integration | `CohortView.tsx` | Claude Code | cohort_stats | P2 | 4h |
| 6 | P3 | Final QA pass against test plan (§21), prep demo talking points on evaluation metrics | QA checklist signed off | — | — | P0 | 3h |
| 6 | Team | Full end-to-end rehearsal, record backup demo video, finalize slides | Rehearsed 3-min demo + backup video | — | — | **P0** | 3h |

---

## 18. Claude Code Workflow (Person 1 & 2)

Each task follows **Inspect → Plan → Implement → Test → Debug → Verify → Commit**. Directory ownership:
- **Person 1 owns:** `backend/app/routes/athletes.py`, `backend/app/routes/cases.py`, `backend/app/db/`, `frontend/src/pages/Dashboard.tsx`, `AthleteProfile.tsx`, `DecisionPanel.tsx`.
- **Person 2 owns:** `backend/app/ml/` (all of it), `backend/app/routes/recommendations.py`, `backend/app/routes/simulation.py`, `frontend/src/components/TrajectoryChart.tsx`, `ExplanationPanel.tsx`, `EvasionSim.tsx`.

Example prompts:

> "Inspect `backend/app/routes/athletes.py` and `backend/app/db/models.py`. Do not modify `backend/app/ml/`. Plan and implement a `GET /athletes` endpoint that joins the latest anomaly score per athlete from the `anomalies` table, sorted descending by anomaly_score. Write a pytest in `tests/test_athletes.py` covering an athlete with no anomalies and one with multiple. Run the tests, fix any failures, then show me a diff before committing."

> "Inspect `backend/app/ml/baseline.py`. I want you to implement a Normal-Normal conjugate Bayesian update function `update_posterior(prior_mean, prior_var, obs, obs_var)` returning `(posterior_mean, posterior_var)`. Add docstring with the math. Write unit tests against hand-computed values for 3 cases. Do not touch any route files."

> "Inspect `frontend/src/components/TrajectoryChart.tsx` and the mock fixture in `mock/trajectory.json`. Implement a Recharts line chart showing observed values as points, baseline as a line, and a shaded confidence band using `ReferenceArea` or a custom area series. Do not modify any other component. Show me a screenshot-equivalent description of the rendered structure before committing."

Claude Code should never be asked to "build the whole feature" in one shot — always scope to one file or one tightly related pair of files.

---

## 19. Person 3 Free-Tool Workflow

Person 3 works entirely in `/ml` and `/data`, independent of the live backend, using Python + Cursor free tier + free local models where useful (or no AI assistance at all for the statistics-heavy parts, which are usually faster to hand-write than to prompt for).

**Module interface contract** (so Person 1/2 can integrate without touching Person 3's code):
- **Input:** none (generator is self-contained, parameterized by a config dict: n_athletes, n_sports, anomaly_rate, seed).
- **Output:** `data/athletes.json`, `data/samples.json`, `data/ground_truth.json` (hidden), `data/cohort_stats.json` — all plain JSON, schema matching §8 exactly.
- **Integration method:** Person 1's DB seed script reads these JSON files directly at backend startup. No API, no live coupling — Person 3 can regenerate and hand off a new file anytime without blocking anyone.
- Evaluation notebook and README are Person 3's own deliverables, used for the demo's "we validated this" moment, not integrated into the running app.

---

## 20. GitHub / Collaboration

```
/frontend        (Person 1 + 2, component-level ownership as in §18)
/backend
  /app/routes    (Person 1: athletes, cases | Person 2: recommendations, simulation)
  /app/ml        (Person 2 only)
  /app/db        (Person 1 only)
/ml              (Person 3 — generator, evaluation notebook)
/data            (generated JSON, committed for reproducibility)
docs/api-contract.md
```

- **Branches:** `main` (always deployable), `p1/*`, `p2/*`, `p3/*` feature branches, PR into `main` daily.
- **Daily merge checkpoint:** end of each day, all three merge to `main` and the team runs the smoke test (§21) before starting the next day — catches integration drift within 24h instead of on Day 6.
- **Conflict prevention:** because ownership is file/directory-scoped (§18), P1 and P2 rarely touch the same file. Shared files (`db/models.py`, `api-contract.md`) require a 1-line Slack/WhatsApp ping before editing.
- **Code review:** lightweight — the other core dev reads the diff before merge, not a formal review process; speed matters more than ceremony at this scale.

---

## 21. Testing

- **Backend/ML:** pytest unit tests for baseline update math (hand-computed expected values), Mahalanobis scoring, Value Score formula, CUSUM detector — these are pure functions, cheap to test thoroughly.
- **API contract:** curl/Postman collection hitting every endpoint in §9 against seeded data, checked into repo as `tests/api_smoke.http`.
- **Frontend:** manual QA checklist per screen (loads, handles empty athlete, handles athlete with 1 sample vs. 40 samples).
- **Data validation:** Person 3's evaluation notebook checks precision/recall of the anomaly detector against hidden ground truth — this number becomes a demo talking point ("our detector catches X% of injected anomalies at Y% false-positive rate").
- **Integration/E2E:** daily merge checkpoint (§20) + full dry-run rehearsal on Day 6 morning.

---

## 22. Deployment

Deploy early — by end of **Day 2** you should have a live (even if empty/mock) frontend on Vercel and backend on Render, so integration problems surface while there's still time to fix them, not at midnight on Day 6. Ping the Render backend a few minutes before your demo slot to avoid a cold-start delay during judging.

---

## 23. Risk Management

| Risk | Probability | Impact | Prevention | Backup Plan |
|---|---|---|---|---|
| Claude Code generates subtly broken math (Bayesian update) | Medium | High | Unit test every formula against hand-computed values before wiring into the app | Person 2 manually verifies math in a notebook first, ports only verified logic |
| P1/P2 edit same file | Low | Medium | Strict directory ownership (§18) | Daily merge + quick Slack ping before touching shared files |
| API mismatch frontend/backend | Medium | Medium | Contract-first (§9) + mock JSON from Day 1 | Contract doc is source of truth; any change requires updating it first |
| ML "doesn't work" (no separation between normal/anomalous) | Medium | High | Validate against hidden ground truth by Day 4, not Day 6 | Fall back to simpler z-score threshold if Mahalanobis underperforms |
| Synthetic data looks unrealistic | Medium | Medium | Ground biomarker ranges/correlations in real published ABP reference values | Person 3 iterates data Day 1–3, locks it by Day 3 |
| Render free-tier cold start during judging | Medium | Medium | Ping backend 5 min before demo slot | Local backend + ngrok as day-of fallback |
| Person 3 blocked without paid AI | Low | Medium | Statistics/data-gen code is often faster hand-written than prompted anyway | Person 1/2 assist for 1–2 hrs if truly stuck |
| Integration takes too long on Day 6 | Medium | High | Daily integration checkpoints (§12–17), not a single Day 6 merge | Day 3 MVP is already fully integrated, so Day 6 only adds P1/P2 features on top of a working base |
| Scope creep | High | Medium | Hard P0/P1/P2/P3 classification (§2), enforced at daily standup | Feature-cutting order below |

---

## 24. Feature-Cutting Plan (if behind schedule)

1. **First cut:** Cohort comparison view, mock login screen (P2 features).
2. **Second cut:** Resource-constrained budget allocator — fall back to per-athlete recommendation only, no cross-athlete ranking.
3. **Third cut:** Adversarial evasion simulation — biggest novelty loss, but the P0 core (baseline + anomaly + uncertainty + recommendation + explanation + human decision) still stands alone as a complete, defensible story.

**Never cut:** the Bayesian baseline, uncertainty score, and human-in-the-loop decision flow — that's the entire thesis of the project. If only one thing survives, it must be "personalized baseline → uncertainty-aware anomaly → explained recommendation → human decides."

---

## 25. 3-Minute Demo Flow

1. **Problem (20s):** "Anti-doping systems today flag population-level thresholds and leave investigators guessing what to do next. We built a system that thinks in terms of *this athlete's* normal, *how sure* we are, and *what to check next* — not just a risk score."
2. **Athlete data → baseline (30s):** Open dashboard, select a flagged athlete, show trajectory chart with confidence band — "this is their personal expected range, learned from their own history."
3. **Deviation → uncertainty (30s):** Point to the anomaly panel — "here's where they deviate, and here's how confident we are — notice the system doesn't say 'doping detected.'"
4. **Recommended action (30s):** Show the recommendation panel and explanation text — "given this uncertainty and a limited testing budget, this is the single most valuable next test, and here's the reasoning."
5. **Human decision (20s):** Investigator clicks accept/reject, logged to audit trail — "a human always makes the final call."
6. **Adversarial proof (30s, if built):** Evasion simulation screen — "we tested our own detector against a micro-dosing strategy designed to stay under the radar — here's where a single-sample check misses it, and here's how our cumulative detector catches the sustained drift."
7. **Close (10s):** "Everything here — data, models, hosting — costs ₹0, built by 3 people in 6 days."

---

## 26. Final Master Checklist

- [ ] Synthetic dataset generated, validated against hidden ground truth, precision/recall documented
- [ ] Bayesian baseline module unit-tested
- [ ] Anomaly detection (Mahalanobis + IsolationForest) wired to real data
- [ ] Uncertainty score computed and displayed separately from anomaly score
- [ ] Recommendation engine (Value Score) producing ranked actions
- [ ] Explanation text generated per recommendation
- [ ] Dashboard, Athlete Profile, Trajectory, Explanation, Recommendation, Decision screens live
- [ ] Case + audit log working end to end
- [ ] Evasion simulation + CUSUM comparison (if not cut)
- [ ] Budget allocator (if not cut)
- [ ] Frontend deployed on Vercel, backend on Render, both smoke-tested
- [ ] Full demo rehearsed at least twice, backup video recorded
- [ ] ₹0 stack audit table double-checked — zero paid dependencies

---

### DAY 3 = WHAT WE CAN DEMO
Dashboard → select athlete → see personalized trajectory with confidence band → see anomaly + uncertainty, on real (seeded) synthetic data, deployed and reachable by URL.

### DAY 6 = WHAT WE CAN DEMO
Full flow above **plus** recommended next action with plain-language explanation, human investigator decision + audit trail, and (if not cut) the adversarial evasion simulation and budget-constrained recommendation ranking.

### EXACT FEATURES WE ARE BUILDING
Personal Bayesian baseline, Mahalanobis + IsolationForest anomaly detection, uncertainty scoring, Value-Score-based adaptive action recommender, template-based explanation generator, investigator dashboard with human-in-the-loop decisions, audit log, and (P1) a micro-dosing adversarial simulation with a CUSUM cumulative detector and a resource-constrained budget allocator.

### EXACT TECHNOLOGIES WE ARE USING
Vite + React + TypeScript + Tailwind + Recharts (Vercel) — FastAPI (Render) — SQLite — NumPy/SciPy/pandas/scikit-learn — GitHub — Claude Code (Person 1/2) — Cursor free tier (Person 3).

### EXACT ML MODELS WE ARE USING
Conjugate Normal-Normal Bayesian update (personal baseline), Mahalanobis distance (anomaly scoring), IsolationForest (cohort-level secondary signal), CUSUM (cumulative drift detector for the adversarial simulation). No deep learning.

### EXACTLY WHO DOES WHAT
Person 1: backend CRUD/DB/deployment + Dashboard/Profile/Decision screens. Person 2: all ML modules + Trajectory/Explanation/Recommendation/Simulation screens. Person 3: synthetic data generation, ground-truth validation, cohort stats, evaluation report, documentation.

### WHAT WE ARE NOT BUILDING
Real WADA/ADAMS integration, social-media/financial/travel surveillance data sources, deep learning, real multi-tenant authentication, mobile app.
