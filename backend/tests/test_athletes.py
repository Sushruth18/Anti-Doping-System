import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Athlete, Sample
from app.db.session import Base, get_db
from app.main import app


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
