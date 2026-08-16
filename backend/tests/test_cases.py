import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Athlete, AuditLog, Case
from app.db.session import Base, get_db
from app.main import app


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "test_cases.db"
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


# --- POST /cases -----------------------------------------------------


def test_create_case_valid(client, db_session, athlete):
    response = client.post("/cases", json={"athlete_id": athlete.id, "notes": "Initial flag review"})

    assert response.status_code == 201
    data = response.json()
    assert data["athlete_id"] == athlete.id
    assert data["status"] == "open"
    assert data["closed_at"] is None
    assert data["investigator_notes"] == "Initial flag review"
    assert data["opened_at"].endswith("Z")
    assert isinstance(data["id"], int)

    row = db_session.query(Case).filter(Case.id == data["id"]).first()
    assert row is not None
    assert row.status == "open"
    assert row.closed_at is None


def test_create_case_without_notes_defaults_to_null(client, athlete):
    response = client.post("/cases", json={"athlete_id": athlete.id})

    assert response.status_code == 201
    assert response.json()["investigator_notes"] is None


def test_create_case_unknown_athlete_returns_404(client):
    response = client.post("/cases", json={"athlete_id": 999})

    assert response.status_code == 404
    assert response.json() == {"detail": "Athlete 999 not found"}


def test_create_case_missing_athlete_id_returns_422(client):
    response = client.post("/cases", json={"notes": "no athlete_id here"})

    assert response.status_code == 422


# --- POST /cases/{id}/decision ----------------------------------------


def test_decision_close_case_closes_it_and_writes_audit_log(client, db_session, athlete):
    create_response = client.post("/cases", json={"athlete_id": athlete.id})
    case_id = create_response.json()["id"]

    response = client.post(
        f"/cases/{case_id}/decision",
        json={"action": "close_case", "investigator": "Dr. Amara Whitfield"},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["case"]["id"] == case_id
    assert data["case"]["status"] == "closed"
    assert data["case"]["closed_at"] is not None
    assert data["case"]["closed_at"].endswith("Z")

    assert data["audit_log"]["case_id"] == case_id
    assert data["audit_log"]["athlete_id"] == athlete.id
    assert data["audit_log"]["actor"] == "Dr. Amara Whitfield"
    assert data["audit_log"]["action"] == "close_case"
    assert data["audit_log"]["details"] == {}
    assert isinstance(data["audit_log"]["id"], int)

    row = db_session.query(Case).filter(Case.id == case_id).first()
    assert row.status == "closed"
    assert row.closed_at is not None

    audit_rows = db_session.query(AuditLog).filter(AuditLog.case_id == case_id).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "close_case"


def test_decision_non_closing_action_leaves_case_open_but_logs(client, db_session, athlete):
    create_response = client.post("/cases", json={"athlete_id": athlete.id})
    case_id = create_response.json()["id"]

    response = client.post(
        f"/cases/{case_id}/decision",
        json={"action": "escalate", "investigator": "Dr. Amara Whitfield"},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["case"]["status"] == "open"
    assert data["case"]["closed_at"] is None
    assert data["audit_log"]["action"] == "escalate"
    assert data["audit_log"]["actor"] == "Dr. Amara Whitfield"

    row = db_session.query(Case).filter(Case.id == case_id).first()
    assert row.status == "open"
    assert row.closed_at is None

    audit_rows = db_session.query(AuditLog).filter(AuditLog.case_id == case_id).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "escalate"


def test_decision_multiple_non_closing_actions_each_logged_independently(client, db_session, athlete):
    create_response = client.post("/cases", json={"athlete_id": athlete.id})
    case_id = create_response.json()["id"]

    client.post(
        f"/cases/{case_id}/decision",
        json={"action": "escalate", "investigator": "Investigator A"},
    )
    client.post(
        f"/cases/{case_id}/decision",
        json={"action": "request_more_testing", "investigator": "Investigator B"},
    )

    audit_rows = db_session.query(AuditLog).filter(AuditLog.case_id == case_id).all()
    assert len(audit_rows) == 2
    assert {row.action for row in audit_rows} == {"escalate", "request_more_testing"}

    row = db_session.query(Case).filter(Case.id == case_id).first()
    assert row.status == "open"


def test_decision_unknown_case_returns_404(client):
    response = client.post(
        "/cases/999/decision", json={"action": "escalate", "investigator": "Someone"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Case 999 not found"}


def test_decision_invalid_action_returns_422(client, athlete):
    create_response = client.post("/cases", json={"athlete_id": athlete.id})
    case_id = create_response.json()["id"]

    response = client.post(
        f"/cases/{case_id}/decision",
        json={"action": "not_a_real_action", "investigator": "Someone"},
    )

    assert response.status_code == 422


def test_decision_missing_investigator_returns_422(client, athlete):
    create_response = client.post("/cases", json={"athlete_id": athlete.id})
    case_id = create_response.json()["id"]

    response = client.post(f"/cases/{case_id}/decision", json={"action": "escalate"})

    assert response.status_code == 422
