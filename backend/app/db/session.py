import os
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

# Anchor the default SQLite file to backend/app.db by the location of this
# file, not the process's cwd — a bare relative URL ("sqlite:///./app.db")
# resolves against whatever directory the process was launched from, which
# silently creates a second, empty database if a script is run from
# somewhere other than /backend.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SQLITE_PATH = (_BACKEND_DIR / "app.db").as_posix()

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}")

# SQLite needs this to allow the connection to be used across the
# threads FastAPI's request handling can dispatch to.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
