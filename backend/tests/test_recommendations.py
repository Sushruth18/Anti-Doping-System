import json
import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Athlete, Sample
from app.db.session import Base, get_db
from app.main import app
from app.ml.action_engine import compute_recommendation

# Real seeded dataset -- same files `app.db.seed.seed()` reads. The
# hand-computed reference values in these tests are for the actual Taylor
# Gomez/Logan Rossi/Indigo Berg rows in this data (already verified against
# compute_recommendation() directly in test_action_engine.py), so this
# loads the same files rather than fabricating athletes.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ATHLETES_PATH = os.path.join(_REPO_ROOT, "data", "athletes.json")
_SAMPLES_PATH = os.path.join(_REPO_ROOT, "data", "samples.json")


@pytest.fixture()
def seeded_db(tmp_path):
    db_path = tmp_path / "recommendations_test.db"
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

    with open(_ATHLETES_PATH, "r", encoding="utf-8") as f:
        athletes_data = json.load(f)
    with open(_SAMPLES_PATH, "r", encoding="utf-8") as f:
        samples_data = json.load(f)

    session = TestingSessionLocal()
    try:
        for row in athletes_data:
            session.add(Athlete(**row))
        for row in samples_data:
            row = dict(row)
            row["date"] = datetime.strptime(row["date"], "%Y-%m-%d").date()
            session.add(Sample(**row))
        session.commit()

        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture()
def client(seeded_db):
    return TestClient(app)


@pytest.mark.parametrize(
    "athlete_id,expected_action_type,expected_value_score",
    [
        (4, "biological_passport_review", 0.0014135307211768622),  # Taylor Gomez
        (44, "target_test", 0.0019973938797114015),  # Logan Rossi
        (65, "biological_passport_review", 0.0014098029409579807),  # Indigo Berg
    ],
)
def test_get_recommendation_matches_compute_recommendation_and_contract_shape(
    client, seeded_db, athlete_id, expected_action_type, expected_value_score
):
    response = client.get(f"/athletes/{athlete_id}/recommendation")

    assert response.status_code == 200
    data = response.json()

    # Exact contract shape: these 9 keys, nothing more, nothing missing.
    assert set(data.keys()) == {
        "id",
        "athlete_id",
        "action_type",
        "value_score",
        "uncertainty_score",
        "anomaly_score",
        "cost",
        "explanation_text",
        "created_at",
    }

    assert data["id"] is None
    assert data["athlete_id"] == athlete_id
    assert data["action_type"] == expected_action_type
    assert data["value_score"] == pytest.approx(expected_value_score)
    assert isinstance(data["explanation_text"], str) and data["explanation_text"] != ""
    assert data["created_at"].endswith("Z")

    # Cross-check against compute_recommendation() itself, called fresh
    # against the same seeded DB, rather than only against hardcoded
    # numbers -- confirms the route is a thin pass-through, not
    # reimplementing/diverging from the pipeline.
    direct = compute_recommendation(athlete_id, seeded_db)
    assert data["value_score"] == pytest.approx(direct["value_score"])
    assert data["uncertainty_score"] == pytest.approx(direct["uncertainty_score"])
    assert data["anomaly_score"] == pytest.approx(direct["anomaly_score"])
    assert data["cost"] == pytest.approx(direct["cost"])
    assert data["action_type"] == direct["action_type"]
    assert data["explanation_text"] == direct["explanation_text"]


def test_get_recommendation_unknown_athlete_returns_404(client):
    response = client.get("/athletes/999/recommendation")

    assert response.status_code == 404
    assert response.json() == {"detail": "Athlete 999 not found"}


def test_get_recommendation_athlete_with_no_samples_returns_404(client, seeded_db):
    athlete = Athlete(name="No Samples Athlete", sport="Cycling", age=25)
    seeded_db.add(athlete)
    seeded_db.commit()
    seeded_db.refresh(athlete)

    response = client.get(f"/athletes/{athlete.id}/recommendation")

    # Same 404 message as "unknown athlete" per api-contract.md -- frontend
    # isn't expected to distinguish "doesn't exist" from "exists but has no
    # recommendation yet".
    assert response.status_code == 404
    assert response.json() == {"detail": f"Athlete {athlete.id} not found"}
