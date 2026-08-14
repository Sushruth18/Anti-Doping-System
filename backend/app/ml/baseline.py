"""Ported from ml/prototype_baseline.py::update_posterior (Dev 2, validated
via that script's validate_convergence() — see CLAUDE.md's app/ml/ vs /ml
note: this is a copy of the validated math, not a live import from /ml).
"""

from __future__ import annotations


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
