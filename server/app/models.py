import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Member(Base):
    """A person moving through the enrollment funnel.

    A row is created the moment enrollment *starts* (status="in_progress"),
    so partially-completed enrollments are resumable by token — a design
    requirement for sick, often older users who may not finish in one sitting.
    """

    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # The stubbed auth credential: the member's browser holds this token.
    # Real auth (OTP over SMS/email) is out of scope — see README "Honest limits".
    token: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_uuid)
    status: Mapped[str] = mapped_column(
        String(20), default="in_progress"
    )  # in_progress | ineligible | enrolled
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))
    contact_preference: Mapped[str | None] = mapped_column(String(10))  # sms | email | phone
    # Where the member left off, so the UI can resume mid-flow.
    current_step: Mapped[str] = mapped_column(String(30), default="eligibility")
    eligibility_answers: Mapped[dict | None] = mapped_column(JSON)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    check_ins: Mapped[list["CheckIn"]] = relationship(back_populates="member")


class FunnelEvent(Base):
    """Append-only enrollment funnel telemetry.

    started -> eligibility_passed/failed -> consent_given -> enrolled.
    This is the table a PM would query to score an enrollment experiment.
    """

    __tablename__ = "funnel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), index=True)
    event: Mapped[str] = mapped_column(String(40), index=True)
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CheckIn(Base):
    """A symptom check-in. Designed to take a patient under 60 seconds.

    Symptom scores use a 0-3 scale (none/mild/moderate/severe) because
    coarse scales are faster and more reliable for self-report than 0-10.
    """

    __tablename__ = "check_ins"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), index=True)
    pain: Mapped[int] = mapped_column(Integer)
    fatigue: Mapped[int] = mapped_column(Integer)
    nausea: Mapped[int] = mapped_column(Integer)
    appetite: Mapped[int] = mapped_column(Integer)
    mood: Mapped[int] = mapped_column(Integer)
    free_text: Mapped[str | None] = mapped_column(Text)
    # Flagging is deterministic (rules), independent of the LLM — the LLM can
    # add nuance to a suggestion but can never un-flag a concerning check-in.
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    member: Mapped[Member] = relationship(back_populates="check_ins")
    suggestion: Mapped["TriageSuggestion | None"] = relationship(back_populates="check_in")


class TriageSuggestion(Base):
    """An LLM (or rules) triage suggestion for a flagged check-in.

    Core invariant of this codebase: a suggestion NEVER acts on its own.
    It stays "pending" until a human accepts or overrides it, and the
    original suggestion is preserved verbatim either way.
    """

    __tablename__ = "triage_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    check_in_id: Mapped[str] = mapped_column(ForeignKey("check_ins.id"), unique=True)
    severity: Mapped[str] = mapped_column(String(10))  # low | moderate | high | urgent
    suggested_action: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(10))  # llm | rules
    model: Mapped[str | None] = mapped_column(String(60))  # model id when source == llm
    status: Mapped[str] = mapped_column(String(12), default="pending")
    # pending | accepted | overridden
    decided_by: Mapped[str | None] = mapped_column(String(100))
    decision_note: Mapped[str | None] = mapped_column(Text)
    # What the human actually decided (== suggestion on accept, differs on override)
    final_severity: Mapped[str | None] = mapped_column(String(10))
    final_action: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    check_in: Mapped[CheckIn] = relationship(back_populates="suggestion")


class AuditLog(Base):
    """Append-only record of every suggestion lifecycle event.

    In a care setting "the AI suggested X, nurse decided Y" must be
    reconstructable months later — so it is written at the same commit
    as the decision itself.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(40), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    actor: Mapped[str] = mapped_column(String(100))  # "system" or care-team identifier
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
