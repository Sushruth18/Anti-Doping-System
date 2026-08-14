import json
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.models import Athlete, Sample
from app.db.session import get_db

router = APIRouter()

_BIOMARKERS = ("hb", "hct", "ret_pct", "off_score", "te_ratio")


class BiomarkerStat(BaseModel):
    mean: float
    std: float


class BaselinePrior(BaseModel):
    hb: BiomarkerStat
    hct: BiomarkerStat
    ret_pct: BiomarkerStat
    off_score: BiomarkerStat
    te_ratio: BiomarkerStat


class SampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_id: int
    date: date_type
    hb: float
    hct: float
    ret_pct: float
    off_score: float
    te_ratio: float
    competition_flag: bool
    altitude_flag: bool
    injury_flag: bool


class AthleteListItem(BaseModel):
    id: int
    name: str
    sport: str
    age: int | None
    latest_anomaly_score: float | None
    latest_uncertainty_score: float | None
    priority_score: float
    last_sample_date: date_type | None


class AthleteDetail(BaseModel):
    id: int
    name: str
    sport: str
    age: int | None
    baseline_prior: BaselinePrior
    samples: list[SampleOut]


@router.get("/athletes", response_model=list[AthleteListItem])
def list_athletes(
    sport: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AthleteListItem]:
    if sort is not None and sort != "priority":
        raise HTTPException(status_code=422, detail=f"Unsupported sort value: {sort!r}")

    query = db.query(Athlete)
    if sport is not None:
        query = query.filter(Athlete.sport == sport)
    athletes = query.all()

    items: list[AthleteListItem] = []
    for athlete in athletes:
        last_sample = (
            db.query(Sample)
            .filter(Sample.athlete_id == athlete.id)
            .order_by(Sample.date.desc())
            .first()
        )
        # `anomalies` and `recommendations` tables aren't implemented yet
        # (see docs/schema.md roadmap), so these are always null per the
        # contract's documented fallback until those land.
        latest_anomaly_score = None
        latest_uncertainty_score = None
        # TODO (Day 3): with both scores null, every athlete ties at 0.0 here — the
        # tie-break then silently falls through to DB insertion order, which
        # api-contract.md never defines. Revisit once real scores exist.
        priority_score = latest_anomaly_score if latest_anomaly_score is not None else 0.0

        items.append(
            AthleteListItem(
                id=athlete.id,
                name=athlete.name,
                sport=athlete.sport,
                age=athlete.age,
                latest_anomaly_score=latest_anomaly_score,
                latest_uncertainty_score=latest_uncertainty_score,
                priority_score=priority_score,
                last_sample_date=last_sample.date if last_sample else None,
            )
        )

    items.sort(
        key=lambda item: (item.priority_score, item.latest_uncertainty_score or 0.0),
        reverse=True,
    )
    return items


@router.get("/athletes/{athlete_id}", response_model=AthleteDetail)
def get_athlete(athlete_id: int, db: Session = Depends(get_db)) -> AthleteDetail:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        raise HTTPException(status_code=404, detail=f"Athlete {athlete_id} not found")

    if athlete.baseline_prior_json:
        baseline_data = json.loads(athlete.baseline_prior_json)
    else:
        # baseline_prior_json is nullable in the schema, but the contract's
        # AthleteDetail shape doesn't make baseline_prior optional; fall
        # back to a zeroed prior rather than breaking response validation.
        baseline_data = {biomarker: {"mean": 0.0, "std": 0.0} for biomarker in _BIOMARKERS}

    samples = (
        db.query(Sample)
        .filter(Sample.athlete_id == athlete_id)
        .order_by(Sample.date.asc())
        .all()
    )

    return AthleteDetail(
        id=athlete.id,
        name=athlete.name,
        sport=athlete.sport,
        age=athlete.age,
        baseline_prior=BaselinePrior(**baseline_data),
        samples=[SampleOut.model_validate(sample) for sample in samples],
    )
