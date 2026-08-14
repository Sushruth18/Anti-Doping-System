import pytest

from app.ml.baseline import update_posterior


def test_equal_variance_averages_evenly():
    # Equal precisions -> posterior_mean is the plain average of prior_mean
    # and obs; posterior_precision = 1/1 + 1/1 = 2 -> posterior_var = 0.5.
    # (10*1 + 12*1) / 2 = 11.0
    mean, var = update_posterior(prior_mean=10.0, prior_var=1.0, obs=12.0, obs_var=1.0)

    assert mean == pytest.approx(11.0)
    assert var == pytest.approx(0.5)


def test_asymmetric_variance_weights_toward_lower_variance_input():
    # prior_precision = 1/0.36 = 25/9, obs_precision = 1/0.25 = 4
    # posterior_precision = 25/9 + 4 = 61/9 -> posterior_var = 9/61
    # posterior_mean = (14.3*25/9 + 15.5*4) / (61/9) = 915.5/61
    mean, var = update_posterior(prior_mean=14.3, prior_var=0.36, obs=15.5, obs_var=0.25)

    assert mean == pytest.approx(915.5 / 61)
    assert var == pytest.approx(9 / 61)
    # obs has lower variance (more precision) than prior, so the posterior
    # mean should land closer to obs (15.5) than to prior_mean (14.3).
    assert abs(mean - 15.5) < abs(mean - 14.3)


def test_observation_matches_prior_mean_shrinks_variance_without_moving_mean():
    # prior_precision = 1/4 = 0.25, obs_precision = 1/1 = 1
    # posterior_precision = 1.25 -> posterior_var = 0.8
    # posterior_mean = (100*0.25 + 100*1) / 1.25 = 100.0
    mean, var = update_posterior(prior_mean=100.0, prior_var=4.0, obs=100.0, obs_var=1.0)

    assert mean == pytest.approx(100.0)
    assert var == pytest.approx(0.8)
    assert var < 4.0  # posterior is always more confident than the prior alone
