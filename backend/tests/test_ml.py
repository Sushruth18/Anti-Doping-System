import pytest

from app.ml.baseline import update_posterior
from app.ml.cusum import compute_cusum


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


def test_cusum_flat_series_does_not_trigger():
    # Every observation equals the baseline mean, so z_i = 0 for all i.
    # C+_i = max(0, C+_{i-1} + 0 - k) and C-_i = max(0, C-_{i-1} - 0 - k):
    # both terms inside max() are <= -k < 0, so both sums are clamped to 0
    # at every step and never accumulate, regardless of how long the series
    # runs.
    observations = [10.0] * 30

    result = compute_cusum(observations, baseline_mean=10.0, baseline_std=1.0, k=0.5, h=5.0)

    assert result["cusum_upper"] == [0.0] * 30
    assert result["cusum_lower"] == [0.0] * 30
    assert result["flagged"] is False
    assert result["flagged_at_index"] is None
    assert result["threshold"] == 5.0


def test_cusum_catches_sustained_drift_invisible_to_single_sample_zscore():
    # EPO micro-dosing blind spot: every sample sits only 0.3 std above
    # baseline, sustained across many draws. A single-sample z-score > 2
    # threshold never fires (0.3 < 2 on every single observation), but the
    # small deviation is directional and never decays, so CUSUM's running
    # sum eventually crosses the decision threshold.
    #
    # z_i = (10.3 - 10.0) / 1.0 = 0.3 for every i.
    # C+_i = max(0, C+_{i-1} + 0.3 - k), k = 0.2 -> C+_i = C+_{i-1} + 0.1
    # (the +0.1 net increment is always positive once C+_0 > 0, so it never
    # clamps back to 0 after the first step): C+_i = 0.1 * (i + 1).
    # C+_i > h = 2.05  =>  0.1*(i+1) > 2.05  =>  i >= 20 (0-indexed):
    #   C+_19 = 0.1*20 = 2.0   (not > 2.05, not yet flagged)
    #   C+_20 = 0.1*21 = 2.1   (> 2.05, flags here)
    # (h is set to 2.05, half a step off the exact 2.0 boundary, so the
    # flag index is robust to the float64 rounding error that repeated
    # 0.1 additions accumulate — it would otherwise land the crossing on
    # either side of an exact 2.0 depending on rounding direction.)
    #
    # C-_i = max(0, C-_{i-1} - 0.3 - 0.2) = max(0, C-_{i-1} - 0.5) = 0
    # always, since the drift is one-directional (upward only).
    k = 0.2
    h = 2.05
    baseline_mean = 10.0
    baseline_std = 1.0
    drift = 0.3
    observations = [baseline_mean + drift] * 25

    # The blind spot: no single observation's z-score comes anywhere near
    # a conventional 2-std-dev anomaly threshold.
    single_sample_z_scores = [(x - baseline_mean) / baseline_std for x in observations]
    assert max(abs(z) for z in single_sample_z_scores) < 2.0

    result = compute_cusum(observations, baseline_mean=baseline_mean, baseline_std=baseline_std, k=k, h=h)

    assert result["cusum_upper"][0] == pytest.approx(0.1)
    assert result["cusum_upper"][19] == pytest.approx(2.0)
    assert result["cusum_upper"][20] == pytest.approx(2.1)
    assert result["cusum_lower"] == [0.0] * 25
    assert result["flagged"] is True
    assert result["flagged_at_index"] == 20
    assert result["threshold"] == 2.05
