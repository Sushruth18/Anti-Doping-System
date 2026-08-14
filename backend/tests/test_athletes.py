import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Athlete, Sample
from app.db.session import Base, get_db
from app.main import app
from app.ml.baseline import update_posterior


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


def test_list_athletes_empty_db(client):
    response = client.get("/athletes")

    assert response.status_code == 200
    assert response.json() == []


def test_list_athletes_populated(client, db_session):
    athlete_with_sample = Athlete(name="Test Athlete A", sport="Cycling", age=25)
    athlete_without_sample = Athlete(name="Test Athlete B", sport="Athletics", age=30)
    db_session.add_all([athlete_with_sample, athlete_without_sample])
    db_session.commit()
    db_session.refresh(athlete_with_sample)
    db_session.refresh(athlete_without_sample)

    db_session.add(
        Sample(
            athlete_id=athlete_with_sample.id,
            date=date(2026, 1, 1),
            hb=14.0,
            hct=42.0,
            ret_pct=1.0,
            off_score=80.0,
            te_ratio=1.3,
            competition_flag=False,
            altitude_flag=False,
            injury_flag=False,
        )
    )
    db_session.commit()

    response = client.get("/athletes")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    by_name = {item["name"]: item for item in data}
    assert by_name["Test Athlete A"]["last_sample_date"] == "2026-01-01"
    assert by_name["Test Athlete B"]["last_sample_date"] is None
    for item in data:
        assert item["latest_anomaly_score"] is None
        assert item["latest_uncertainty_score"] is None
        assert item["priority_score"] == 0.0


def test_get_athlete_valid_lookup(client, db_session):
    baseline_prior_json = json.dumps(
        {
            "hb": {"mean": 14.0, "std": 0.5},
            "hct": {"mean": 42.0, "std": 1.5},
            "ret_pct": {"mean": 1.0, "std": 0.2},
            "off_score": {"mean": 80.0, "std": 8.0},
            "te_ratio": {"mean": 1.3, "std": 0.3},
        }
    )
    athlete = Athlete(
        name="Test Athlete C",
        sport="Swimming",
        age=22,
        baseline_prior_json=baseline_prior_json,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    db_session.add_all(
        [
            Sample(
                athlete_id=athlete.id,
                date=date(2026, 2, 1),
                hb=14.1,
                hct=42.1,
                ret_pct=1.0,
                off_score=81.0,
                te_ratio=1.3,
                competition_flag=False,
                altitude_flag=False,
                injury_flag=False,
            ),
            Sample(
                athlete_id=athlete.id,
                date=date(2026, 1, 1),
                hb=14.0,
                hct=42.0,
                ret_pct=1.05,
                off_score=79.0,
                te_ratio=1.28,
                competition_flag=False,
                altitude_flag=False,
                injury_flag=False,
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/athletes/{athlete.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == athlete.id
    assert data["name"] == "Test Athlete C"
    assert data["sport"] == "Swimming"
    assert data["age"] == 22
    assert data["baseline_prior"]["hb"] == {"mean": 14.0, "std": 0.5}
    assert [s["date"] for s in data["samples"]] == ["2026-01-01", "2026-02-01"]


def test_get_athlete_not_found(client):
    response = client.get("/athletes/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Athlete 999999 not found"}


def test_get_athlete_trajectory_with_several_samples(client, db_session):
    baseline_prior_json = json.dumps(
        {
            "hb": {"mean": 14.0, "std": 0.6},
            "hct": {"mean": 42.0, "std": 1.8},
            "ret_pct": {"mean": 1.0, "std": 0.25},
            "off_score": {"mean": 80.0, "std": 9.0},
            "te_ratio": {"mean": 1.3, "std": 0.3},
        }
    )
    athlete = Athlete(
        name="Test Athlete D",
        sport="Rowing",
        age=27,
        baseline_prior_json=baseline_prior_json,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    sample_rows = [
        (date(2026, 1, 1), 14.1, 42.2, 0.95, 82.0, 1.32),
        (date(2026, 1, 15), 14.3, 42.6, 0.90, 84.0, 1.35),
        (date(2026, 2, 1), 14.6, 43.0, 0.85, 87.0, 1.40),
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

    response = client.get(f"/athletes/{athlete.id}/trajectory")

    assert response.status_code == 200
    data = response.json()
    assert data["athlete_id"] == athlete.id
    assert data["ci_level"] == 0.95

    # Fixed order per api-contract.md, and all 5 biomarkers must be present
    # (not just hb, unlike the prototype's single-biomarker demo).
    assert [s["biomarker"] for s in data["series"]] == [
        "hb",
        "hct",
        "ret_pct",
        "off_score",
        "te_ratio",
    ]

    hb_series = data["series"][0]
    assert hb_series["unit"] == "g/dL"
    assert [p["date"] for p in hb_series["points"]] == [
        "2026-01-01",
        "2026-01-15",
        "2026-02-01",
    ]
    assert [p["observed"] for p in hb_series["points"]] == [14.1, 14.3, 14.6]

    # Independently recompute the expected running mean via the same
    # (already unit-tested in test_ml.py) update_posterior function, to
    # check the endpoint's wiring — obs_var scaling, sequential chaining,
    # ordering, serialization — rather than re-deriving the Bayesian math
    # by hand a second time.
    prior_mean, prior_std = 14.0, 0.6
    obs_var = (0.25 * prior_std) ** 2
    mean, var = prior_mean, prior_std**2
    expected_means = []
    for hb in (14.1, 14.3, 14.6):
        mean, var = update_posterior(mean, var, hb, obs_var)
        expected_means.append(mean)

    actual_means = [p["expected"] for p in hb_series["points"]]
    for actual, expected in zip(actual_means, expected_means):
        assert actual == pytest.approx(expected)

    # CI band should always straddle the expected value.
    for point in hb_series["points"]:
        assert point["ci_lower"] < point["expected"] < point["ci_upper"]
