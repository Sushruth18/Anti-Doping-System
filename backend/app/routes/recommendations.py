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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_serializer
from sqlalchemy.orm import Session

from app.db.models import Athlete
from app.db.session import get_db
from app.ml.action_engine import compute_recommendation

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
