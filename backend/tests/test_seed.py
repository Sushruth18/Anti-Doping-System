import json
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import seed
from app.db.models import Anomaly, Athlete, Sample
from app.db.session import Base


def test_seed_clears_stale_anomaly_rows(tmp_path, monkeypatch):
    # Regression test for seed()'s clear-and-reinsert: Sample/Athlete rows
    # get deleted and their ids can be recycled by SQLite on reinsert, so
    # any pre-existing Anomaly rows referencing the old ids must also be
    # cleared, not left pointing at stale/reassigned data.
    db_path = tmp_path / "seed_test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    setup_session = TestingSessionLocal()
    athlete = Athlete(name="Pre-existing Athlete", sport="Cycling", age=25)
    setup_session.add(athlete)
    setup_session.commit()
    setup_session.refresh(athlete)
    sample = Sample(
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
    setup_session.add(sample)
    setup_session.commit()
    setup_session.refresh(sample)
    setup_session.add(
        Anomaly(
            athlete_id=athlete.id,
            sample_id=sample.id,
            anomaly_score=0.5,
            mahalanobis_distance=1.0,
            method="mahalanobis_baseline",
            created_at=datetime(2026, 1, 1, 9, 0, 0),
        )
    )
    setup_session.commit()
    assert setup_session.query(Anomaly).count() == 1
    setup_session.close()

    athletes_path = tmp_path / "athletes.json"
    samples_path = tmp_path / "samples.json"
    athletes_path.write_text(
        json.dumps(
            [{"id": 1, "name": "Reseeded Athlete", "sport": "Cycling", "age": 22}]
        ),
        encoding="utf-8",
    )
    samples_path.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "athlete_id": 1,
                    "date": "2026-02-01",
                    "hb": 15.0,
                    "hct": 44.0,
                    "ret_pct": 1.1,
                    "off_score": 85.0,
                    "te_ratio": 1.4,
                    "competition_flag": False,
                    "altitude_flag": False,
                    "injury_flag": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(seed, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(seed, "engine", engine)
    monkeypatch.setattr(seed, "ATHLETES_PATH", str(athletes_path))
    monkeypatch.setattr(seed, "SAMPLES_PATH", str(samples_path))

    seed.seed()

    verify_session = TestingSessionLocal()
    try:
        assert verify_session.query(Anomaly).count() == 0
        assert verify_session.query(Athlete).count() == 1
        assert verify_session.query(Sample).count() == 1
    finally:
        verify_session.close()
    engine.dispose()
