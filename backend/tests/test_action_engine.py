import json
import os
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Athlete, Sample
from app.db.session import Base
from app.ml.action_engine import (
    compute_recommendation,
    compute_value_score,
    normalize_value_scores_for_display,
    select_action_tier,
)

# Real seeded dataset, same files `app.db.seed.seed()` reads -- the
# hand-computed reference values below are for the actual Taylor
# Gomez/Logan Rossi/Indigo Berg rows in this data, not synthetic fixtures,
# so the tests load the same files rather than fabricating athletes.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ATHLETES_PATH = os.path.join(_REPO_ROOT, "data", "athletes.json")
_SAMPLES_PATH = os.path.join(_REPO_ROOT, "data", "samples.json")


@pytest.fixture()
def seeded_db(tmp_path):
    db_path = tmp_path / "action_engine_test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with open(_ATHLETES_PATH, "r", encoding="utf-8") as f:
        athletes_data = json.load(f)
    with open(_SAMPLES_PATH, "r", encoding="utf-8") as f:
        samples_data = json.load(f)

    db = TestingSessionLocal()
    try:
        for row in athletes_data:
            db.add(Athlete(**row))
        for row in samples_data:
            row = dict(row)
            row["date"] = datetime.strptime(row["date"], "%Y-%m-%d").date()
            db.add(Sample(**row))
        db.commit()

        yield db
    finally:
        db.close()
        engine.dispose()


# --- select_action_tier -----------------------------------------------


@pytest.mark.parametrize(
    "anomaly_score_normalized,expected_action_type",
    [
        (0.0, "no_action"),
        (0.29999, "no_action"),
        (0.30, "increase_monitoring"),  # lower bound is inclusive
        (0.54999, "increase_monitoring"),
        (0.55, "target_test"),
        (0.69999, "target_test"),
        (0.70, "biological_passport_review"),
        (0.84999, "biological_passport_review"),
        (0.85, "open_case"),
        (1.0, "open_case"),
    ],
)
def test_select_action_tier_boundaries(anomaly_score_normalized, expected_action_type):
    tier = select_action_tier(anomaly_score_normalized)
    assert tier["action_type"] == expected_action_type


# --- compute_value_score -------------------------------------------------


def test_compute_value_score_increase_monitoring_tier():
    # anomaly=0.3260226578956815, uncertainty=0.04913508126939056,
    # sensitivity=0.3 (increase_monitoring), cost=1.0
    # value_score = 0.3260226578956815 * 0.04913508126939056 * 0.3 / 1.0
    result = compute_value_score(
        anomaly_score_normalized=0.3260226578956815,
        uncertainty_score=0.04913508126939056,
        sensitivity=0.3,
        cost=1.0,
    )
    assert result == pytest.approx(0.004805744937410108)


def test_compute_value_score_biological_passport_review_tier():
    # anomaly=0.8178841807108579, uncertainty=0.03343842768976375,
    # sensitivity=0.85 (biological_passport_review), cost=5.0
    # value_score = 0.8178841807108579 * 0.03343842768976375 * 0.85 / 5.0
    result = compute_value_score(
        anomaly_score_normalized=0.8178841807108579,
        uncertainty_score=0.03343842768976375,
        sensitivity=0.85,
        cost=5.0,
    )
    assert result == pytest.approx(0.004649289376001287)


# --- compute_recommendation, real seeded athletes -------------------------
#
# Reference anomaly_score/uncertainty_score values are the live
# get_anomaly_score()/compute_athlete_uncertainty_score() output already
# confirmed against this exact dataset in the preceding investigation.


def test_compute_recommendation_taylor_gomez_no_action(seeded_db):
    # anomaly_score_normalized = 0.1226168959151116 < 0.30 -> no_action,
    # value_score/cost forced to 0.0 (no_action never reaches
    # compute_value_score -- see ACTION_TIERS' cost=None/sensitivity=None
    # for this tier).
    rec = compute_recommendation(4, seeded_db)

    assert rec is not None
    assert rec["athlete_id"] == 4
    assert rec["action_type"] == "no_action"
    assert rec["anomaly_score"] == pytest.approx(0.1226168959151116)
    assert rec["uncertainty_score"] == pytest.approx(0.03346660544910412)
    assert rec["value_score"] == pytest.approx(0.0)
    assert rec["cost"] == pytest.approx(0.0)


def test_compute_recommendation_logan_rossi_increase_monitoring(seeded_db):
    # anomaly_score_normalized = 0.3260226578956815, in [0.30, 0.55) ->
    # increase_monitoring (cost=1.0, sensitivity=0.3).
    # value_score = 0.3260226578956815 * 0.04913508126939056 * 0.3 / 1.0
    #             = 0.004805744937410108
    rec = compute_recommendation(44, seeded_db)

    assert rec is not None
    assert rec["athlete_id"] == 44
    assert rec["action_type"] == "increase_monitoring"
    assert rec["anomaly_score"] == pytest.approx(0.3260226578956815)
    assert rec["uncertainty_score"] == pytest.approx(0.04913508126939056)
    assert rec["value_score"] == pytest.approx(0.004805744937410108)
    assert rec["cost"] == pytest.approx(1.0)


def test_compute_recommendation_indigo_berg_biological_passport_review(seeded_db):
    # anomaly_score_normalized = 0.8178841807108579, in [0.70, 0.85) ->
    # biological_passport_review (cost=5.0, sensitivity=0.85).
    # value_score = 0.8178841807108579 * 0.03343842768976375 * 0.85 / 5.0
    #             = 0.004649289376001287
    rec = compute_recommendation(65, seeded_db)

    assert rec is not None
    assert rec["athlete_id"] == 65
    assert rec["action_type"] == "biological_passport_review"
    assert rec["anomaly_score"] == pytest.approx(0.8178841807108579)
    assert rec["uncertainty_score"] == pytest.approx(0.03343842768976375)
    assert rec["value_score"] == pytest.approx(0.004649289376001287)
    assert rec["cost"] == pytest.approx(5.0)


def test_compute_recommendation_unscored_athlete_returns_none(seeded_db):
    athlete = Athlete(name="No Samples Athlete", sport="Cycling", age=25)
    seeded_db.add(athlete)
    seeded_db.commit()
    seeded_db.refresh(athlete)

    assert compute_recommendation(athlete.id, seeded_db) is None


# --- normalize_value_scores_for_display -----------------------------------


def test_normalize_value_scores_for_display_min_max():
    result = normalize_value_scores_for_display([0.0, 0.005, 0.01])
    assert result == pytest.approx([0.0, 0.5, 1.0])


def test_normalize_value_scores_for_display_all_equal_avoids_div_by_zero():
    assert normalize_value_scores_for_display([0.3, 0.3, 0.3]) == [0.0, 0.0, 0.0]


def test_normalize_value_scores_for_display_empty_list():
    assert normalize_value_scores_for_display([]) == []
