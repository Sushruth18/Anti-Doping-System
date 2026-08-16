"""Value Score / recommended-action engine, per
`docs/implementation-roadmap.md`'s Day 4 spec:
`Value Score = anomaly x uncertainty x sensitivity / cost`.

Ties together `app.ml.anomaly` (anomaly score, contributing biomarkers)
and `app.ml.uncertainty` (per-biomarker + athlete-level uncertainty) into
a single recommended `action_type` and `value_score` per athlete, matching
the fields `docs/api-contract.md`'s `Recommendation` interface expects.
Cost/sensitivity constants per `action_type` were decided together (not
invented here) -- see `ACTION_TIERS` below.

Does not persist anything (no `recommendations` table yet). Wired into
`GET /athletes/{id}/recommendation` (`app.routes.recommendations`) --
`compute_recommendation` is the plain function that route calls.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal, TypedDict

from sqlalchemy.orm import Session

from app.db.models import Athlete
from app.ml.anomaly import get_anomaly_score, normalize_anomaly_score
from app.ml.baseline import BIOMARKERS, compute_current_posterior
from app.ml.explain import explain_recommendation
from app.ml.uncertainty import compute_athlete_uncertainty_score, compute_uncertainty_score

ActionType = Literal[
    "no_action",
    "increase_monitoring",
    "target_test",
    "biological_passport_review",
    "open_case",
]


class ActionTier(TypedDict):
    min_anomaly_score: float
    action_type: ActionType
    cost: float | None
    sensitivity: float | None


# Ordered ascending by `min_anomaly_score`; bands are on the NORMALIZED 0-1
# anomaly score (`normalize_anomaly_score()`'s output), not the raw
# unbounded Mahalanobis distance `get_anomaly_score()` returns.
# `no_action`'s `cost`/`sensitivity` are `None`: it's a "nothing to act
# on" tier, not one of the four scored actions, so it never reaches
# `compute_value_score` (see `compute_recommendation`) -- there's no
# sensitivity/cost to define for not acting.
ACTION_TIERS: tuple[ActionTier, ...] = (
    {"min_anomaly_score": 0.00, "action_type": "no_action", "cost": None, "sensitivity": None},
    {"min_anomaly_score": 0.30, "action_type": "increase_monitoring", "cost": 1.0, "sensitivity": 0.3},
    {"min_anomaly_score": 0.55, "action_type": "target_test", "cost": 3.0, "sensitivity": 0.7},
    {"min_anomaly_score": 0.70, "action_type": "biological_passport_review", "cost": 5.0, "sensitivity": 0.85},
    {"min_anomaly_score": 0.85, "action_type": "open_case", "cost": 8.0, "sensitivity": 0.95},
)

class Recommendation(TypedDict):
    id: None
    athlete_id: int
    action_type: ActionType
    value_score: float
    uncertainty_score: float
    anomaly_score: float
    cost: float
    explanation_text: str
    created_at: datetime


def select_action_tier(anomaly_score_normalized: float) -> ActionTier:
    """The highest tier in `ACTION_TIERS` whose `min_anomaly_score` is <=
    `anomaly_score_normalized`. `ACTION_TIERS` is ordered ascending and its
    bands are contiguous (each tier's upper edge is the next tier's
    `min_anomaly_score`), so the last tier satisfied is exactly the band
    `anomaly_score_normalized` falls into.
    """
    selected = ACTION_TIERS[0]
    for tier in ACTION_TIERS:
        if anomaly_score_normalized >= tier["min_anomaly_score"]:
            selected = tier
        else:
            break
    return selected


def compute_value_score(
    anomaly_score_normalized: float,
    uncertainty_score: float,
    sensitivity: float,
    cost: float,
) -> float:
    """`Value Score = anomaly * uncertainty * sensitivity / cost`, exactly
    as decided in `docs/implementation-roadmap.md`. No clipping/rounding --
    callers needing a bounded 0-1 display value should use
    `normalize_value_scores_for_display` on a cohort of these, not modify
    this function.
    """
    return anomaly_score_normalized * uncertainty_score * sensitivity / cost


def _compute_uncertainty_score(
    athlete_id: int,
    db: Session,
    posterior: dict[str, tuple[float, float]],
    z_score_squared_by_biomarker: dict[str, float],
) -> float:
    """Athlete-level uncertainty score for `compute_recommendation`, reusing
    `posterior` and `z_score_squared_by_biomarker` already computed by the
    caller (from `compute_current_posterior` and `get_anomaly_score`
    respectively) instead of recomputing them. Same per-biomarker-score ->
    `compute_athlete_uncertainty_score` shape as
    `app.routes.athletes._compute_latest_uncertainty_score`.
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    baseline_data = json.loads(athlete.baseline_prior_json)
    per_biomarker_scores = {
        biomarker: compute_uncertainty_score(
            posterior[biomarker][1], baseline_data[biomarker]["std"] ** 2
        )
        for biomarker in BIOMARKERS
    }
    return compute_athlete_uncertainty_score(per_biomarker_scores, z_score_squared_by_biomarker)


def compute_recommendation(athlete_id: int, db: Session) -> Recommendation | None:
    """Full Value Score pipeline for one athlete: live anomaly score ->
    action tier -> uncertainty score -> value score -> Recommendation-shaped
    dict (`docs/api-contract.md`'s `Recommendation` interface).

    `id` is always `None` here: there's no `recommendations` table yet to
    assign a real primary key from, so persistence (and setting `id`) is
    left to whatever endpoint/write-path adopts this function later.
    `created_at` is `datetime.utcnow()` at call time, same convention
    `app.routes.athletes` uses for freshly created `Anomaly` rows.

    For the `no_action` tier, `value_score` is `0.0` and `cost` is `0.0` --
    `no_action` has no `sensitivity`/`cost` in `ACTION_TIERS` (nothing is
    being recommended, so there's no cost to spend), so
    `compute_value_score` is not called for it.

    Returns:
        `None` if the athlete can't be scored (mirrors `get_anomaly_score`'s
        `reason="insufficient_history"` case: unknown athlete, no
        `baseline_prior_json`, or no samples) rather than raising.
    """
    result = get_anomaly_score(athlete_id, db)
    if result["reason"] is not None:
        return None

    anomaly_score_normalized = normalize_anomaly_score(result["anomaly_score"])
    z_score_squared_by_biomarker = {
        entry["biomarker"]: entry["z_score_squared"] for entry in result["contributing_biomarkers"]
    }

    posterior = compute_current_posterior(athlete_id, db)
    uncertainty_score = _compute_uncertainty_score(
        athlete_id, db, posterior, z_score_squared_by_biomarker
    )

    tier = select_action_tier(anomaly_score_normalized)
    if tier["action_type"] == "no_action":
        value_score = 0.0
        cost = 0.0
    else:
        value_score = compute_value_score(
            anomaly_score_normalized, uncertainty_score, tier["sensitivity"], tier["cost"]
        )
        cost = tier["cost"]

    explanation_text = explain_recommendation(tier["action_type"], result["contributing_biomarkers"])

    return {
        "id": None,
        "athlete_id": athlete_id,
        "action_type": tier["action_type"],
        "value_score": value_score,
        "uncertainty_score": uncertainty_score,
        "anomaly_score": anomaly_score_normalized,
        "cost": cost,
        "explanation_text": explanation_text,
        "created_at": datetime.utcnow(),
    }


def normalize_value_scores_for_display(scores: list[float]) -> list[float]:
    """Min-max normalize raw `value_score`s (e.g. a cohort's worth of
    `compute_recommendation(...)["value_score"]`) into 0-1, for DISPLAY
    purposes only.

    Kept as a distinct function from `compute_value_score` on purpose: the
    raw `value_score` (small, e.g. ~0.005 for the seeded cohort -- see
    `docs/known-limitations.md`-adjacent investigation notes) is the true
    Value Score formula output and is what ranking/budget-allocation should
    use; this min-max-rescaled version is only for showing a 0-1 bar/number
    to a human and must never be fed back into ranking or
    `compute_value_score` math, so the two are never returned from (or
    passed to) the same function.

    Args:
        scores: raw `value_score` values, in whatever order the caller
            wants preserved (same order comes back out).

    Returns:
        Same-length list, each value min-max normalized against `scores`'
        own min/max. If every score is equal (including the empty-list and
        single-item cases trivially satisfying this), returns all `0.0`
        rather than dividing by zero -- there's no meaningful spread to
        normalize.
    """
    if not scores:
        return []

    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [0.0 for _ in scores]

    return [(score - lo) / (hi - lo) for score in scores]
