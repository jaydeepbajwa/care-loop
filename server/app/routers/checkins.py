"""Member-facing symptom check-ins.

The submit path is the one that pages on-call if it breaks: a sick patient
took the time to tell us how they feel, so persistence is non-negotiable.
Triage runs after the check-in is safely written, and any triage failure
degrades to the rules classifier rather than failing the request.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import triage
from ..db import get_db
from ..metrics import METRICS
from ..models import AuditLog, CheckIn, Member, TriageSuggestion
from ..schemas import CheckInCreate, CheckInOut

log = logging.getLogger("careloop.checkins")

router = APIRouter(prefix="/api/members", tags=["check-ins"])


def _get_enrolled_member(token: str, db: Session) -> Member:
    member = db.query(Member).filter(Member.token == token).one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Unknown member token.")
    if member.status != "enrolled":
        raise HTTPException(
            status_code=403,
            detail="Check-ins are available after enrollment is complete.",
        )
    return member


@router.post("/{token}/checkins", response_model=CheckInOut, status_code=201)
def submit_checkin(
    token: str, payload: CheckInCreate, db: Session = Depends(get_db)
) -> CheckIn:
    member = _get_enrolled_member(token, db)

    flagged, reason = triage.flag(payload)
    check_in = CheckIn(
        member_id=member.id,
        pain=payload.pain,
        fatigue=payload.fatigue,
        nausea=payload.nausea,
        appetite=payload.appetite,
        mood=payload.mood,
        free_text=payload.free_text,
        flagged=flagged,
        flag_reason=reason,
    )
    db.add(check_in)
    # Commit the check-in BEFORE triage: the member's report must survive
    # even if everything downstream fails.
    try:
        db.commit()
    except Exception:
        db.rollback()
        METRICS.incr("checkin_submit_errors_total")  # <- the on-call alert metric
        log.exception("check-in persistence failed", extra={"ctx": {"member_id": member.id}})
        raise HTTPException(
            status_code=503,
            detail="We couldn't save your check-in. Please try again in a moment — "
            "your answers are still on this page.",
        ) from None

    METRICS.incr("checkins_submitted_total")

    if flagged:
        assessment, source, model = triage.assess(payload, reason)
        suggestion = TriageSuggestion(
            check_in_id=check_in.id,
            severity=assessment.severity,
            suggested_action=assessment.suggested_action,
            rationale=assessment.rationale,
            source=source,
            model=model,
        )
        db.add(suggestion)
        db.flush()  # populate suggestion.id before the audit row references it
        db.add(
            AuditLog(
                event="suggestion_created",
                entity="triage_suggestion",
                entity_id=suggestion.id,
                actor="system",
                detail={
                    "check_in_id": check_in.id,
                    "severity": assessment.severity,
                    "source": source,
                    "model": model,
                },
            )
        )
        db.commit()
        log.info(
            "check-in flagged",
            extra={
                "ctx": {
                    "member_id": member.id,
                    "check_in_id": check_in.id,
                    "severity": assessment.severity,
                    "triage_source": source,
                }
            },
        )

    return check_in


@router.get("/{token}/checkins", response_model=list[CheckInOut])
def list_checkins(token: str, db: Session = Depends(get_db)) -> list[CheckIn]:
    member = _get_enrolled_member(token, db)
    return (
        db.query(CheckIn)
        .filter(CheckIn.member_id == member.id)
        .order_by(CheckIn.created_at.desc())
        .all()
    )
