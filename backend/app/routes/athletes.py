import json
import math
from datetime import date as date_type
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Anomaly, Athlete, Sample
from app.db.session import get_db
from app.ml.anomaly import ANOMALY_METHOD, get_anomaly_score, normalize_anomaly_score
from app.ml.baseline import (
    BIOMARKERS,
    OBS_VAR_STD_FRACTION,
    compute_current_posterior,
    fold_biomarker_posterior,
)

router = APIRouter()

_BIOMARKER_UNITS = {
    "hb": "g/dL",
    "hct": "%",
    "ret_pct": "%",
    "off_score": "score",
    "te_ratio": "ratio",
}

_TRAJECTORY_CI_LEVEL = 0.95


def _compute_off_score(hb: float, ret_pct: float) -> float:
    # Locked formula per CLAUDE.md: off_score = (hb_g_dL * 10) - 60 *
    # sqrt(ret_pct). hb is stored/received in g/dL; convert to g/L (*10)
    # before applying the formula.
    return (hb * 10) - 60 * math.sqrt(ret_pct)


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


class TrajectoryPoint(BaseModel):
    date: date_type
    observed: float
    expected: float
    ci_lower: float
    ci_upper: float


class BiomarkerTrajectory(BaseModel):
    biomarker: Literal["hb", "hct", "ret_pct", "off_score", "te_ratio"]
    unit: str
    points: list[TrajectoryPoint]


class TrajectoryResponse(BaseModel):
    athlete_id: int
    ci_level: float
    series: list[BiomarkerTrajectory]


class NewSampleInput(BaseModel):
    # extra="forbid" rejects any unexpected field — including a
    # client-supplied off_score — with a 422, per api-contract.md's
    # "reject rather than silently ignore" requirement. off_score is
    # always server-derived (see _compute_off_score) and never accepted
    # from the client.
    model_config = ConfigDict(extra="forbid")

    date: date_type
    hb: float
    hct: float
    ret_pct: float
    te_ratio: float
    competition_flag: bool
    altitude_flag: bool
    injury_flag: bool


class AnomalyOut(BaseModel):
    """Small Anomaly shape used only by NewSampleResponse.anomaly — no
    contributing_biomarkers, per api-contract.md's distinct `Anomaly`
    interface there (as opposed to AnomalyDetail below, used by
    GET /athletes/{id}/anomalies, which does include it)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_id: int
    sample_id: int
    anomaly_score: float
    mahalanobis_distance: float
    method: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class NewSampleResponse(BaseModel):
    sample: SampleOut
    updated_baseline: BaselinePrior
    anomaly: AnomalyOut


class ContributingBiomarkerOut(BaseModel):
    biomarker: Literal["hb", "hct", "ret_pct", "off_score", "te_ratio"]
    observed_value: float
    posterior_mean: float
    z_score_squared: float
    deviation_direction: Literal["above", "below"]


class AnomalyDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_id: int
    sample_id: int
    anomaly_score: float
    mahalanobis_distance: float
    method: str
    created_at: datetime
    contributing_biomarkers: list[ContributingBiomarkerOut]

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


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

    # One query for the latest anomaly per athlete (row_number over
    # created_at desc, id desc as a deterministic tiebreak for equal
    # timestamps) instead of a per-athlete N+1 lookup.
    latest_rank = (
        func.row_number()
        .over(
            partition_by=Anomaly.athlete_id,
            order_by=(Anomaly.created_at.desc(), Anomaly.id.desc()),
        )
        .label("latest_rank")
    )
    ranked_anomalies = select(
        Anomaly.athlete_id, Anomaly.anomaly_score, latest_rank
    ).subquery()
    latest_anomaly_rows = db.execute(
        select(ranked_anomalies.c.athlete_id, ranked_anomalies.c.anomaly_score).where(
            ranked_anomalies.c.latest_rank == 1
        )
    ).all()
    latest_anomaly_by_athlete = {row.athlete_id: row.anomaly_score for row in latest_anomaly_rows}

    items: list[AthleteListItem] = []
    for athlete in athletes:
        last_sample = (
            db.query(Sample)
            .filter(Sample.athlete_id == athlete.id)
            .order_by(Sample.date.desc())
            .first()
        )
        latest_anomaly_score = latest_anomaly_by_athlete.get(athlete.id)
        # `recommendations` table isn't implemented yet (see docs/schema.md
        # roadmap), so this stays null per the contract's documented
        # fallback until it lands.
        latest_uncertainty_score = None
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
        baseline_data = {biomarker: {"mean": 0.0, "std": 0.0} for biomarker in BIOMARKERS}

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


@router.get("/athletes/{athlete_id}/trajectory", response_model=TrajectoryResponse)
def get_athlete_trajectory(athlete_id: int, db: Session = Depends(get_db)) -> TrajectoryResponse:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        raise HTTPException(status_code=404, detail=f"Athlete {athlete_id} not found")

    baseline_data = json.loads(athlete.baseline_prior_json)

    samples = (
        db.query(Sample)
        .filter(Sample.athlete_id == athlete_id)
        .order_by(Sample.date.asc())
        .all()
    )

    series: list[BiomarkerTrajectory] = []
    for biomarker in BIOMARKERS:
        prior_entry = baseline_data[biomarker]
        prior_std = prior_entry["std"]
        obs_var = (OBS_VAR_STD_FRACTION * prior_std) ** 2

        mean = prior_entry["mean"]
        var = prior_std**2
        obs_pairs = ((sample.date, getattr(sample, biomarker)) for sample in samples)
        points: list[TrajectoryPoint] = []
        for sample, (_label, mean, var) in zip(
            samples, fold_biomarker_posterior(mean, var, obs_pairs, obs_var)
        ):
            observed = getattr(sample, biomarker)
            margin = 1.96 * math.sqrt(var)
            points.append(
                TrajectoryPoint(
                    date=sample.date,
                    observed=observed,
                    expected=mean,
                    ci_lower=mean - margin,
                    ci_upper=mean + margin,
                )
            )

        series.append(
            BiomarkerTrajectory(
                biomarker=biomarker,
                unit=_BIOMARKER_UNITS[biomarker],
                points=points,
            )
        )

    return TrajectoryResponse(
        athlete_id=athlete_id,
        ci_level=_TRAJECTORY_CI_LEVEL,
        series=series,
    )


@router.post("/athletes/{athlete_id}/samples", response_model=NewSampleResponse, status_code=201)
def create_athlete_sample(
    athlete_id: int, body: NewSampleInput, db: Session = Depends(get_db)
) -> NewSampleResponse:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        raise HTTPException(status_code=404, detail=f"Athlete {athlete_id} not found")

    latest_sample = (
        db.query(Sample)
        .filter(Sample.athlete_id == athlete_id)
        .order_by(Sample.date.desc())
        .first()
    )
    if latest_sample is not None and body.date <= latest_sample.date:
        raise HTTPException(
            status_code=422,
            detail=(
                f"New sample date {body.date} must be strictly after the athlete's "
                f"current latest sample date {latest_sample.date}; out-of-order "
                "ingestion is rejected because compute_current_posterior's fold "
                "is order-dependent."
            ),
        )

    off_score = _compute_off_score(body.hb, body.ret_pct)
    new_sample = Sample(
        athlete_id=athlete_id,
        date=body.date,
        hb=body.hb,
        hct=body.hct,
        ret_pct=body.ret_pct,
        off_score=off_score,
        te_ratio=body.te_ratio,
        competition_flag=body.competition_flag,
        altitude_flag=body.altitude_flag,
        injury_flag=body.injury_flag,
    )
    db.add(new_sample)
    db.flush()  # assign new_sample.id without committing yet

    result = get_anomaly_score(athlete_id, db)
    if result["reason"] is not None:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot score athlete {athlete_id}: insufficient_history "
                "(missing or invalid baseline_prior_json — a posterior "
                "could not be computed for this athlete)."
            ),
        )

    raw_distance = result["anomaly_score"]
    new_anomaly = Anomaly(
        athlete_id=athlete_id,
        sample_id=new_sample.id,
        anomaly_score=normalize_anomaly_score(raw_distance),
        mahalanobis_distance=raw_distance,
        method=ANOMALY_METHOD,
        created_at=datetime.utcnow(),
    )
    db.add(new_anomaly)
    db.commit()
    db.refresh(new_sample)
    db.refresh(new_anomaly)

    posterior = compute_current_posterior(athlete_id, db)
    updated_baseline = BaselinePrior(
        **{
            biomarker: {"mean": mean, "std": math.sqrt(var)}
            for biomarker, (mean, var) in posterior.items()
        }
    )

    return NewSampleResponse(
        sample=SampleOut.model_validate(new_sample),
        updated_baseline=updated_baseline,
        anomaly=AnomalyOut.model_validate(new_anomaly),
    )


@router.get("/athletes/{athlete_id}/anomalies", response_model=list[AnomalyDetail])
def get_athlete_anomalies(athlete_id: int, db: Session = Depends(get_db)) -> list[AnomalyDetail]:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        raise HTTPException(status_code=404, detail=f"Athlete {athlete_id} not found")

    anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.athlete_id == athlete_id)
        .order_by(Anomaly.created_at.desc(), Anomaly.id.desc())
        .all()
    )
    if not anomalies:
        return []

    # contributing_biomarkers can only be freshly computed against the
    # CURRENT posterior — it's meaningful for the most recent anomaly only;
    # older rows' originating posterior state can't be reconstructed after
    # the fact (see docs/api-contract.md discussion), so they get [].
    latest_contributing_biomarkers: list[ContributingBiomarkerOut] = []
    live_result = get_anomaly_score(athlete_id, db)
    if live_result["reason"] is None:
        posterior = compute_current_posterior(athlete_id, db)
        latest_sample = (
            db.query(Sample)
            .filter(Sample.athlete_id == athlete_id)
            .order_by(Sample.date.desc())
            .first()
        )
        for entry in live_result["contributing_biomarkers"]:
            biomarker = entry["biomarker"]
            posterior_mean, _posterior_var = posterior[biomarker]
            latest_contributing_biomarkers.append(
                ContributingBiomarkerOut(
                    biomarker=biomarker,
                    observed_value=getattr(latest_sample, biomarker),
                    posterior_mean=posterior_mean,
                    z_score_squared=entry["z_score_squared"],
                    deviation_direction=entry["deviation_direction"],
                )
            )

    details: list[AnomalyDetail] = []
    for index, anomaly in enumerate(anomalies):
        details.append(
            AnomalyDetail(
                id=anomaly.id,
                athlete_id=anomaly.athlete_id,
                sample_id=anomaly.sample_id,
                anomaly_score=anomaly.anomaly_score,
                mahalanobis_distance=anomaly.mahalanobis_distance,
                method=anomaly.method,
                created_at=anomaly.created_at,
                contributing_biomarkers=(
                    latest_contributing_biomarkers if index == 0 else []
                ),
            )
        )

    return details
