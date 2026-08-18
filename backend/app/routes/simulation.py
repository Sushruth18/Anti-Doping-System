import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Athlete, Sample
from app.db.session import get_db
from app.ml.anomaly import mahalanobis_distance, normalize_anomaly_score
from app.ml.baseline import BIOMARKERS, compute_current_posterior
from app.ml.cusum import compute_cusum

router = APIRouter()

# `pattern` IS the biomarker selector — there's no separate `biomarker`
# query param. The two archetypes this endpoint simulates are each defined
# by a single biomarker's drift (EPO micro-dosing -> hb, steroid
# micro-dosing -> te_ratio per CLAUDE.md's locked biomarker list), so
# `pattern` and "which biomarker" are the same choice; asking for both
# would let them contradict each other. Inference is from this explicit
# query param, not from the athlete's ground-truth archetype (the live
# endpoint must never read ground_truth.json — see CLAUDE.md's standing
# guardrail).
_PATTERN_BIOMARKER: dict[str, str] = {
    "micro_dosing": "hb",  # EPO micro-dosing (default)
    "steroid_micro_dosing": "te_ratio",
}

# Same "moderate" cutoff frontend/src/components/ExplanationPanel.tsx
# already applies to the normalized anomaly_score to label something
# elevated/moderate priority — reused here rather than inventing a new
# threshold. That file's own comment documents exactly the blind spot this
# endpoint exists to demonstrate: "EPO and steroid micro-dosing patterns
# score lower than transfusion patterns under this single-sample
# Mahalanobis detector — a known, documented limitation addressed by the
# planned CUSUM cumulative detector, not a threshold bug."
_SINGLE_SAMPLE_FLAG_THRESHOLD = 0.55


class CusumResult(BaseModel):
    cusum_upper: list[float]
    cusum_lower: list[float]
    flagged: bool
    flagged_at_index: int | None
    threshold: float


class EvasionSimulationResponse(BaseModel):
    athlete_id: int
    biomarker: Literal["hb", "te_ratio"]
    pattern: Literal["micro_dosing", "steroid_micro_dosing"]
    sample_count: int
    single_sample_scores: list[float]
    single_sample_flagged_any: bool
    cusum_result: CusumResult
    cusum_flagged: bool


@router.get("/simulation/evasion", response_model=EvasionSimulationResponse)
def simulate_evasion(
    athlete_id: int = Query(...),
    pattern: Literal["micro_dosing", "steroid_micro_dosing"] = Query(default="micro_dosing"),
    db: Session = Depends(get_db),
) -> EvasionSimulationResponse:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        raise HTTPException(status_code=404, detail=f"Athlete {athlete_id} not found")

    biomarker = _PATTERN_BIOMARKER[pattern]

    try:
        posterior = compute_current_posterior(athlete_id, db)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot simulate evasion for athlete {athlete_id}: insufficient_history "
                "(missing or invalid baseline_prior_json — a posterior could not be "
                "computed for this athlete)."
            ),
        )

    samples = (
        db.query(Sample)
        .filter(Sample.athlete_id == athlete_id)
        .order_by(Sample.date.asc())
        .all()
    )

    # (a) Per-sample single-sample scoring: anomaly.py's existing
    # mahalanobis_distance/normalize_anomaly_score, applied unmodified to
    # every historical sample against the athlete's current (fully-folded)
    # posterior — the same posterior/sample shape get_anomaly_score already
    # uses for the live latest-sample score, just looped over the whole
    # series instead of only the latest row.
    single_sample_scores: list[float] = []
    for sample in samples:
        sample_values = {b: getattr(sample, b) for b in BIOMARKERS}
        raw_distance = mahalanobis_distance(posterior, sample_values)
        single_sample_scores.append(normalize_anomaly_score(raw_distance))

    single_sample_flagged_any = any(
        score >= _SINGLE_SAMPLE_FLAG_THRESHOLD for score in single_sample_scores
    )

    # (b) CUSUM over just the target biomarker's series, against that same
    # posterior's mean/std for that biomarker — actual defaults (k=0.5,
    # h=5.0), not tuned for this athlete.
    baseline_mean, baseline_var = posterior[biomarker]
    baseline_std = math.sqrt(baseline_var)
    observations = [getattr(sample, biomarker) for sample in samples]

    cusum_result = compute_cusum(observations, baseline_mean=baseline_mean, baseline_std=baseline_std)

    return EvasionSimulationResponse(
        athlete_id=athlete_id,
        biomarker=biomarker,
        pattern=pattern,
        sample_count=len(samples),
        single_sample_scores=single_sample_scores,
        single_sample_flagged_any=single_sample_flagged_any,
        cusum_result=CusumResult(**cusum_result),
        cusum_flagged=cusum_result["flagged"],
    )
