import json
import os
import sys
from datetime import datetime

# Allow running as a plain script (`python seed.py`) as well as a module
# (`python -m app.db.seed`) by ensuring /backend is on sys.path, same
# approach as init_db.py.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _BACKEND_DIR)

from app.db import models  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402

_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
ATHLETES_PATH = os.path.join(_REPO_ROOT, "data", "athletes.json")
SAMPLES_PATH = os.path.join(_REPO_ROOT, "data", "samples.json")


def seed() -> None:
    Base.metadata.create_all(bind=engine)

    with open(ATHLETES_PATH, "r", encoding="utf-8") as f:
        athletes_data = json.load(f)
    with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
        samples_data = json.load(f)

    db = SessionLocal()
    try:
        # Clear-and-reinsert rather than upsert: this is a small, fully
        # fixed placeholder dataset (not incrementally-updated real data),
        # so each run should leave the tables exactly matching the JSON
        # files rather than merging with whatever was there before.
        db.query(models.Sample).delete()
        db.query(models.Athlete).delete()

        for row in athletes_data:
            db.add(models.Athlete(**row))

        for row in samples_data:
            row = dict(row)
            row["date"] = datetime.strptime(row["date"], "%Y-%m-%d").date()
            db.add(models.Sample(**row))

        db.commit()

        athlete_count = db.query(models.Athlete).count()
        sample_count = db.query(models.Sample).count()
        print(f"Seeded {athlete_count} athletes, {sample_count} samples.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
