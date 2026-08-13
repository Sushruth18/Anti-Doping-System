from datetime import date as date_type

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sport: Mapped[str] = mapped_column(String, nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline_prior_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    hb: Mapped[float] = mapped_column(Float, nullable=False)
    hct: Mapped[float] = mapped_column(Float, nullable=False)
    ret_pct: Mapped[float] = mapped_column(Float, nullable=False)
    off_score: Mapped[float] = mapped_column(Float, nullable=False)
    te_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    competition_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    altitude_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    injury_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
