import pytest

from app.ml.uncertainty import compute_uncertainty_score


def test_compute_uncertainty_score_zero_samples_boundary():
    # posterior_var == prior_var (the zero-sample case: no evidence has
    # narrowed the posterior below the prior yet).
    # ratio = 0.36 / 0.36 = 1.0
    assert compute_uncertainty_score(posterior_variance=0.36, prior_variance=0.36) == pytest.approx(1.0)


def test_compute_uncertainty_score_converged_boundary():
    # posterior_var -> 0 (many samples folded in, precision has accumulated
    # far past the prior's).
    # ratio = 0.0001 / 0.36 = 0.0002777...
    # Not exactly 0.0 (posterior_var is asymptotic to 0, never exactly 0 for
    # a finite number of samples), but should be close to the 0.0 floor.
    assert compute_uncertainty_score(posterior_variance=0.0001, prior_variance=0.36) == pytest.approx(
        0.0002777777777777778
    )


def test_compute_uncertainty_score_mid_range_case():
    # Mid-range case: posterior_var = 0.09, prior_var = 0.36.
    # ratio = 0.09 / 0.36 = 0.25
    assert compute_uncertainty_score(posterior_variance=0.09, prior_variance=0.36) == pytest.approx(0.25)


def test_compute_uncertainty_score_raises_for_non_positive_prior_variance():
    # Same non-positive-variance guard convention as
    # baseline.update_posterior and anomaly.mahalanobis_distance elsewhere
    # in this codebase.
    with pytest.raises(ValueError):
        compute_uncertainty_score(posterior_variance=0.1, prior_variance=0.0)

    with pytest.raises(ValueError):
        compute_uncertainty_score(posterior_variance=0.1, prior_variance=-0.36)
