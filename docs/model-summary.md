# Model Summary — Adaptive Anti-Doping Defense Engine

This document describes the detection and decision pipeline in plain
English, intended for a non-technical audience. No mathematical
notation is used; technical detail is given in inline comments in the
relevant source files.

---

## Overview

The system does **not** compare an athlete against population averages.
Instead it builds and continuously updates a personal model for each
athlete, then measures how far each new test result sits from *that
individual's own normal*. This personalisation is the core design
principle: a haemoglobin value of 16.0 g/dL may be unremarkable for a
Cycling athlete at altitude but alarming for a swimmer who has never
exceeded 14.8 g/dL.

The pipeline has four stages:

1. Personalised Bayesian baseline (learn what's normal for *this* athlete)
2. Mahalanobis anomaly scoring (measure distance from personal normal)
3. Uncertainty score (track confidence separately from risk)
4. Value Score action engine (prioritise limited testing resources)

---

## Stage 1 — Personalised Bayesian Baseline

**What it does:** The system maintains a personal statistical model for
every athlete — specifically, a running estimate of each athlete's
typical value and typical variability for each biomarker. When a new
sample arrives, the model updates itself to incorporate the new
observation.

**How it works (in plain terms):** The model starts with a
sport-population prior — broad knowledge about what's physiologically
normal for, say, cyclists in general. Each new sample nudges the
estimate toward that individual's actual history. After a handful of
tests, the model is primarily shaped by the athlete's own data rather
than the population average. This is a standard Bayesian conjugate
update: the prior belief is a Normal distribution, and each observation
is combined with it to produce a tighter, athlete-specific posterior.

**Why this matters:** A blanket threshold (e.g. "flag anyone above 16.5
g/dL Hb") generates false positives for athletes who are naturally at
the high end of the range. The personalised baseline adapts to each
individual, making flags much more meaningful.

---

## Stage 2 — Mahalanobis Anomaly Scoring

**What it does:** Produces a single anomaly score (0–1) for each
sample, representing how unusual that sample is relative to the
athlete's own baseline.

**How it works (in plain terms):** Think of the athlete's five
biomarkers (Hb, Hct, RET%, OFF-score, T/E ratio) as a point in
five-dimensional space. The baseline defines the athlete's "home
region" — the cluster of values that are normal for them. The
Mahalanobis distance is the straight-line distance from today's sample
to that home region, but adjusted so that biomarkers which naturally
vary more (e.g. RET%) count proportionally less than biomarkers that
are usually very stable for this athlete. The raw distance is
normalised to a 0–1 scale using a chi-squared transformation so scores
are comparable across athletes and biomarkers.

**What it outputs:** An `anomaly_score` (0–1) and a list of
`contributing_biomarkers` ordered by their individual contribution,
so an investigator can immediately see *which* biomarkers drove the
flag, not just that a flag occurred.

---

## Stage 3 — Uncertainty Score

**What it does:** Quantifies how confident the system is in its
anomaly assessment for a given athlete at a given point in time.

**How it works (in plain terms):** An athlete with only 2 samples has a
very uncertain personal baseline — the model hasn't had enough data to
distinguish "this is their normal" from "this is an anomaly." The
uncertainty score captures this. It is kept entirely separate from the
anomaly score so that a high-anomaly, low-confidence flag ("something
looks unusual but we don't have enough history to be sure") is treated
differently from a high-anomaly, high-confidence flag ("this is
definitively outside this athlete's normal").

**Why this matters:** In a real anti-doping context, acting on an
uncertain flag wastes limited testing resources and risks unfairly
targeting athletes who simply haven't been tested enough yet. Surfacing
uncertainty as a first-class output lets the investigator make an
informed prioritisation decision.

---

## Stage 4 — Value Score Action Engine

**What it does:** Recommends the single most useful next action for
each athlete, given a limited testing budget.

**How it works (in plain terms):** For each flagged athlete, the system
estimates the *expected information value* of ordering an additional
test — how much the result would reduce uncertainty about a potential
violation — versus the cost of that test (an abstract resource unit).
It then solves a budget allocation problem: "given a fixed testing
budget, which combination of athletes maximises the total expected
information gained?" The output is a ranked recommendation list with
one of five action types:

| Action | Meaning |
|---|---|
| `no_action` | Score too low to warrant any response |
| `increase_monitoring` | Flag for heightened attention; no test yet |
| `target_test` | Order an out-of-competition targeted test |
| `biological_passport_review` | Trigger a full ABP longitudinal review |
| `open_case` | Open a formal investigation case |

---

## Validated Performance

Performance is evaluated against the 15 synthetic anomaly athletes in
`data/ground_truth.json` (18.75% of the 80-athlete dataset). Numbers
are from the fresh evaluation run against the re-exported anomaly
scores (Day 5).

### Precision / Recall / FPR by threshold

| Threshold | Precision | Recall | FPR | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|
| 0.50 | 58.3% | 46.7% | 7.7% | 51.9% | 7 | 5 | 8 | 60 |
| 0.55 | 54.5% | 40.0% | 7.7% | 46.2% | 6 | 5 | 9 | 60 |
| **0.70** | **100.0%** | **26.7%** | **0.0%** | **42.1%** | 4 | 0 | 11 | 65 |
| 0.85 | — | — | — | — | 0 | 0 | 15 | 65 |

> **Recommended operating threshold: 0.70.** Zero false positives at
> this level, at the cost of lower overall recall. Investigators
> receive only high-confidence flags and can direct limited resources
> accordingly.

### Recall by anomaly archetype (threshold 0.50)

| Pattern | Flagged athletes | Caught | Recall | Avg score |
|---|---|---|---|---|
| Transfusion | 5 | 5 | **100.0%** | 0.752 |
| EPO micro-dosing | 5 | 1 | **20.0%** | 0.404 |
| Steroid micro-dosing | 5 | 1 | **20.0%** | 0.398 |

---

## Known Limitations

### EPO and steroid micro-dosing are under-detected by the current model

The Mahalanobis detector is fundamentally a **single-sample** method:
it assesses how unusual one test result is compared to the athlete's
historical baseline. Micro-dosing strategies are designed to produce
changes that are individually small — no single sample crosses a clear
threshold. At the recommended threshold of 0.70, neither EPO nor
steroid micro-dosing athletes are caught; at 0.50, recall is 20% for
both patterns (1/5 athletes each).

**Mitigation — CUSUM (in development):** A CUSUM (Cumulative Sum
control chart) algorithm is being added to detect gradual drift across
a sample series. This directly addresses the micro-dosing gap by
accumulating small deviations over time, which individually fall below
the Mahalanobis threshold but collectively constitute a statistically
significant trend. See `GET /simulation/evasion` in
`docs/api-contract.md` for the planned endpoint.
