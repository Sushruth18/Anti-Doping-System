import math
from datetime import date
from unittest.mock import Mock

import pytest

from app.db.models import Sample
from app.ml.anomaly import get_anomaly_score, mahalanobis_distance, rank_contributing_biomarkers

# Posterior/sample fixture shared by the get_anomaly_score tests below,
# reusing the sqrt(14) hand-computable values from
# test_mahalanobis_distance_hand_computable_case and the resulting ranking
# order from test_rank_contributing_biomarkers_orders_by_squared_z_score_descending.
_VALID_POSTERIOR = {
    "hb": (14.0, 0.25),
    "hct": (42.0, 4.0),
    "ret_pct": (1.0, 0.01),
    "off_score": (80.0, 16.0),
    "te_ratio": (1.3, 0.09),
}


def _make_sample(athlete_id: int) -> Sample:
    return Sample(
        id=1,
        athlete_id=athlete_id,
        date=date(2026, 3, 1),
        hb=15.0,
        hct=44.0,
        ret_pct=1.2,
        off_score=88.0,
        te_ratio=1.6,
        competition_flag=False,
        altitude_flag=False,
        injury_flag=False,
    )


def _mock_db_session_returning_sample(sample):
    db_session = Mock()
    db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = sample
    return db_session


def test_mahalanobis_distance_hand_computable_case():
    # Per-biomarker (mean, var) posterior and a sample chosen so each term
    # (observed - mean)^2 / var comes out to a round number:
    #   hb:        (15.0 - 14.0)^2 / 0.25 = 1.00 / 0.25 =  4
    #   hct:       (44.0 - 42.0)^2 / 4.00 = 4.00 / 4.00 =  1
    #   ret_pct:   (1.2  - 1.0 )^2 / 0.01 = 0.04 / 0.01 =  4
    #   off_score: (88.0 - 80.0)^2 / 16.0 = 64.0 / 16.0 =  4
    #   te_ratio:  (1.6  - 1.3 )^2 / 0.09 = 0.09 / 0.09 =  1
    # sum = 14 -> distance = sqrt(14)
    posterior = {
        "hb": (14.0, 0.25),
        "hct": (42.0, 4.0),
        "ret_pct": (1.0, 0.01),
        "off_score": (80.0, 16.0),
        "te_ratio": (1.3, 0.09),
    }
    sample = {
        "hb": 15.0,
        "hct": 44.0,
        "ret_pct": 1.2,
        "off_score": 88.0,
        "te_ratio": 1.6,
    }

    distance = mahalanobis_distance(posterior, sample)

    assert distance == pytest.approx(math.sqrt(14))


def test_mahalanobis_distance_zero_when_sample_matches_mean():
    posterior = {
        "hb": (14.0, 0.25),
        "hct": (42.0, 4.0),
        "ret_pct": (1.0, 0.01),
        "off_score": (80.0, 16.0),
        "te_ratio": (1.3, 0.09),
    }
    sample = {biomarker: mean for biomarker, (mean, _var) in posterior.items()}

    assert mahalanobis_distance(posterior, sample) == pytest.approx(0.0)


def test_mahalanobis_distance_raises_on_nonpositive_variance():
    posterior = {
        "hb": (14.0, 0.0),
        "hct": (42.0, 4.0),
        "ret_pct": (1.0, 0.01),
        "off_score": (80.0, 16.0),
        "te_ratio": (1.3, 0.09),
    }
    sample = {
        "hb": 14.0,
        "hct": 42.0,
        "ret_pct": 1.0,
        "off_score": 80.0,
        "te_ratio": 1.3,
    }

    with pytest.raises(ValueError):
        mahalanobis_distance(posterior, sample)


def test_rank_contributing_biomarkers_orders_by_squared_z_score_descending():
    # Same posterior/sample fixture as the sqrt(14) hand-computable case
    # above. The squared z-scores are mathematically 4, 1, 4, 4, 1 for
    # hb/hct/ret_pct/off_score/te_ratio respectively, but IEEE-754 float
    # division doesn't land exactly on 4.0/1.0 for every term — e.g.
    # (1.2 - 1.0) ** 2 / 0.01 evaluates to 3.999999999999998, not 4.0, and
    # (1.6 - 1.3) ** 2 / 0.09 evaluates to 1.0000000000000002, not 1.0
    # (verified via direct computation). So the "tie" groups aren't exact
    # ties in floating point, and BIOMARKERS-tuple-order tie-breaking never
    # actually kicks in for this fixture — descending sort on the true
    # float values already produces a unique, deterministic order:
    #   hb (4.0) > off_score (4.0, exact) > ret_pct (~3.999999999999998)
    #   > te_ratio (~1.0000000000000002) > hct (1.0, exact)
    # hb and off_score both hit exact 4.0 in float64 (integer numerator/
    # denominator with clean binary representations), so that pair *is* a
    # genuine tie, broken by BIOMARKERS order (hb before off_score).
    posterior = {
        "hb": (14.0, 0.25),
        "hct": (42.0, 4.0),
        "ret_pct": (1.0, 0.01),
        "off_score": (80.0, 16.0),
        "te_ratio": (1.3, 0.09),
    }
    sample = {
        "hb": 15.0,
        "hct": 44.0,
        "ret_pct": 1.2,
        "off_score": 88.0,
        "te_ratio": 1.6,
    }

    ranked = rank_contributing_biomarkers(posterior, sample)

    assert [entry["biomarker"] for entry in ranked] == [
        "hb",
        "off_score",
        "ret_pct",
        "te_ratio",
        "hct",
    ]
    assert [entry["z_score_squared"] for entry in ranked] == pytest.approx(
        [4.0, 4.0, 4.0, 1.0, 1.0]
    )
    # All five sample values are above their posterior mean in this fixture.
    assert all(entry["deviation_direction"] == "above" for entry in ranked)


def test_get_anomaly_score_happy_path(monkeypatch):
    # Same posterior/sample as the sqrt(14) fixture above, so anomaly_score
    # is hand-computable as sqrt(14), and the ranked contributing_biomarkers
    # order is the same deterministic order established in
    # test_rank_contributing_biomarkers_orders_by_squared_z_score_descending:
    # hb, off_score, ret_pct, te_ratio, hct.
    monkeypatch.setattr(
        "app.ml.anomaly.compute_current_posterior",
        lambda athlete_id, db_session: _VALID_POSTERIOR,
    )
    db_session = _mock_db_session_returning_sample(_make_sample(athlete_id=7))

    result = get_anomaly_score(7, db_session)

    assert result["athlete_id"] == 7
    assert result["reason"] is None
    assert result["anomaly_score"] == pytest.approx(math.sqrt(14))
    assert [b["biomarker"] for b in result["contributing_biomarkers"]] == [
        "hb",
        "off_score",
        "ret_pct",
        "te_ratio",
        "hct",
    ]

    # No DB writes should happen — get_anomaly_score is pure computation;
    # DB writes belong in the route layer.
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()


def test_get_anomaly_score_zero_samples_returns_insufficient_history(monkeypatch):
    monkeypatch.setattr(
        "app.ml.anomaly.compute_current_posterior",
        lambda athlete_id, db_session: _VALID_POSTERIOR,
    )
    db_session = _mock_db_session_returning_sample(None)

    result = get_anomaly_score(3, db_session)

    assert result == {
        "athlete_id": 3,
        "anomaly_score": None,
        "reason": "insufficient_history",
        "contributing_biomarkers": [],
    }
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()


def test_get_anomaly_score_compute_current_posterior_raises_returns_insufficient_history(
    monkeypatch,
):
    # e.g. unknown athlete or missing baseline_prior_json, per
    # compute_current_posterior's own documented ValueError cases.
    def _raise(athlete_id, db_session):
        raise ValueError("athlete not found or has no baseline_prior_json")

    monkeypatch.setattr("app.ml.anomaly.compute_current_posterior", _raise)
    db_session = _mock_db_session_returning_sample(_make_sample(athlete_id=5))

    result = get_anomaly_score(5, db_session)

    assert result == {
        "athlete_id": 5,
        "anomaly_score": None,
        "reason": "insufficient_history",
        "contributing_biomarkers": [],
    }
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()


def test_get_anomaly_score_zero_variance_returns_insufficient_history_not_raises(monkeypatch):
    posterior_with_zero_variance = {
        "hb": (14.0, 0.0),  # new athlete with too little history -> 0 variance
        "hct": (42.0, 4.0),
        "ret_pct": (1.0, 0.01),
        "off_score": (80.0, 16.0),
        "te_ratio": (1.3, 0.09),
    }
    monkeypatch.setattr(
        "app.ml.anomaly.compute_current_posterior",
        lambda athlete_id, db_session: posterior_with_zero_variance,
    )
    db_session = _mock_db_session_returning_sample(_make_sample(athlete_id=9))

    result = get_anomaly_score(9, db_session)

    assert result == {
        "athlete_id": 9,
        "anomaly_score": None,
        "reason": "insufficient_history",
        "contributing_biomarkers": [],
    }
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()
