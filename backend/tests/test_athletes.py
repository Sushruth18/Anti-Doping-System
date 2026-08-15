import json
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Anomaly, Athlete, Sample
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


def test_list_athletes_uses_latest_anomaly_score(client, db_session):
    athlete = Athlete(name="Test Athlete E", sport="Cycling", age=29)
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    sample_older = Sample(
        athlete_id=athlete.id,
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
    sample_newer = Sample(
        athlete_id=athlete.id,
        date=date(2026, 2, 1),
        hb=14.2,
        hct=42.3,
        ret_pct=0.95,
        off_score=83.0,
        te_ratio=1.31,
        competition_flag=False,
        altitude_flag=False,
        injury_flag=False,
    )
    db_session.add_all([sample_older, sample_newer])
    db_session.commit()
    db_session.refresh(sample_older)
    db_session.refresh(sample_newer)

    # Two anomaly records for the same athlete — only the one with the
    # latest created_at should be used, regardless of insertion order.
    db_session.add_all(
        [
            Anomaly(
                athlete_id=athlete.id,
                sample_id=sample_newer.id,
                anomaly_score=0.91,
                mahalanobis_distance=3.2,
                method="mahalanobis_baseline",
                created_at=datetime(2026, 2, 1, 9, 0, 0),
            ),
            Anomaly(
                athlete_id=athlete.id,
                sample_id=sample_older.id,
                anomaly_score=0.15,
                mahalanobis_distance=0.4,
                method="mahalanobis_baseline",
                created_at=datetime(2026, 1, 1, 9, 0, 0),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/athletes")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["latest_anomaly_score"] == pytest.approx(0.91)
    assert data[0]["priority_score"] == pytest.approx(0.91)


def test_list_athletes_no_anomaly_record_falls_back(client, db_session):
    athlete = Athlete(name="Test Athlete F", sport="Cycling", age=24)
    db_session.add(athlete)
    db_session.commit()

    response = client.get("/athletes")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["latest_anomaly_score"] is None
    assert data[0]["priority_score"] == 0.0


def test_list_athletes_sort_priority_orders_descending(client, db_session):
    low_priority = Athlete(name="Low Priority Athlete", sport="Rowing", age=26)
    high_priority = Athlete(name="High Priority Athlete", sport="Rowing", age=31)
    db_session.add_all([low_priority, high_priority])
    db_session.commit()
    db_session.refresh(low_priority)
    db_session.refresh(high_priority)

    low_sample = Sample(
        athlete_id=low_priority.id,
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
    high_sample = Sample(
        athlete_id=high_priority.id,
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
    db_session.add_all([low_sample, high_sample])
    db_session.commit()
    db_session.refresh(low_sample)
    db_session.refresh(high_sample)

    db_session.add_all(
        [
            Anomaly(
                athlete_id=low_priority.id,
                sample_id=low_sample.id,
                anomaly_score=0.2,
                mahalanobis_distance=0.5,
                method="mahalanobis_baseline",
                created_at=datetime(2026, 1, 1, 9, 0, 0),
            ),
            Anomaly(
                athlete_id=high_priority.id,
                sample_id=high_sample.id,
                anomaly_score=0.87,
                mahalanobis_distance=3.9,
                method="mahalanobis_baseline",
                created_at=datetime(2026, 1, 1, 9, 0, 0),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/athletes?sort=priority")

    assert response.status_code == 200
    data = response.json()
    names_in_order = [item["name"] for item in data]
    assert names_in_order.index("High Priority Athlete") < names_in_order.index(
        "Low Priority Athlete"
    )
    scores = [item["priority_score"] for item in data]
    assert scores == sorted(scores, reverse=True)


def test_list_athletes_sport_filter(client, db_session):
    cyclist = Athlete(name="Cyclist Athlete", sport="Cycling", age=28)
    swimmer = Athlete(name="Swimmer Athlete", sport="Swimming", age=23)
    db_session.add_all([cyclist, swimmer])
    db_session.commit()

    response = client.get("/athletes?sport=Cycling")

    assert response.status_code == 200
    data = response.json()
    assert [item["name"] for item in data] == ["Cyclist Athlete"]


def test_list_athletes_invalid_sort_returns_422(client, db_session):
    response = client.get("/athletes?sort=bogus")

    assert response.status_code == 422


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


def test_get_athlete_trajectory_response_matches_pre_refactor_snapshot(client, db_session):
    # Byte-for-byte snapshot of the actual /athletes/{id}/trajectory JSON
    # response, captured live from a real TestClient request against this
    # exact fixture BEFORE the fold_biomarker_posterior/compute_current_posterior
    # refactor of get_athlete_trajectory (which moved the fold loop's math
    # out of this route and into app/ml/baseline.py). This guards that the
    # refactor is a pure internal restructuring with zero change to the
    # wire response, for the same reasons/fixture as
    # test_get_athlete_trajectory_with_several_samples above.
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
    assert response.json() == {
        "athlete_id": 1,
        "ci_level": 0.95,
        "series": [
            {
                "biomarker": "hb",
                "unit": "g/dL",
                "points": [
                    {
                        "date": "2026-01-01",
                        "observed": 14.1,
                        "expected": 14.094117647058823,
                        "ci_lower": 13.808895752016095,
                        "ci_upper": 14.379339542101551,
                    },
                    {
                        "date": "2026-01-15",
                        "observed": 14.3,
                        "expected": 14.193939393939395,
                        "ci_lower": 13.989224070535494,
                        "ci_upper": 14.398654717343296,
                    },
                    {
                        "date": "2026-02-01",
                        "observed": 14.6,
                        "expected": 14.3265306122449,
                        "ci_lower": 14.1585306122449,
                        "ci_upper": 14.4945306122449,
                    },
                ],
            },
            {
                "biomarker": "hct",
                "unit": "%",
                "points": [
                    {
                        "date": "2026-01-01",
                        "observed": 42.2,
                        "expected": 42.18823529411765,
                        "ci_lower": 41.33256960898947,
                        "ci_upper": 43.043900979245834,
                    },
                    {
                        "date": "2026-01-15",
                        "observed": 42.6,
                        "expected": 42.3878787878788,
                        "ci_lower": 41.773732817667096,
                        "ci_upper": 43.0020247580905,
                    },
                    {
                        "date": "2026-02-01",
                        "observed": 43.0,
                        "expected": 42.58775510204082,
                        "ci_lower": 42.083755102040826,
                        "ci_upper": 43.09175510204082,
                    },
                ],
            },
            {
                "biomarker": "ret_pct",
                "unit": "%",
                "points": [
                    {
                        "date": "2026-01-01",
                        "observed": 0.95,
                        "expected": 0.9529411764705882,
                        "ci_lower": 0.834098720202785,
                        "ci_upper": 1.0717836327383914,
                    },
                    {
                        "date": "2026-01-15",
                        "observed": 0.9,
                        "expected": 0.9272727272727274,
                        "ci_lower": 0.8419746758544354,
                        "ci_upper": 1.0125707786910194,
                    },
                    {
                        "date": "2026-02-01",
                        "observed": 0.85,
                        "expected": 0.9020408163265305,
                        "ci_lower": 0.8320408163265306,
                        "ci_upper": 0.9720408163265305,
                    },
                ],
            },
            {
                "biomarker": "off_score",
                "unit": "score",
                "points": [
                    {
                        "date": "2026-01-01",
                        "observed": 82.0,
                        "expected": 81.88235294117648,
                        "ci_lower": 77.60402451553557,
                        "ci_upper": 86.16068136681739,
                    },
                    {
                        "date": "2026-01-15",
                        "observed": 84.0,
                        "expected": 82.90909090909089,
                        "ci_lower": 79.83836105803238,
                        "ci_upper": 85.97982076014941,
                    },
                    {
                        "date": "2026-02-01",
                        "observed": 87.0,
                        "expected": 84.24489795918366,
                        "ci_lower": 81.72489795918366,
                        "ci_upper": 86.76489795918366,
                    },
                ],
            },
            {
                "biomarker": "te_ratio",
                "unit": "ratio",
                "points": [
                    {
                        "date": "2026-01-01",
                        "observed": 1.32,
                        "expected": 1.3188235294117647,
                        "ci_lower": 1.176212581890401,
                        "ci_upper": 1.4614344769331284,
                    },
                    {
                        "date": "2026-01-15",
                        "observed": 1.35,
                        "expected": 1.333939393939394,
                        "ci_lower": 1.2315817322374436,
                        "ci_upper": 1.4362970556413444,
                    },
                    {
                        "date": "2026-02-01",
                        "observed": 1.4,
                        "expected": 1.355510204081633,
                        "ci_lower": 1.2715102040816328,
                        "ci_upper": 1.439510204081633,
                    },
                ],
            },
        ],
    }
