"""Mahalanobis distance scoring against a per-athlete Bayesian baseline.

Given the athlete's posterior mean/variance per biomarker (as produced by
repeated calls to `app.ml.baseline.update_posterior`) and a sample of
observed values, this computes how far that sample sits from the athlete's
personal baseline in standardized units.

For a multivariate normal baseline with covariance matrix Sigma, the
Mahalanobis distance of an observation x from mean mu is:

    d(x) = sqrt( (x - mu)^T * Sigma^-1 * (x - mu) )

This module assumes the biomarkers are **independent**, i.e. Sigma is
diagonal with each biomarker's own posterior variance on the diagonal.
Sigma^-1 is then also diagonal (1/var_i per biomarker), which collapses the
quadratic form into a simple sum of per-biomarker squared z-scores:

    d(x) = sqrt( sum_i ( (x_i - mu_i)^2 / var_i ) )

This is a simplifying assumption for the MVP — biomarkers are not actually
independent (e.g. off_score is derived from hb and ret_pct, hb and hct move
together), so a full covariance estimate would produce a different distance.
Estimating the true multivariate covariance is out of scope here; this
diagonal approximation is a reasonable first pass for flagging outliers.
"""

from __future__ import annotations

import math
from typing import Mapping

from app.db.models import Sample
from app.ml.baseline import compute_current_posterior

BIOMARKERS = ("hb", "hct", "ret_pct", "off_score", "te_ratio")

ANOMALY_METHOD = "mahalanobis_baseline"

# Maps the raw, unbounded Mahalanobis distance from get_anomaly_score into
# the contract's normalized-0-1 anomaly_score via 1 - exp(-distance / SCALE).
#
# Calibration method (unchanged since the original 3.0->10.0 recalibration):
# target the non-anomalous population's median RAW Mahalanobis distance to
# map to ~0.5 normalized, i.e. SCALE = -median_non_anomalous_raw_distance /
# ln(0.5). This keeps the normalized score's center of mass at a fixed,
# interpretable point (a "typical clean athlete" scores ~0.5) regardless of
# how the underlying raw-distance magnitude shifts with dataset changes.
#
# Recalibrated 2026-08-19 (10.0 -> 24.4008): the seeded dataset moved from a
# fixed 5 samples/athlete to 8-20 samples/athlete. Tighter posteriors from
# more samples systematically inflate raw Mahalanobis distance for the same
# physiological deviation (posterior variance shrinks, and Mahalanobis
# distance divides by variance), which desynced the old SCALE=10.0 from the
# new data: cohort-wide median raw distance drifted to ~16.9 (was
# calibrated against a much lower baseline under 5-sample posteriors),
# pushing median normalized score to ~0.82 and 41% of the 80-athlete cohort
# into the top "open_case" tier. Rederived via the same formula against the
# regenerated data/ground_truth.json's 66 non-anomalous athletes:
# median_non_anomalous_raw = 16.9134 -> SCALE = -16.9134 / ln(0.5) =
# 24.4008. Confirmed this restores median normalized score to ~0.50 across
# the 80-athlete cohort -- see the offline calibration check referenced in
# the recalibration commit for the full before/after tier distribution.
#
# Still not a validated-against-real-lab-data calibration (no real assay
# ground truth exists for this MVP, same caveat as baseline.BIOMARKER_CV) --
# revisit whenever the dataset's sample-depth distribution changes again.
ANOMALY_SCORE_SCALE = 24.4008


def normalize_anomaly_score(raw_distance: float) -> float:
    return 1 - math.exp(-raw_distance / ANOMALY_SCORE_SCALE)


def mahalanobis_distance(
    posterior: Mapping[str, tuple[float, float]],
    sample: Mapping[str, float],
) -> float:
    """Diagonal-covariance Mahalanobis distance of `sample` from `posterior`.

    Args:
        posterior: biomarker -> (posterior_mean, posterior_var), as returned
            by `app.ml.baseline.update_posterior`. One entry per biomarker
            in `BIOMARKERS`.
        sample: biomarker -> observed value. One entry per biomarker in
            `BIOMARKERS`.

    Returns:
        The non-negative Mahalanobis distance under the independence
        assumption described in the module docstring.
    """
    squared_total = 0.0
    for biomarker in BIOMARKERS:
        mean, var = posterior[biomarker]
        if var <= 0:
            raise ValueError(f"posterior variance for {biomarker!r} must be positive")
        observed = sample[biomarker]
        squared_total += (observed - mean) ** 2 / var

    return math.sqrt(squared_total)


def rank_contributing_biomarkers(
    posterior: Mapping[str, tuple[float, float]],
    sample: Mapping[str, float],
) -> list[dict]:
    """Rank biomarkers by how much each contributed to the Mahalanobis distance.

    Computes the same per-biomarker squared z-score used inside
    `mahalanobis_distance` — (observed - mean)^2 / var — for every biomarker
    in `BIOMARKERS`, independently of that function (not calling it, since
    `mahalanobis_distance` only returns the aggregate scalar distance and
    doesn't expose the per-biomarker terms).

    Args:
        posterior: biomarker -> (posterior_mean, posterior_var), same shape
            as `mahalanobis_distance` expects.
        sample: biomarker -> observed value, same shape as
            `mahalanobis_distance` expects.

    Returns:
        A list of dicts, one per biomarker in `BIOMARKERS`:
            {"biomarker": str, "z_score_squared": float, "deviation_direction": "above" | "below"}
        sorted descending by `z_score_squared` (the biomarker that
        contributed most to the overall distance first). Ties are broken by
        `BIOMARKERS` tuple order (stable sort over the biomarkers built in
        that order). `deviation_direction` is `"above"` when the observed
        value is strictly greater than the posterior mean, `"below"`
        otherwise (including the exact-equal case, where z_score_squared is
        0 anyway).
    """
    entries = []
    for biomarker in BIOMARKERS:
        mean, var = posterior[biomarker]
        if var <= 0:
            raise ValueError(f"posterior variance for {biomarker!r} must be positive")
        observed = sample[biomarker]
        z_score_squared = (observed - mean) ** 2 / var
        entries.append(
            {
                "biomarker": biomarker,
                "z_score_squared": z_score_squared,
                "deviation_direction": "above" if observed > mean else "below",
            }
        )

    entries.sort(key=lambda entry: entry["z_score_squared"], reverse=True)
    return entries


def get_anomaly_score(athlete_id: int, db_session) -> dict:
    """Live computation of an athlete's current anomaly score against their
    personal Bayesian posterior. Pure computation, no DB writes — this is a
    building block for a later task that will persist results as Anomaly
    rows and implement the full GET /athletes/{id}/anomalies read path;
    it is not that endpoint's implementation.

    `anomaly_score` here is the RAW, unbounded Mahalanobis distance from
    `mahalanobis_distance` — NOT the normalized 0-1 value that
    `docs/api-contract.md`'s `AnomalyDetail.anomaly_score` specifies for the
    persisted/contract field. Normalizing it (if needed) is the
    responsibility of whatever later persists this into an `Anomaly` row;
    it is not done here.

    Returns:
        On success: {"athlete_id": athlete_id, "anomaly_score": float,
        "reason": None, "contributing_biomarkers": list[dict]} — the latter
        as returned by `rank_contributing_biomarkers`.

        When the athlete has no samples yet, `compute_current_posterior`
        raises (unknown athlete or missing `baseline_prior_json`), or any
        posterior variance is 0/missing for a biomarker the score would
        need: {"athlete_id": athlete_id, "anomaly_score": None,
        "reason": "insufficient_history", "contributing_biomarkers": []}.
        No exception propagates out of this function.
    """
    insufficient_history = {
        "athlete_id": athlete_id,
        "anomaly_score": None,
        "reason": "insufficient_history",
        "contributing_biomarkers": [],
    }

    try:
        posterior = compute_current_posterior(athlete_id, db_session)
    except ValueError:
        return insufficient_history

    latest_sample = (
        db_session.query(Sample)
        .filter(Sample.athlete_id == athlete_id)
        .order_by(Sample.date.desc())
        .first()
    )
    if latest_sample is None:
        return insufficient_history

    sample = {biomarker: getattr(latest_sample, biomarker) for biomarker in BIOMARKERS}

    try:
        anomaly_score = mahalanobis_distance(posterior, sample)
        contributing_biomarkers = rank_contributing_biomarkers(posterior, sample)
    except ValueError:
        return insufficient_history

    return {
        "athlete_id": athlete_id,
        "anomaly_score": anomaly_score,
        "reason": None,
        "contributing_biomarkers": contributing_biomarkers,
    }
