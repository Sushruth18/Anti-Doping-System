"""`POST /cases` and `POST /cases/{id}/decision` per `docs/api-contract.md`'s
Day 6 case/decision shapes and `docs/schema.md`'s `cases`/`audit_logs`
tables.

Independent of the anomaly/uncertainty/action-engine/explain modules and
`/athletes/{id}/recommendation` -- a case is opened against an `athlete_id`
directly, not against a specific `Anomaly`/`Recommendation` row (see
`docs/known-limitations.md`'s note on why the `recommendations` table gap
doesn't block this).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy.orm import Session

from app.db.models import Anomaly, Athlete, AuditLog, Case, Sample
from app.db.session import get_db
from app.routes.athletes import AnomalyOut, SampleOut

router = APIRouter()

DecisionAction = Literal["escalate", "clear", "request_more_testing", "close_case"]

# Per api-contract.md: only this action flips case.status to "closed" /
# sets closed_at; every other action still writes an AuditLog row but
# leaves the case otherwise unchanged.
_CLOSING_ACTION: DecisionAction = "close_case"


def _parse_details_json(details_json: Optional[str]) -> dict[str, object]:
    return json.loads(details_json) if details_json else {}


class NewCaseInput(BaseModel):
    athlete_id: int
    notes: Optional[str] = None


class CaseOut(BaseModel):
    id: int
    athlete_id: int
    status: Literal["open", "closed"]
    opened_at: datetime
    closed_at: Optional[datetime]
    investigator_notes: Optional[str]

    @field_serializer("opened_at")
    def _serialize_opened_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    @field_serializer("closed_at")
    def _serialize_closed_at(self, value: Optional[datetime]) -> Optional[str]:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value is not None else None

    @classmethod
    def from_model(cls, case: Case) -> "CaseOut":
        return cls(
            id=case.id,
            athlete_id=case.athlete_id,
            status=case.status,
            opened_at=case.opened_at,
            closed_at=case.closed_at,
            investigator_notes=case.investigator_notes,
        )


class DecisionInput(BaseModel):
    action: DecisionAction
    investigator: str


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: Optional[int]
    athlete_id: int
    actor: str
    action: str
    timestamp: datetime
    details: dict[str, object]

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def from_model(cls, audit_log: AuditLog) -> "AuditLogOut":
        return cls(
            id=audit_log.id,
            case_id=audit_log.case_id,
            athlete_id=audit_log.athlete_id,
            actor=audit_log.actor,
            action=audit_log.action,
            timestamp=audit_log.timestamp,
            details=_parse_details_json(audit_log.details_json),
        )


class DecisionResponse(BaseModel):
    case: CaseOut
    audit_log: AuditLogOut


@router.post("/cases", response_model=CaseOut, status_code=201)
def create_case(body: NewCaseInput, db: Session = Depends(get_db)) -> CaseOut:
    athlete = db.query(Athlete).filter(Athlete.id == body.athlete_id).first()
    if athlete is None:
        raise HTTPException(status_code=404, detail=f"Athlete {body.athlete_id} not found")

    case = Case(
        athlete_id=body.athlete_id,
        status="open",
        opened_at=datetime.utcnow(),
        closed_at=None,
        investigator_notes=body.notes,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    return CaseOut.from_model(case)


@router.post("/cases/{case_id}/decision", response_model=DecisionResponse, status_code=201)
def log_decision(
    case_id: int, body: DecisionInput, db: Session = Depends(get_db)
) -> DecisionResponse:
    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    now = datetime.utcnow()
    if body.action == _CLOSING_ACTION:
        case.status = "closed"
        case.closed_at = now

    audit_log = AuditLog(
        case_id=case.id,
        athlete_id=case.athlete_id,
        actor=body.investigator,
        action=body.action,
        timestamp=now,
        details_json=None,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(case)
    db.refresh(audit_log)

    return DecisionResponse(
        case=CaseOut.from_model(case),
        audit_log=AuditLogOut.from_model(audit_log),
    )


# --- GET /audit/{athlete_id} -----------------------------------------------
#
# Per docs/api-contract.md's locked `AuditEvent`/`AuditTimelineResponse`
# shapes: field names are `type`/`data`/`events`, matching
# frontend/mock/audit.json -- that locked contract is the source of truth
# here, not the `event_type`/`details`/`timeline` names floated earlier.
# Reuses `SampleOut`/`AnomalyOut` from `app.routes.athletes` and
# `CaseOut`/`AuditLogOut` already defined above instead of redefining the
# same shapes a third time.
#
# Deviation from the locked contract: docs/api-contract.md's AuditEvent
# union (line ~528) includes a `recommendation` variant, and this endpoint
# does not emit it. That's a real, acknowledged gap against the contract,
# not an implementation detail invisible from the contract's perspective.
#
# Reason: per docs/known-limitations.md, no `recommendations` table exists
# yet, so there is no REAL historical recommendation value to source a
# past event from -- only a live-computed CURRENT value via
# compute_recommendation(). This endpoint deliberately does not fabricate
# historical recommendation events by re-running compute_recommendation()
# against each past sample's context: doing so would show what the system
# would recommend TODAY given the athlete's CURRENT posterior, not what it
# actually would have recommended at that historical point in time -- and
# an audit trail is the one place in this system where historical accuracy
# matters most, so a wrong-but-plausible-looking backdated recommendation
# is worse than an admitted gap. Left incomplete-but-honest rather than
# complete-but-fabricated; revisit as a follow-up once a real
# `recommendations` table exists to persist real historical values.
#
# `anomaly` events, by contrast, ARE emitted: unlike recommendations, the
# `anomalies` table IS persisted (written by POST /athletes/{id}/samples
# and backfilled for pre-existing seeded samples by
# app/db/backfill_anomalies.py), so this reads real historical rows here,
# not a live recomputation.


class _TimestampedEvent(BaseModel):
    timestamp: datetime

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class SampleEvent(_TimestampedEvent):
    type: Literal["sample"] = "sample"
    data: SampleOut


class AnomalyEvent(_TimestampedEvent):
    type: Literal["anomaly"] = "anomaly"
    data: AnomalyOut


class CaseOpenedEvent(_TimestampedEvent):
    type: Literal["case_opened"] = "case_opened"
    data: CaseOut


class CaseClosedEvent(_TimestampedEvent):
    # Included because docs/api-contract.md's locked AuditEvent union has
    # it as its own variant, backed by real persisted data
    # (`cases.closed_at`) -- not blocked by the same
    # missing-recommendations-table gap that justifies omitting
    # `recommendation` above.
    type: Literal["case_closed"] = "case_closed"
    data: CaseOut


class DecisionEvent(_TimestampedEvent):
    type: Literal["decision"] = "decision"
    data: AuditLogOut


AuditEvent = Annotated[
    Union[SampleEvent, AnomalyEvent, CaseOpenedEvent, CaseClosedEvent, DecisionEvent],
    Field(discriminator="type"),
]


class AuditTimelineResponse(BaseModel):
    athlete_id: int
    events: list[AuditEvent]


# Tiebreak order for events sharing the exact same timestamp (same-day
# samples, or a close_case decision and its resulting case_closed event,
# which share `datetime.utcnow()` from the same request in log_decision
# above) -- applied as a secondary sort key so ties are deterministic
# rather than left to whatever order the four queries below happen to
# merge in. Ordered along the causal chain a single sample can set off: a
# sample is observed, it gets scored (anomaly), that may open a case, an
# investigator then decides on it, and only THEN (if the decision was
# close_case) does the case actually close.
_EVENT_TYPE_TIEBREAK_ORDER: dict[str, int] = {
    "sample": 0,
    "anomaly": 1,
    "case_opened": 2,
    "decision": 3,
    "case_closed": 4,
}


@router.get("/audit/{athlete_id}", response_model=AuditTimelineResponse)
def get_audit_timeline(athlete_id: int, db: Session = Depends(get_db)) -> AuditTimelineResponse:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        raise HTTPException(status_code=404, detail=f"Athlete {athlete_id} not found")

    events: list[AuditEvent] = []

    samples = (
        db.query(Sample).filter(Sample.athlete_id == athlete_id).order_by(Sample.date.asc()).all()
    )
    for sample in samples:
        # samples.date has no time component -- midnight UTC, per
        # api-contract.md's "For type: sample events..." note.
        timestamp = datetime.combine(sample.date, datetime.min.time())
        events.append(SampleEvent(timestamp=timestamp, data=SampleOut.model_validate(sample)))

    anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.athlete_id == athlete_id)
        .order_by(Anomaly.created_at.asc())
        .all()
    )
    for anomaly in anomalies:
        events.append(
            AnomalyEvent(timestamp=anomaly.created_at, data=AnomalyOut.model_validate(anomaly))
        )

    cases = (
        db.query(Case).filter(Case.athlete_id == athlete_id).order_by(Case.opened_at.asc()).all()
    )
    for case in cases:
        # Both events reuse the same (current) row state -- there's no
        # historical snapshotting of a case's fields at open-time vs.
        # close-time, same class of "can't reconstruct past state"
        # limitation already documented for AnomalyDetail.contributing_
        # biomarkers in app.routes.athletes.get_athlete_anomalies.
        case_out = CaseOut.from_model(case)
        events.append(CaseOpenedEvent(timestamp=case.opened_at, data=case_out))
        if case.closed_at is not None:
            events.append(CaseClosedEvent(timestamp=case.closed_at, data=case_out))

    audit_logs = (
        db.query(AuditLog)
        .filter(AuditLog.athlete_id == athlete_id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    for audit_log in audit_logs:
        events.append(
            DecisionEvent(timestamp=audit_log.timestamp, data=AuditLogOut.from_model(audit_log))
        )

    events.sort(key=lambda event: (event.timestamp, _EVENT_TYPE_TIEBREAK_ORDER[event.type]))

    return AuditTimelineResponse(athlete_id=athlete_id, events=events)
