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

BIOMARKERS = ("hb", "hct", "ret_pct", "off_score", "te_ratio")


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
