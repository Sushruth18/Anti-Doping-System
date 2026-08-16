"""Uncertainty scoring from an athlete's per-biomarker posterior variance.

Normalizes a biomarker's posterior variance (from
`app.ml.baseline.compute_current_posterior`) into a 0-1 uncertainty score,
relative to that same biomarker's prior variance rather than a fixed,
cross-biomarker scale constant. This avoids the recalibration problem
`anomaly.ANOMALY_SCORE_SCALE` has (a single magic constant that has to be
separately right for every biomarker despite their prior variances spanning
very different absolute ranges, e.g. off_score ~O(100) vs te_ratio ~O(0.1)).

Formerly degenerate, now resolved: `baseline.py` used to scale `obs_var` as
a fixed fraction of each biomarker's own `prior_var`
(`OBS_VAR_STD_FRACTION`), which made `posterior_var / prior_var` reduce
algebraically to a function of sample count `n` alone -- `prior_var`
canceled out completely, so every athlete/biomarker with the same `n`
produced the identical uncertainty score regardless of actual observed
values. `baseline.py` now derives `obs_var` from each biomarker's
analytical CV and prior *mean* instead (`compute_obs_var`,
`BIOMARKER_CV`), which doesn't cancel against `prior_var` the same way --
confirmed empirically across the 80 seeded athletes: 23 distinct ratio
values (not 1), spanning ~0.026-0.189.
"""

from __future__ import annotations

from typing import Mapping


def compute_uncertainty_score(posterior_variance: float, prior_variance: float) -> float:
    """Normalize posterior variance to a 0-1 uncertainty score, relative to
    the same biomarker's prior variance.

    Interpretation: `posterior_variance / prior_variance` is the fraction of
    the athlete's original (zero-sample) uncertainty for this biomarker that
    remains after folding in their observed samples via
    `app.ml.baseline.compute_current_posterior`. Because the conjugate
    Normal-Normal update in `baseline.update_posterior` only ever increases
    precision (never decreases it), `posterior_variance` is bounded in
    `(0, prior_variance]` for an athlete with a valid posterior, so this
    ratio is naturally bounded in `(0, 1]` before clipping — the `clip` here
    is a defensive floor/ceiling, not evidence this ratio is expected to
    exceed those bounds in normal operation.

    Boundary behavior:
        - Zero samples: `posterior_variance == prior_variance`, ratio is
          `1.0` -> maximally uncertain (no evidence yet beyond the prior).
        - Many samples / fully converged: `posterior_variance -> 0` as
          precision accumulates without bound, ratio -> `0.0` -> minimally
          uncertain (posterior tightly concentrated around its mean).

    Args:
        posterior_variance: the biomarker's current posterior variance, as
            returned by `compute_current_posterior`. Expected to be positive
            and at most `prior_variance` in normal operation (see above).
        prior_variance: the same biomarker's prior variance (i.e.
            `prior_std ** 2` from `Athlete.baseline_prior_json`), used as
            the normalizing scale. Must be strictly positive: a prior with
            zero or negative variance is a degenerate/invalid baseline and
            cannot serve as a normalization scale.

    Raises:
        ValueError: if `prior_variance <= 0`. This mirrors the same guard
            `baseline.update_posterior` and `anomaly.mahalanobis_distance`
            already apply to variances elsewhere in this codebase — a
            non-positive variance is treated as invalid input to reject,
            not a degenerate case to silently absorb.

    Returns:
        `posterior_variance / prior_variance`, clipped to `[0, 1]`.
    """
    if prior_variance <= 0:
        raise ValueError("prior_variance must be positive")

    ratio = posterior_variance / prior_variance
    return max(0.0, min(1.0, ratio))


def compute_athlete_uncertainty_score(
    per_biomarker_scores: Mapping[str, float],
    z_score_squared_by_biomarker: Mapping[str, float],
) -> float:
    """Aggregate an athlete's per-biomarker uncertainty scores (each from
    `compute_uncertainty_score`) into the single athlete-level score the
    API contract's `AthleteListItem.latest_uncertainty_score` and
    `Recommendation.uncertainty_score` fields expect.

    Weighted by each biomarker's `z_score_squared` contribution to that
    same sample's anomaly score (the same values
    `app.ml.anomaly.rank_contributing_biomarkers` produces), rather than a
    plain mean: an investigation compared a plain mean, a max, and this
    weighted approach across the seeded cohort and found the plain mean
    collapsed athletes with very different anomaly profiles onto the same
    aggregate (their five per-biomarker scores were nearly identical), and
    max was dominated by `te_ratio` for essentially every athlete
    (`te_ratio`'s CV is structurally higher than the other biomarkers', not
    because it's usually the anomalous one). Weighting by z² ties the
    aggregate to which biomarkers actually drove that athlete's anomaly
    score, so two athletes with the same per-biomarker uncertainty scores
    but different anomaly drivers get different aggregates.

    Args:
        per_biomarker_scores: biomarker -> `compute_uncertainty_score`
            output. One entry per biomarker.
        z_score_squared_by_biomarker: biomarker -> `z_score_squared`, as
            produced by `app.ml.anomaly.rank_contributing_biomarkers` for
            the same athlete and sample `per_biomarker_scores` was computed
            from. Must have an entry for every key in `per_biomarker_scores`.

    Returns:
        The z²-weighted average of `per_biomarker_scores`. Falls back to a
        plain (unweighted) mean when every `z_score_squared` is 0 (e.g. a
        sample that lands exactly on the posterior mean for every
        biomarker), since weights would otherwise all be 0/0.
    """
    total_z2 = sum(z_score_squared_by_biomarker[biomarker] for biomarker in per_biomarker_scores)

    if total_z2 <= 0:
        return sum(per_biomarker_scores.values()) / len(per_biomarker_scores)

    return sum(
        score * (z_score_squared_by_biomarker[biomarker] / total_z2)
        for biomarker, score in per_biomarker_scores.items()
    )
