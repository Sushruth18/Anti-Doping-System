"""Ported from ml/prototype_baseline.py::update_posterior (Dev 2, validated
via that script's validate_convergence() — see CLAUDE.md's app/ml/ vs /ml
note: this is a copy of the validated math, not a live import from /ml).
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Iterator

from sqlalchemy.orm import Session

from app.db.models import Athlete, Sample

BIOMARKERS = ("hb", "hct", "ret_pct", "off_score", "te_ratio")

# TODO (Day 3): obs_var is a placeholder — the prototype only validated a
# fixed measurement-noise variance (0.25) for Hb specifically. Scaling it
# from each biomarker's own prior std keeps it dimensionally sane across
# biomarkers with very different ranges (e.g. te_ratio ~1-2 vs off_score
# ~70-120), but it's unvalidated. Replace with real per-biomarker
# measurement-noise variances once Dev 2 supplies them.
OBS_VAR_STD_FRACTION = 0.25


def update_posterior(
    prior_mean: float,
    prior_var: float,
    obs: float,
    obs_var: float,
) -> tuple[float, float]:
    """Normal-Normal conjugate update for a single scalar observation.

    Given prior N(prior_mean, prior_var) and observation N(obs, obs_var):

        posterior_precision = 1/prior_var + 1/obs_var
        posterior_var     = 1 / posterior_precision
        posterior_mean      = posterior_var * (prior_mean/prior_var + obs/obs_var)

    Equivalently, posterior_mean is the precision-weighted average of
    prior_mean and obs.

    Returns:
        (posterior_mean, posterior_var)
    """
    if prior_var <= 0 or obs_var <= 0:
        raise ValueError("prior_var and obs_var must be positive")

    prior_precision = 1.0 / prior_var
    obs_precision = 1.0 / obs_var
    posterior_precision = prior_precision + obs_precision
    posterior_var = 1.0 / posterior_precision
    posterior_mean = posterior_var * (
        (prior_mean * prior_precision) + (obs * obs_precision)
    )
    return posterior_mean, posterior_var


def fold_biomarker_posterior(
    prior_mean: float,
    prior_var: float,
    samples_for_biomarker: Iterable[tuple[Any, float]],
    obs_var: float,
) -> Iterator[tuple[Any, float, float]]:
    """Fold a single biomarker's samples through `update_posterior` in order.

    `samples_for_biomarker` is an iterable of `(label, observed_value)`
    pairs, already ordered the way the caller wants folded (e.g. ascending
    by date). `label` is opaque to this function — not interpreted, just
    echoed back in each yielded tuple so a caller that discards its own
    sample list can still re-associate a fold step with whatever it used to
    order the samples. This function does not know about `Athlete`/`Sample`
    ORM models or `BIOMARKERS`/`OBS_VAR_STD_FRACTION` — plain values in,
    plain values out, no DB dependency.

    Yields:
        `(label, mean, var)` after each fold step, one per item in
        `samples_for_biomarker`, in order. The raw prior itself is never
        yielded — only post-update states.
    """
    mean, var = prior_mean, prior_var
    for label, observed in samples_for_biomarker:
        mean, var = update_posterior(mean, var, observed, obs_var)
        yield label, mean, var


def compute_current_posterior(
    athlete_id: int, db_session: Session
) -> dict[str, tuple[float, float]]:
    """Current per-biomarker posterior for an athlete.

    Starts from `Athlete.baseline_prior_json` as the prior for each
    biomarker in `BIOMARKERS`, then folds every `Sample` row (ordered by
    date ascending) through `fold_biomarker_posterior`, keeping only the
    final `(mean, var)` per biomarker after all samples — not the
    intermediate per-sample values.

    Raises:
        ValueError: if the athlete doesn't exist or has no
            `baseline_prior_json`.

    Returns:
        `biomarker -> (posterior_mean, posterior_var)`, one entry per
        `BIOMARKERS`.
    """
    athlete = db_session.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None or not athlete.baseline_prior_json:
        raise ValueError(
            f"athlete {athlete_id} not found or has no baseline_prior_json"
        )

    baseline_data = json.loads(athlete.baseline_prior_json)
    samples = (
        db_session.query(Sample)
        .filter(Sample.athlete_id == athlete_id)
        .order_by(Sample.date.asc())
        .all()
    )

    result: dict[str, tuple[float, float]] = {}
    for biomarker in BIOMARKERS:
        prior_entry = baseline_data[biomarker]
        prior_std = prior_entry["std"]
        obs_var = (OBS_VAR_STD_FRACTION * prior_std) ** 2
        mean, var = prior_entry["mean"], prior_std**2

        samples_for_biomarker = (
            (None, getattr(sample, biomarker)) for sample in samples
        )
        for _label, mean, var in fold_biomarker_posterior(
            mean, var, samples_for_biomarker, obs_var
        ):
            pass  # only the final (mean, var) matters here

        result[biomarker] = (mean, var)

    return result
