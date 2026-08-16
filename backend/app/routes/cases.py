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
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy.orm import Session

from app.db.models import Athlete, AuditLog, Case
from app.db.session import get_db

router = APIRouter()

DecisionAction = Literal["escalate", "clear", "request_more_testing", "close_case"]

# Per api-contract.md: only this action flips case.status to "closed" /
# sets closed_at; every other action still writes an AuditLog row but
# leaves the case otherwise unchanged.
_CLOSING_ACTION: DecisionAction = "close_case"


def _parse_details_json(details_json: str | None) -> dict[str, object]:
    return json.loads(details_json) if details_json else {}


class NewCaseInput(BaseModel):
    athlete_id: int
    notes: str | None = None


class CaseOut(BaseModel):
    id: int
    athlete_id: int
    status: Literal["open", "closed"]
    opened_at: datetime
    closed_at: datetime | None
    investigator_notes: str | None

    @field_serializer("opened_at")
    def _serialize_opened_at(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    @field_serializer("closed_at")
    def _serialize_closed_at(self, value: datetime | None) -> str | None:
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
    case_id: int | None
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
