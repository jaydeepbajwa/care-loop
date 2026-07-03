"""Member enrollment: start -> eligibility -> consent -> contact info -> enrolled.

Every step autosaves and every transition writes a funnel event. The flow is
resumable: the browser holds the member token and GET returns saved state.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..metrics import METRICS
from ..models import FunnelEvent, Member
from ..schemas import ContactInfo, EligibilityAnswers, EnrollmentDraft, EnrollmentState

log = logging.getLogger("careloop.enrollment")

router = APIRouter(prefix="/api/enrollment", tags=["enrollment"])

# States CareLoop serves in this demo. Not used for eligibility (cancer dx,
# age, insurance are the gates) but kept here as the natural next question.
ELIGIBLE_INSURANCE = {"medicare_advantage", "medicaid", "commercial"}


def _get_member(token: str, db: Session) -> Member:
    member = db.query(Member).filter(Member.token == token).one_or_none()
    if member is None:
        raise HTTPException(
            status_code=404,
            detail="No enrollment found for this token. "
            "Start a new enrollment at POST /api/enrollment/start.",
        )
    return member


def _funnel(db: Session, member: Member, event: str, detail: dict | None = None) -> None:
    db.add(FunnelEvent(member_id=member.id, event=event, detail=detail))


def _state(member: Member) -> EnrollmentState:
    return EnrollmentState(
        token=member.token,
        status=member.status,
        current_step=member.current_step,
        first_name=member.first_name,
        last_name=member.last_name,
        phone=member.phone,
        email=member.email,
        contact_preference=member.contact_preference,
        eligibility_answers=(
            EligibilityAnswers(**member.eligibility_answers) if member.eligibility_answers else None
        ),
        consented=member.consented_at is not None,
    )


@router.post("/start", response_model=EnrollmentState, status_code=201)
def start(db: Session = Depends(get_db)) -> EnrollmentState:
    member = Member()
    db.add(member)
    db.flush()
    _funnel(db, member, "started")
    db.commit()
    METRICS.incr("enrollments_started_total")
    log.info("enrollment started", extra={"ctx": {"member_id": member.id}})
    return _state(member)


@router.get("/{token}", response_model=EnrollmentState)
def resume(token: str, db: Session = Depends(get_db)) -> EnrollmentState:
    return _state(_get_member(token, db))


@router.patch("/{token}", response_model=EnrollmentState)
def autosave(token: str, draft: EnrollmentDraft, db: Session = Depends(get_db)) -> EnrollmentState:
    """Autosave any subset of fields. Called by the UI on every step change."""
    member = _get_member(token, db)
    if member.status == "enrolled":
        raise HTTPException(status_code=409, detail="Enrollment already completed.")
    data = draft.model_dump(exclude_unset=True)
    answers = data.pop("eligibility_answers", None)
    if answers is not None:
        member.eligibility_answers = answers
    for field, value in data.items():
        setattr(member, field, value)
    db.commit()
    return _state(member)


@router.post("/{token}/eligibility", response_model=EnrollmentState)
def submit_eligibility(
    token: str, answers: EligibilityAnswers, db: Session = Depends(get_db)
) -> EnrollmentState:
    member = _get_member(token, db)
    if member.status == "enrolled":
        raise HTTPException(status_code=409, detail="Enrollment already completed.")
    member.eligibility_answers = answers.model_dump()

    eligible = (
        answers.cancer_diagnosis
        and answers.age_18_or_over
        and answers.insurance in ELIGIBLE_INSURANCE
    )
    if eligible:
        member.current_step = "consent"
        _funnel(db, member, "eligibility_passed")
    else:
        member.status = "ineligible"
        member.current_step = "ineligible"
        _funnel(db, member, "eligibility_failed", detail=answers.model_dump())
    db.commit()
    return _state(member)


@router.post("/{token}/consent", response_model=EnrollmentState)
def give_consent(token: str, db: Session = Depends(get_db)) -> EnrollmentState:
    member = _get_member(token, db)
    if member.status != "in_progress" or member.current_step not in ("consent", "contact"):
        raise HTTPException(
            status_code=409,
            detail="Consent requires a passed eligibility check first (POST .../eligibility).",
        )
    if member.consented_at is None:
        member.consented_at = datetime.now(UTC)
        member.current_step = "contact"
        _funnel(db, member, "consent_given")
        db.commit()
    return _state(member)


@router.post("/{token}/complete", response_model=EnrollmentState)
def complete(token: str, contact: ContactInfo, db: Session = Depends(get_db)) -> EnrollmentState:
    member = _get_member(token, db)
    if member.status == "enrolled":
        return _state(member)  # idempotent: re-submitting a finished flow is fine
    if member.consented_at is None:
        raise HTTPException(
            status_code=409,
            detail="Cannot enroll before consent is given (POST .../consent).",
        )
    for field, value in contact.model_dump().items():
        setattr(member, field, value)
    member.status = "enrolled"
    member.current_step = "done"
    member.enrolled_at = datetime.now(UTC)
    _funnel(db, member, "enrolled")
    db.commit()
    METRICS.incr("enrollments_completed_total")
    log.info("member enrolled", extra={"ctx": {"member_id": member.id}})
    return _state(member)
