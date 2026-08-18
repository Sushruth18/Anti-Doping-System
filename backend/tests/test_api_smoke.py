import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Athlete, Sample
from app.db.session import Base, get_db
from app.main import app

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GROUND_TRUTH_PATH = _REPO_ROOT / "data" / "ground_truth.json"
_ATHLETES_PATH = _REPO_ROOT / "data" / "athletes.json"
_SAMPLES_PATH = _REPO_ROOT / "data" / "samples.json"


def _find_seeded_athlete_id(pattern_type: str) -> int:
    # ground_truth.json is looked up here, in the test, only to pick which
    # already-seeded athlete_id to exercise the endpoint against — the
    # endpoint itself never reads it (see CLAUDE.md's standing guardrail).
    ground_truth = json.loads(_GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    for row in ground_truth:
        if row.get("is_synthetic_anomaly") and row.get("pattern_type") == pattern_type:
            return row["athlete_id"]
    raise AssertionError(f"no seeded athlete found with pattern_type={pattern_type!r}")


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


def _seed_athlete(db_session, athlete_id: int) -> None:
    # Loads this one athlete's real generator output from data/athletes.json
    # + data/samples.json (the same files app/db/seed.py reads) into the
    # test's own throwaway DB, rather than depending on the untracked local
    # backend/app.db — keeps the test deterministic and CI-safe while still
    # exercising real seeded values, not hand-fabricated ones.
    athletes_data = json.loads(_ATHLETES_PATH.read_text(encoding="utf-8"))
    samples_data = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))

    athlete_row = next(row for row in athletes_data if row["id"] == athlete_id)
    db_session.add(Athlete(**athlete_row))

    for row in samples_data:
        if row["athlete_id"] != athlete_id:
            continue
        row = dict(row)
        row["date"] = datetime.strptime(row["date"], "%Y-%m-%d").date()
        db_session.add(Sample(**row))

    db_session.commit()


def test_simulation_evasion_epo_micro_dosing_smoke(client, db_session):
    athlete_id = _find_seeded_athlete_id("epo")
    _seed_athlete(db_session, athlete_id)

    response = client.get("/simulation/evasion", params={"athlete_id": athlete_id})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "athlete_id",
        "biomarker",
        "pattern",
        "sample_count",
        "single_sample_scores",
        "single_sample_flagged_any",
        "cusum_result",
        "cusum_flagged",
    }
    assert body["athlete_id"] == athlete_id
    assert body["biomarker"] == "hb"
    assert body["pattern"] == "micro_dosing"
    assert body["sample_count"] == len(body["single_sample_scores"])
    assert isinstance(body["single_sample_flagged_any"], bool)
    assert isinstance(body["cusum_flagged"], bool)
    assert set(body["cusum_result"].keys()) == {
        "cusum_upper",
        "cusum_lower",
        "flagged",
        "flagged_at_index",
        "threshold",
    }
    assert body["cusum_result"]["threshold"] == 5.0
    assert len(body["cusum_result"]["cusum_upper"]) == body["sample_count"]
    assert len(body["cusum_result"]["cusum_lower"]) == body["sample_count"]


def test_simulation_evasion_steroid_micro_dosing_smoke(client, db_session):
    athlete_id = _find_seeded_athlete_id("steroid")
    _seed_athlete(db_session, athlete_id)

    response = client.get(
        "/simulation/evasion",
        params={"athlete_id": athlete_id, "pattern": "steroid_micro_dosing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_id"] == athlete_id
    assert body["biomarker"] == "te_ratio"
    assert body["pattern"] == "steroid_micro_dosing"
    assert body["sample_count"] == len(body["single_sample_scores"])


def test_simulation_evasion_unknown_athlete_404(client, db_session):
    response = client.get("/simulation/evasion", params={"athlete_id": 999999})

    assert response.status_code == 404
