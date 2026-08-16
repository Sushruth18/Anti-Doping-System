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
