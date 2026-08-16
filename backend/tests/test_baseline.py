import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Athlete, Sample
from app.db.session import Base
from app.ml.baseline import (
    BIOMARKER_CV,
    BIOMARKERS,
    compute_current_posterior,
    compute_obs_var,
    fold_biomarker_posterior,
    update_posterior,
)
from datetime import date


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "test_baseline.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_fold_biomarker_posterior_yields_full_intermediate_sequence():
    # prior N(14.0, 0.36), obs_var = 0.0225 (obs noise fixed for both steps),
    # two observations folded in order: 15.0, then 15.5.
    #
    # step 1: prior_precision = 1/0.36 = 2.777...
    #         obs_precision    = 1/0.0225 = 44.444...
    #         posterior_precision = 47.222...
    #         posterior_var  = 1/47.222... = 0.021176470588235293
    #         posterior_mean = posterior_var * (14.0*2.777... + 15.0*44.444...)
    #                        = 14.941176470588234
    #
    # step 2: prior_precision = 1/0.021176470588235293 = 47.222...
    #         obs_precision    = 1/0.0225 = 44.444...
    #         posterior_precision = 91.666...
    #         posterior_var  = 1/91.666... = 0.01090909090909091
    #         posterior_mean = posterior_var * (14.941176470588234*47.222... + 15.5*44.444...)
    #                        = 15.212121212121213
    prior_mean, prior_var = 14.0, 0.36
    obs_var = 0.0225

    results = list(
        fold_biomarker_posterior(
            prior_mean,
            prior_var,
            [("day1", 15.0), ("day2", 15.5)],
            obs_var,
        )
    )

    assert [label for label, _mean, _var in results] == ["day1", "day2"]

    label1, mean1, var1 = results[0]
    assert mean1 == pytest.approx(14.941176470588234)
    assert var1 == pytest.approx(0.021176470588235293)

    label2, mean2, var2 = results[1]
    assert mean2 == pytest.approx(15.212121212121213)
    assert var2 == pytest.approx(0.01090909090909091)

    # Cross-check against direct update_posterior calls (independent of the
    # generator's own bookkeeping) to confirm the fold is doing exactly two
    # sequential update_posterior calls and nothing else.
    m, v = update_posterior(prior_mean, prior_var, 15.0, obs_var)
    m, v = update_posterior(m, v, 15.5, obs_var)
    assert (mean2, var2) == pytest.approx((m, v))


def test_fold_biomarker_posterior_yields_nothing_for_empty_samples():
    results = list(fold_biomarker_posterior(14.0, 0.36, [], 0.0225))
    assert results == []


def test_compute_current_posterior_hand_computed_hb_chain(db_session):
    # hb prior: mean=14.0, std=0.6 -> prior_var=0.36
    # obs_var = (BIOMARKER_CV["hb"] * prior_mean) ** 2
    #         = (0.018 * 14.0) ** 2 = 0.252 ** 2 = 0.063504
    # Two hb samples folded in date order: 15.0, then 15.5.
    #   step 1 -> mean=14.85005100306018,  var=0.0539816388983339
    #   step 2 -> mean=15.148685903326593, var=0.02917845984194082
    baseline_prior_json = json.dumps(
        {
            "hb": {"mean": 14.0, "std": 0.6},
            "hct": {"mean": 42.0, "std": 2.0},
            "ret_pct": {"mean": 1.0, "std": 0.2},
            "off_score": {"mean": 80.0, "std": 8.0},
            "te_ratio": {"mean": 1.3, "std": 0.3},
        }
    )
    athlete = Athlete(
        name="Test Athlete E",
        sport="Swimming",
        age=24,
        baseline_prior_json=baseline_prior_json,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    sample_rows = [
        (date(2026, 1, 1), 15.0, 43.0, 1.1, 85.0, 1.4),
        (date(2026, 1, 15), 15.5, 43.5, 1.15, 87.0, 1.45),
    ]
    for sample_date, hb, hct, ret_pct, off_score, te_ratio in sample_rows:
        db_session.add(
            Sample(
                athlete_id=athlete.id,
                date=sample_date,
                hb=hb,
                hct=hct,
                ret_pct=ret_pct,
                off_score=off_score,
                te_ratio=te_ratio,
                competition_flag=False,
                altitude_flag=False,
                injury_flag=False,
            )
        )
    db_session.commit()

    posterior = compute_current_posterior(athlete.id, db_session)

    assert set(posterior.keys()) == set(BIOMARKERS)

    hb_mean, hb_var = posterior["hb"]
    assert hb_mean == pytest.approx(15.148685903326593)
    assert hb_var == pytest.approx(0.02917845984194082)

    # Independently recompute the other four biomarkers via direct
    # update_posterior calls (not hand-derived by arithmetic a second time,
    # same approach as the trajectory endpoint test) to confirm
    # compute_current_posterior folds every biomarker, not just hb. Uses
    # compute_obs_var (the same function production code calls) rather than
    # re-deriving the CV/error-propagation arithmetic a second time here —
    # that arithmetic itself is covered separately below and in
    # test_compute_obs_var_*.
    baseline_data = json.loads(baseline_prior_json)
    for biomarker in BIOMARKERS:
        if biomarker == "hb":
            continue
        prior_entry = baseline_data[biomarker]
        prior_std = prior_entry["std"]
        obs_var = compute_obs_var(biomarker, baseline_data)
        mean, var = prior_entry["mean"], prior_std**2
        for _sample_date, hb, hct, ret_pct, off_score, te_ratio in sample_rows:
            observed = {
                "hct": hct,
                "ret_pct": ret_pct,
                "off_score": off_score,
                "te_ratio": te_ratio,
            }[biomarker]
            mean, var = update_posterior(mean, var, observed, obs_var)

        actual_mean, actual_var = posterior[biomarker]
        assert actual_mean == pytest.approx(mean)
        assert actual_var == pytest.approx(var)


def test_compute_current_posterior_raises_for_unknown_athlete(db_session):
    with pytest.raises(ValueError):
        compute_current_posterior(999999, db_session)


# Hand-computed obs_var reference cases, using the "typical athlete" baseline
# (median priors across the 80 seeded athletes, from the investigation
# report that preceded this change):
#   hb=14.90 (std=0.70), hct=44.00 (std=1.90), ret_pct=1.080 (std=0.270),
#   off_score=86.10 (std=9.50), te_ratio=1.100 (std=0.20)
_MEDIAN_ATHLETE_BASELINE = {
    "hb": {"mean": 14.9, "std": 0.70},
    "hct": {"mean": 44.0, "std": 1.90},
    "ret_pct": {"mean": 1.080, "std": 0.270},
    "off_score": {"mean": 86.1, "std": 9.50},
    "te_ratio": {"mean": 1.100, "std": 0.20},
}


def test_compute_obs_var_hb_median_athlete():
    # obs_var = (BIOMARKER_CV["hb"] * prior_mean) ** 2
    #         = (0.018 * 14.9) ** 2 = 0.2682 ** 2 = 0.07193124
    assert BIOMARKER_CV["hb"] == pytest.approx(0.018)
    obs_var = compute_obs_var("hb", _MEDIAN_ATHLETE_BASELINE)
    assert obs_var == pytest.approx(0.07193124)


def test_compute_obs_var_ret_pct_median_athlete():
    # obs_var = (BIOMARKER_CV["ret_pct"] * prior_mean) ** 2
    #         = (0.12 * 1.080) ** 2 = 0.1296 ** 2 = 0.01679616
    assert BIOMARKER_CV["ret_pct"] == pytest.approx(0.12)
    obs_var = compute_obs_var("ret_pct", _MEDIAN_ATHLETE_BASELINE)
    assert obs_var == pytest.approx(0.01679616)


def test_compute_obs_var_off_score_derived_via_error_propagation():
    # off_score has no direct CV entry — derived from hb's and ret_pct's own
    # obs_var via the error-propagation formula:
    #   Var(off_score) = 100 * Var(hb) + (900 / ret_pct_mean) * Var(ret_pct)
    #
    # var_hb  = 0.07193124  (from test_compute_obs_var_hb_median_athlete)
    # var_ret = 0.01679616  (from test_compute_obs_var_ret_pct_median_athlete)
    # ret_pct_mean = 1.080
    #
    # Var(off_score) = 100 * 0.07193124 + (900 / 1.080) * 0.01679616
    #                = 7.193124 + 833.33333... * 0.01679616
    #                = 7.193124 + 13.9968
    #                = 21.189924
    assert "off_score" not in BIOMARKER_CV  # not an independent CV entry
    obs_var = compute_obs_var("off_score", _MEDIAN_ATHLETE_BASELINE)
    assert obs_var == pytest.approx(21.189924)


def test_compute_obs_var_off_score_matches_manual_propagation_formula():
    # Cross-check against the propagation formula spelled out independently
    # (not calling compute_obs_var for the hb/ret_pct terms a second time),
    # to confirm the off_score branch is really doing 100*Var(hb) +
    # (900/ret_pct)*Var(ret_pct) and not some other combination.
    hb_mean = _MEDIAN_ATHLETE_BASELINE["hb"]["mean"]
    ret_mean = _MEDIAN_ATHLETE_BASELINE["ret_pct"]["mean"]
    var_hb = (BIOMARKER_CV["hb"] * hb_mean) ** 2
    var_ret = (BIOMARKER_CV["ret_pct"] * ret_mean) ** 2
    expected = 100 * var_hb + (900 / ret_mean) * var_ret

    obs_var = compute_obs_var("off_score", _MEDIAN_ATHLETE_BASELINE)
    assert obs_var == pytest.approx(expected)
