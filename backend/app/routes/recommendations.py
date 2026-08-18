"""`GET /athletes/{id}/recommendation` per `docs/api-contract.md`'s
Day 4/5 `Recommendation` shape.

Compute-on-request only, same pattern as `GET /athletes/{id}/anomalies`'
live `contributing_biomarkers` computation -- no `recommendations` table
exists yet, so nothing here is persisted. See
`docs/known-limitations.md` for the live-vs-persisted question this
raises (same class of issue as `latest_uncertainty_score`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_serializer
from sqlalchemy.orm import Session

from app.db.models import Athlete
from app.db.session import get_db
from app.ml.action_engine import compute_recommendation
from app.ml.budget_allocator import allocate_budget

router = APIRouter()


class RecommendationOut(BaseModel):
    # `id` is nullable here even though the locked contract's
    # `Recommendation.id` is `number` (non-nullable): `compute_recommendation`
    # always returns `id=None` since there's no `recommendations` table to
    # assign a real primary key from yet (see module docstring). Flagging
    # this as a contract deviation rather than inventing a fake id.
    id: int | None
    athlete_id: int
    action_type: Literal[
        "no_action",
        "increase_monitoring",
        "target_test",
        "biological_passport_review",
        "open_case",
    ]
    value_score: float
    uncertainty_score: float
    anomaly_score: float
    cost: float
    explanation_text: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/athletes/{athlete_id}/recommendation", response_model=RecommendationOut)
def get_athlete_recommendation(athlete_id: int, db: Session = Depends(get_db)) -> RecommendationOut:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        raise HTTPException(status_code=404, detail=f"Athlete {athlete_id} not found")

    recommendation = compute_recommendation(athlete_id, db)
    if recommendation is None:
        # Per api-contract.md: "athlete exists but has no recommendation
        # yet" gets the same 404 message as an unknown athlete id --
        # frontend isn't expected to distinguish the two cases.
        raise HTTPException(status_code=404, detail=f"Athlete {athlete_id} not found")

    return RecommendationOut(**recommendation)


_ActionType = Literal[
    "no_action",
    "increase_monitoring",
    "target_test",
    "biological_passport_review",
    "open_case",
]


class BudgetSelectedItem(BaseModel):
    athlete_id: int
    name: str
    action_type: _ActionType
    value_score: float
    cost: float
    cumulative_cost_after: float
    explanation_text: str


class BudgetAllocationResponse(BaseModel):
    budget: int
    selected: list[BudgetSelectedItem]
    total_cost: float
    total_value: float
    athletes_evaluated: int
    candidates_considered: int
    candidates_selected: int


@router.get("/recommendations/budget", response_model=BudgetAllocationResponse)
def get_budget_recommendations(
    budget: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> BudgetAllocationResponse:
    athletes = db.query(Athlete).all()

    # Reuses compute_recommendation exactly as get_athlete_recommendation
    # above does -- same function, same call shape, no reimplementation
    # (and explanation_text comes along for free: compute_recommendation
    # already calls explain.explain_recommendation internally, so there's
    # no separate call to duplicate here).
    #
    # Two athlete categories are excluded from the candidates list
    # entirely, not passed through as zero-cost/zero-value entries:
    #   - compute_recommendation returns None (no samples / insufficient
    #     history -- the case api-contract.md and the single-athlete
    #     endpoint already treat as "no recommendation exists"). Not
    #     scored at all -- excluded from athletes_evaluated too.
    #   - action_type == "no_action": a real, scored recommendation, but
    #     one with nothing to fund (cost=0.0, value_score=0.0 -- see
    #     action_engine.compute_recommendation's no_action handling).
    #     There's nothing to buy for this athlete, so it doesn't belong in
    #     a budget candidate pool any more than an unscored athlete does.
    #     This also keeps allocate_budget's own precondition intact: it
    #     raises ValueError on any candidate with cost <= 0, which every
    #     no_action recommendation would otherwise trigger. Still counted
    #     in athletes_evaluated, though -- it WAS scored, just not
    #     eligible for the budget pool.
    #
    # athletes_evaluated (every non-None result) vs. candidates_considered
    # (allocate_budget's own count of what it received, i.e. excluding
    # no_action too) are deliberately different numbers -- see
    # docs/api-contract.md for the worked distinction.
    recommendations_by_athlete_id: dict[int, dict] = {}
    candidates: list[dict] = []
    athletes_evaluated = 0
    for athlete in athletes:
        recommendation = compute_recommendation(athlete.id, db)
        if recommendation is None:
            continue
        athletes_evaluated += 1
        if recommendation["action_type"] == "no_action":
            continue
        recommendations_by_athlete_id[athlete.id] = recommendation
        candidates.append(
            {
                "athlete_id": athlete.id,
                "value_score": recommendation["value_score"],
                "cost": recommendation["cost"],
            }
        )

    allocation = allocate_budget(candidates, budget)

    athlete_names = {athlete.id: athlete.name for athlete in athletes}
    selected = [
        BudgetSelectedItem(
            athlete_id=item["athlete_id"],
            name=athlete_names[item["athlete_id"]],
            action_type=recommendations_by_athlete_id[item["athlete_id"]]["action_type"],
            value_score=item["value_score"],
            cost=item["cost"],
            cumulative_cost_after=item["cumulative_cost_after"],
            explanation_text=recommendations_by_athlete_id[item["athlete_id"]]["explanation_text"],
        )
        for item in allocation["selected"]
    ]

    return BudgetAllocationResponse(
        budget=budget,
        selected=selected,
        total_cost=allocation["total_cost"],
        total_value=allocation["total_value"],
        athletes_evaluated=athletes_evaluated,
        candidates_considered=allocation["candidates_considered"],
        candidates_selected=allocation["candidates_selected"],
    )
