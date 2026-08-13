import os
import sys

# Allow running as a plain script (`python app/db/init_db.py`) as well as
# a module (`python -m app.db.init_db`) by ensuring /backend is on sys.path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db import models  # noqa: F401 - import registers the tables on Base.metadata
from app.db.session import Base, engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database tables created.")
