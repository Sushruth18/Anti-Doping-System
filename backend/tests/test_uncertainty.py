import pytest

from app.ml.uncertainty import compute_athlete_uncertainty_score, compute_uncertainty_score


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


# Reference values below are pulled from the seeded 80-athlete cohort
# (`compute_current_posterior` + `rank_contributing_biomarkers` for each
# athlete's current posterior and latest sample) rather than invented, per
# the investigation into aggregation approaches (mean vs. max vs.
# z²-weighted) that motivated `compute_athlete_uncertainty_score`.


def test_compute_athlete_uncertainty_score_taylor_gomez():
    # Athlete 4, Taylor Gomez: z² is fairly spread across biomarkers (no
    # single dominant driver), so the weighted aggregate sits below the
    # simple mean (~0.0599) since the low-uncertainty biomarkers (hb, hct)
    # happen to carry more of the weight than te_ratio (the highest
    # per-biomarker score) does.
    per_biomarker_scores = {
        "hb": 0.027711439339524382,
        "hct": 0.025631183127985464,
        "ret_pct": 0.04761904761904761,
        "off_score": 0.04314595171623506,
        "te_ratio": 0.15563361253715213,
    }
    z_score_squared_by_biomarker = {
        "hb": 0.7195150687656361,
        "hct": 0.419447665501568,
        "ret_pct": 0.0558862433862454,
        "off_score": 0.5017471629737311,
        "te_ratio": 0.014569948349709634,
    }
    result = compute_athlete_uncertainty_score(per_biomarker_scores, z_score_squared_by_biomarker)
    assert result == pytest.approx(0.03346660544910412)


def test_compute_athlete_uncertainty_score_logan_rossi():
    # Athlete 44, Logan Rossi: identical per-biomarker uncertainty scores to
    # Taylor Gomez (same n=5 sample count, same prior-generation bucket),
    # but a very different z² profile (ret_pct/off_score dominate here
    # instead of hb). A plain mean would give Taylor and Logan the same
    # aggregate (~0.0599) despite this difference; z²-weighting is the
    # whole reason this function exists instead of just averaging.
    per_biomarker_scores = {
        "hb": 0.027711439339524382,
        "hct": 0.025631183127985464,
        "ret_pct": 0.04761904761904761,
        "off_score": 0.04314595171623506,
        "te_ratio": 0.15563361253715213,
    }
    z_score_squared_by_biomarker = {
        "hb": 0.19388649238621725,
        "hct": 2.587586420961053,
        "ret_pct": 6.435267857142819,
        "off_score": 5.348459887193541,
        "te_ratio": 1.0024628788964882,
    }
    result = compute_athlete_uncertainty_score(per_biomarker_scores, z_score_squared_by_biomarker)
    assert result == pytest.approx(0.04913508126939056)

    # Same per-biomarker scores as Taylor Gomez, but a different aggregate —
    # confirms the weighting (not just the inputs) drives the result.
    taylor_result = compute_athlete_uncertainty_score(
        per_biomarker_scores,
        {
            "hb": 0.7195150687656361,
            "hct": 0.419447665501568,
            "ret_pct": 0.0558862433862454,
            "off_score": 0.5017471629737311,
            "te_ratio": 0.014569948349709634,
        },
    )
    assert result != pytest.approx(taylor_result)


def test_compute_athlete_uncertainty_score_indigo_berg():
    # Athlete 65, Indigo Berg: hb/hct z² are both >100 (huge outlier on this
    # sample for those two biomarkers), dwarfing te_ratio's z² of ~0.43 even
    # though te_ratio has by far the highest per-biomarker uncertainty
    # score (0.164). The weighted aggregate stays low (~0.033) because it's
    # pulled toward hb/hct's low uncertainty scores (~0.030), not te_ratio's
    # high one — the opposite of what a max-based aggregate would report.
    per_biomarker_scores = {
        "hb": 0.03017337026885053,
        "hct": 0.030065497715575876,
        "ret_pct": 0.04562164200207372,
        "off_score": 0.04537584884544867,
        "te_ratio": 0.16389358037491011,
    }
    z_score_squared_by_biomarker = {
        "hb": 119.71065738041449,
        "hct": 110.65027693384904,
        "ret_pct": 2.3028218759459103,
        "off_score": 56.96623080606069,
        "te_ratio": 0.42920608033172103,
    }
    result = compute_athlete_uncertainty_score(per_biomarker_scores, z_score_squared_by_biomarker)
    assert result == pytest.approx(0.03343842768976375)


def test_compute_athlete_uncertainty_score_falls_back_to_mean_when_all_z2_zero():
    # Every z_score_squared is 0 (sample lands exactly on the posterior
    # mean for every biomarker) -- weights would be 0/0, so this falls back
    # to a plain mean instead.
    per_biomarker_scores = {"hb": 0.2, "hct": 0.4, "ret_pct": 0.6, "off_score": 0.8, "te_ratio": 1.0}
    z_score_squared_by_biomarker = {b: 0.0 for b in per_biomarker_scores}

    result = compute_athlete_uncertainty_score(per_biomarker_scores, z_score_squared_by_biomarker)
    assert result == pytest.approx(0.6)  # mean(0.2, 0.4, 0.6, 0.8, 1.0)
