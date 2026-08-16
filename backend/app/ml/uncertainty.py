"""Uncertainty scoring from an athlete's per-biomarker posterior variance.

Normalizes a biomarker's posterior variance (from
`app.ml.baseline.compute_current_posterior`) into a 0-1 uncertainty score,
relative to that same biomarker's prior variance rather than a fixed,
cross-biomarker scale constant. This avoids the recalibration problem
`anomaly.ANOMALY_SCORE_SCALE` has (a single magic constant that has to be
separately right for every biomarker despite their prior variances spanning
very different absolute ranges, e.g. off_score ~O(100) vs te_ratio ~O(0.1)).

Known limitation, current seed data: the resulting score is currently
degenerate. `baseline.OBS_VAR_STD_FRACTION` scales `obs_var` as a fixed
fraction of `prior_var` (`obs_var = (OBS_VAR_STD_FRACTION * prior_std) ** 2`),
which makes `posterior_var / prior_var` reduce algebraically to `1 / (1 +
n / OBS_VAR_STD_FRACTION**2)` -- a function of sample count `n` alone, with
`prior_var` canceling out completely. Combined with every seeded athlete
having the same `n=5` sample count, every athlete/biomarker currently
produces the identical uncertainty score regardless of actual observed
values. This is a known limitation of `baseline.py`'s `OBS_VAR_STD_FRACTION`
placeholder, not a bug in this file -- revisit once real per-biomarker
measurement noise variances and/or varied sample counts are available.
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
