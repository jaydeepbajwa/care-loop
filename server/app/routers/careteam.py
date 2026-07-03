"""Care-team surfaces: member roster, flagged queue, and suggestion decisions.

Auth is stubbed with an X-Care-Team header naming the clinician (see README
"Honest limits"). The decision endpoint is the ONLY place in the codebase
where a triage suggestion turns into an outcome — and every decision writes
an audit row in the same transaction.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, CheckIn, FunnelEvent, Member, TriageSuggestion
from ..schemas import (
    CheckInOut,
    Decision,
    FunnelReport,
    MemberSummary,
    QueueItem,
    SuggestionOut,
)

router = APIRouter(prefix="/api/care", tags=["care-team"])


def care_team_actor(x_care_team: str | None = Header(default=None)) -> str:
    if not x_care_team:
        raise HTTPException(
            status_code=401,
            detail="Care-team endpoints need an X-Care-Team header identifying you, "
            "e.g. X-Care-Team: nurse-rivera. (Stub for real auth — see README.)",
        )
    return x_care_team


@router.get("/members", response_model=list[MemberSummary])
def list_members(
    db: Session = Depends(get_db), actor: str = Depends(care_team_actor)
) -> list[MemberSummary]:
    members = db.query(Member).filter(Member.status == "enrolled").all()
    summaries = []
    for m in members:
        last = (
            db.query(func.max(CheckIn.created_at)).filter(CheckIn.member_id == m.id).scalar()
        )
        open_flags = (
            db.query(func.count(TriageSuggestion.id))
            .join(CheckIn, CheckIn.id == TriageSuggestion.check_in_id)
            .filter(CheckIn.member_id == m.id, TriageSuggestion.status == "pending")
            .scalar()
        )
        summaries.append(
            MemberSummary(
                id=m.id,
                name=f"{m.first_name} {m.last_name}",
                status=m.status,
                enrolled_at=m.enrolled_at,
                last_check_in_at=last,
                open_flags=open_flags or 0,
            )
        )
    # Most urgent first: members with open flags, then by recency
    summaries.sort(key=lambda s: (-s.open_flags, s.name))
    return summaries


@router.get("/queue", response_model=list[QueueItem])
def flagged_queue(
    db: Session = Depends(get_db), actor: str = Depends(care_team_actor)
) -> list[QueueItem]:
    severity_rank = {"urgent": 0, "high": 1, "moderate": 2, "low": 3}
    rows = (
        db.query(TriageSuggestion, CheckIn, Member)
        .join(CheckIn, CheckIn.id == TriageSuggestion.check_in_id)
        .join(Member, Member.id == CheckIn.member_id)
        .filter(TriageSuggestion.status == "pending")
        .all()
    )
    items = [
        QueueItem(
            member_name=f"{member.first_name} {member.last_name}",
            member_id=member.id,
            check_in=CheckInOut.model_validate(check_in),
            suggestion=SuggestionOut.model_validate(suggestion),
        )
        for suggestion, check_in, member in rows
    ]
    items.sort(key=lambda i: (severity_rank.get(i.suggestion.severity, 9), i.check_in.created_at))
    return items


@router.post("/suggestions/{suggestion_id}/decision", response_model=SuggestionOut)
def decide(
    suggestion_id: str,
    decision: Decision,
    db: Session = Depends(get_db),
    actor: str = Depends(care_team_actor),
) -> TriageSuggestion:
    suggestion = db.get(TriageSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    if suggestion.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Already decided ({suggestion.status} by {suggestion.decided_by}). "
            "Decisions are final so the audit trail stays truthful.",
        )

    if decision.action == "accept":
        suggestion.final_severity = suggestion.severity
        suggestion.final_action = suggestion.suggested_action
        suggestion.status = "accepted"
    else:
        if not decision.severity or not decision.suggested_action:
            raise HTTPException(
                status_code=422,
                detail="An override must include the corrected 'severity' and "
                "'suggested_action' so the record shows what was decided instead.",
            )
        # The original severity/suggested_action columns are never touched —
        # an override records what the human chose alongside what the model said.
        suggestion.final_severity = decision.severity
        suggestion.final_action = decision.suggested_action
        suggestion.status = "overridden"

    suggestion.decided_by = actor
    suggestion.decision_note = decision.note
    suggestion.decided_at = datetime.now(UTC)

    db.add(
        AuditLog(
            event=f"suggestion_{suggestion.status}",
            entity="triage_suggestion",
            entity_id=suggestion.id,
            actor=actor,
            detail={
                "original": {
                    "severity": suggestion.severity,
                    "suggested_action": suggestion.suggested_action,
                    "source": suggestion.source,
                },
                "final": {
                    "severity": suggestion.final_severity,
                    "suggested_action": suggestion.final_action,
                },
                "note": decision.note,
            },
        )
    )
    db.commit()
    return suggestion


@router.get("/funnel", response_model=FunnelReport)
def funnel(db: Session = Depends(get_db), actor: str = Depends(care_team_actor)) -> FunnelReport:
    counts = dict(
        db.query(FunnelEvent.event, func.count(FunnelEvent.id))
        .group_by(FunnelEvent.event)
        .all()
    )
    return FunnelReport(
        started=counts.get("started", 0),
        eligibility_passed=counts.get("eligibility_passed", 0),
        eligibility_failed=counts.get("eligibility_failed", 0),
        consented=counts.get("consent_given", 0),
        enrolled=counts.get("enrolled", 0),
    )
