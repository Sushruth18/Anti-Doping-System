from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sport: Mapped[str] = mapped_column(String, nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    baseline_prior_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


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


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), nullable=False)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    mahalanobis_distance: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    investigator_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
