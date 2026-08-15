import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.backfill_anomalies import backfill_anomalies
from app.db.models import Anomaly, Athlete, Sample
from app.db.session import Base

_VALID_BASELINE_PRIOR_JSON = json.dumps(
    {
        "hb": {"mean": 14.0, "std": 0.6},
        "hct": {"mean": 42.0, "std": 1.8},
        "ret_pct": {"mean": 1.0, "std": 0.25},
        "off_score": {"mean": 80.0, "std": 9.0},
        "te_ratio": {"mean": 1.3, "std": 0.3},
    }
)


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
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


def _add_sample(db_session, athlete_id, sample_date):
    sample = Sample(
        athlete_id=athlete_id,
        date=sample_date,
        hb=15.0,
        hct=44.0,
        ret_pct=1.2,
        off_score=88.0,
        te_ratio=1.6,
        competition_flag=False,
        altitude_flag=False,
        injury_flag=False,
    )
    db_session.add(sample)
    db_session.commit()
    db_session.refresh(sample)
    return sample


def test_backfill_scores_athlete_with_valid_baseline_and_sample(db_session):
    athlete = Athlete(
        name="Scoreable Athlete",
        sport="Cycling",
        age=25,
        baseline_prior_json=_VALID_BASELINE_PRIOR_JSON,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    sample = _add_sample(db_session, athlete.id, date(2026, 3, 1))

    summary = backfill_anomalies(db_session)

    assert summary.scored == 1
    assert summary.total_athletes == 1
    anomalies = db_session.query(Anomaly).all()
    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly.sample_id == sample.id
    assert anomaly.athlete_id == athlete.id
    assert anomaly.method == "mahalanobis_baseline"
    assert 0.0 <= anomaly.anomaly_score < 1.0


def test_backfill_skips_athlete_with_no_samples(db_session):
    athlete = Athlete(
        name="No Samples Athlete",
        sport="Cycling",
        age=25,
        baseline_prior_json=_VALID_BASELINE_PRIOR_JSON,
    )
    db_session.add(athlete)
    db_session.commit()

    summary = backfill_anomalies(db_session)

    assert summary.skipped_no_samples == 1
    assert summary.skipped_no_baseline == 0
    assert summary.scored == 0
    assert db_session.query(Anomaly).count() == 0


def test_backfill_skips_athlete_with_missing_baseline(db_session):
    athlete = Athlete(name="No Baseline Athlete", sport="Cycling", age=25)
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    _add_sample(db_session, athlete.id, date(2026, 3, 1))

    summary = backfill_anomalies(db_session)

    assert summary.skipped_no_baseline == 1
    assert summary.skipped_no_samples == 0
    assert summary.scored == 0
    assert db_session.query(Anomaly).count() == 0


def test_backfill_mixed_cohort_counts_are_fully_accounted_for(db_session):
    scoreable = Athlete(
        name="Scoreable", sport="Cycling", age=25, baseline_prior_json=_VALID_BASELINE_PRIOR_JSON
    )
    no_samples = Athlete(name="NoSamples", sport="Cycling", age=25)
    no_baseline = Athlete(name="NoBaseline", sport="Cycling", age=25)
    db_session.add_all([scoreable, no_samples, no_baseline])
    db_session.commit()
    db_session.refresh(scoreable)
    db_session.refresh(no_baseline)
    _add_sample(db_session, scoreable.id, date(2026, 3, 1))
    _add_sample(db_session, no_baseline.id, date(2026, 3, 1))

    summary = backfill_anomalies(db_session)

    assert summary.total_athletes == 3
    assert (
        summary.scored
        + summary.already_scored
        + summary.skipped_no_samples
        + summary.skipped_no_baseline
        + summary.skipped_degenerate_variance
        == summary.total_athletes
    )
    assert summary.scored == 1
    assert summary.skipped_no_samples == 1
    assert summary.skipped_no_baseline == 1


def test_backfill_is_idempotent_across_repeated_runs(db_session):
    athlete = Athlete(
        name="Idempotent Athlete",
        sport="Cycling",
        age=25,
        baseline_prior_json=_VALID_BASELINE_PRIOR_JSON,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    _add_sample(db_session, athlete.id, date(2026, 3, 1))

    first_summary = backfill_anomalies(db_session)
    count_after_first = db_session.query(Anomaly).count()

    second_summary = backfill_anomalies(db_session)
    count_after_second = db_session.query(Anomaly).count()

    assert first_summary.scored == 1
    assert second_summary.scored == 0
    assert second_summary.already_scored == 1
    assert count_after_first == count_after_second == 1

    sample_ids = [row.sample_id for row in db_session.query(Anomaly).all()]
    assert len(sample_ids) == len(set(sample_ids))


def test_backfill_scores_new_sample_after_prior_backfill_without_duplicating(db_session):
    # Regression guard for the per-sample (not per-athlete) dedup scoping:
    # an athlete already scored by one backfill run who then gets a
    # genuinely new sample must get a second, distinct Anomaly row on the
    # next backfill run rather than being skipped as "already scored".
    athlete = Athlete(
        name="Growing History Athlete",
        sport="Cycling",
        age=25,
        baseline_prior_json=_VALID_BASELINE_PRIOR_JSON,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    first_sample = _add_sample(db_session, athlete.id, date(2026, 3, 1))

    backfill_anomalies(db_session)
    assert db_session.query(Anomaly).count() == 1

    second_sample = _add_sample(db_session, athlete.id, date(2026, 4, 1))
    summary = backfill_anomalies(db_session)

    assert summary.scored == 1
    assert summary.already_scored == 0
    anomalies = db_session.query(Anomaly).all()
    assert len(anomalies) == 2
    sample_ids = {row.sample_id for row in anomalies}
    assert sample_ids == {first_sample.id, second_sample.id}
