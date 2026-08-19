import json
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Anomaly, Athlete, AuditLog, Case, Sample
from app.db.session import Base, get_db
from app.main import app


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "test_audit.db"
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


@pytest.fixture()
def athlete(db_session):
    athlete = Athlete(name="Test Athlete", sport="Cycling", age=27)
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _add_sample(db_session, athlete_id, sample_date, **overrides):
    values = dict(
        athlete_id=athlete_id,
        date=sample_date,
        hb=14.0,
        hct=42.0,
        ret_pct=1.2,
        off_score=74.27,
        te_ratio=1.1,
        competition_flag=False,
        altitude_flag=False,
        injury_flag=False,
    )
    values.update(overrides)
    sample = Sample(**values)
    db_session.add(sample)
    db_session.commit()
    db_session.refresh(sample)
    return sample


def test_audit_athlete_with_only_samples_returns_them_in_chronological_order(
    client, db_session, athlete
):
    # Inserted out of chronological order on purpose -- the endpoint must
    # sort by timestamp, not return insertion/query order.
    later = _add_sample(db_session, athlete.id, date(2026, 6, 15))
    earlier = _add_sample(db_session, athlete.id, date(2026, 6, 1))

    response = client.get(f"/audit/{athlete.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_id"] == athlete.id
    assert [event["type"] for event in body["events"]] == ["sample", "sample"]

    # samples.date has no time component -- midnight UTC per
    # docs/api-contract.md's note on sample event timestamps.
    assert body["events"][0]["timestamp"] == "2026-06-01T00:00:00Z"
    assert body["events"][0]["data"]["id"] == earlier.id
    assert body["events"][1]["timestamp"] == "2026-06-15T00:00:00Z"
    assert body["events"][1]["data"]["id"] == later.id


def test_audit_full_history_sample_anomaly_case_and_decision_in_chronological_order(
    client, db_session, athlete
):
    sample = _add_sample(db_session, athlete.id, date(2026, 7, 1))

    anomaly = Anomaly(
        athlete_id=athlete.id,
        sample_id=sample.id,
        anomaly_score=0.82,
        mahalanobis_distance=4.35,
        method="mahalanobis_baseline",
        created_at=datetime(2026, 7, 1, 9, 15, 0),
    )
    db_session.add(anomaly)

    case = Case(
        athlete_id=athlete.id,
        status="closed",
        opened_at=datetime(2026, 7, 1, 9, 25, 0),
        closed_at=datetime(2026, 7, 2, 14, 0, 0),
        investigator_notes="Opened based on automated recommendation engine flag.",
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # `decision` and the resulting `case_closed` share the exact same
    # timestamp on purpose -- mirrors log_decision (app/routes/cases.py)
    # writing both from a single `now` in real usage, and exercises the
    # documented _EVENT_TYPE_TIEBREAK_ORDER tiebreak.
    audit_log = AuditLog(
        case_id=case.id,
        athlete_id=athlete.id,
        actor="Dr. Amara Whitfield",
        action="close_case",
        timestamp=datetime(2026, 7, 2, 14, 0, 0),
        details_json=json.dumps({"notes": "Confirmed doping violation."}),
    )
    db_session.add(audit_log)
    db_session.commit()

    response = client.get(f"/audit/{athlete.id}")

    assert response.status_code == 200
    events = response.json()["events"]
    assert [event["type"] for event in events] == [
        "sample",
        "anomaly",
        "case_opened",
        "decision",
        "case_closed",
    ]

    assert events[0]["timestamp"] == "2026-07-01T00:00:00Z"
    assert events[0]["data"]["id"] == sample.id

    assert events[1]["timestamp"] == "2026-07-01T09:15:00Z"
    assert events[1]["data"]["id"] == anomaly.id
    assert events[1]["data"]["anomaly_score"] == 0.82

    assert events[2]["timestamp"] == "2026-07-01T09:25:00Z"
    assert events[2]["data"]["id"] == case.id
    # Current row state, not an open-time snapshot -- see the comment on
    # this in app/routes/cases.py's get_audit_timeline.
    assert events[2]["data"]["status"] == "closed"

    assert events[3]["timestamp"] == "2026-07-02T14:00:00Z"
    assert events[3]["type"] == "decision"
    assert events[3]["data"]["action"] == "close_case"
    assert events[3]["data"]["actor"] == "Dr. Amara Whitfield"
    assert events[3]["data"]["details"] == {"notes": "Confirmed doping violation."}

    assert events[4]["timestamp"] == "2026-07-02T14:00:00Z"
    assert events[4]["type"] == "case_closed"
    assert events[4]["data"]["id"] == case.id
    assert events[4]["data"]["closed_at"] == "2026-07-02T14:00:00Z"


def test_audit_unknown_athlete_returns_404(client):
    response = client.get("/audit/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Athlete 999999 not found"}


def test_audit_athlete_with_no_events_returns_200_empty_events(client, athlete):
    response = client.get(f"/audit/{athlete.id}")

    assert response.status_code == 200
    assert response.json() == {"athlete_id": athlete.id, "events": []}
