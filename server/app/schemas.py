from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Severity = Literal["low", "moderate", "high", "urgent"]
SymptomScore = Field(ge=0, le=3, description="0=none, 1=mild, 2=moderate, 3=severe")


# ---- Enrollment ----------------------------------------------------------


class EligibilityAnswers(BaseModel):
    cancer_diagnosis: bool
    age_18_or_over: bool
    insurance: Literal["medicare_advantage", "medicaid", "commercial", "none", "other"]


class EnrollmentDraft(BaseModel):
    """Partial autosave payload — every field optional so any step can save."""

    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    contact_preference: Literal["sms", "email", "phone"] | None = None
    current_step: str | None = None
    eligibility_answers: EligibilityAnswers | None = None


class ContactInfo(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    phone: str = Field(min_length=7)
    email: EmailStr
    contact_preference: Literal["sms", "email", "phone"]


class EnrollmentState(BaseModel):
    token: str
    status: str
    current_step: str
    first_name: str | None
    last_name: str | None
    phone: str | None
    email: str | None
    contact_preference: str | None
    eligibility_answers: EligibilityAnswers | None
    consented: bool


# ---- Check-ins ------------------------------------------------------------


class CheckInCreate(BaseModel):
    pain: int = SymptomScore
    fatigue: int = SymptomScore
    nausea: int = SymptomScore
    appetite: int = SymptomScore
    mood: int = SymptomScore
    free_text: str | None = Field(default=None, max_length=2000)


class CheckInOut(BaseModel):
    id: str
    pain: int
    fatigue: int
    nausea: int
    appetite: int
    mood: int
    free_text: str | None
    flagged: bool
    flag_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Triage ---------------------------------------------------------------


class TriageAssessment(BaseModel):
    """Structured output the LLM must produce — also the rules engine's shape."""

    severity: Severity
    suggested_action: str = Field(
        description="One concrete next step for the care team, e.g. "
        "'Call member today to assess uncontrolled nausea.'"
    )
    rationale: str = Field(description="1-2 sentences citing the specific symptoms/text.")


class SuggestionOut(BaseModel):
    id: str
    check_in_id: str
    severity: Severity
    suggested_action: str
    rationale: str
    source: str
    model: str | None
    status: str
    decided_by: str | None
    decision_note: str | None
    final_severity: str | None
    final_action: str | None
    created_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class Decision(BaseModel):
    action: Literal["accept", "override"]
    # Required when overriding — validated in the router so the 422 message can
    # say exactly what's missing.
    severity: Severity | None = None
    suggested_action: str | None = None
    note: str | None = None


# ---- Care team views -------------------------------------------------------


class QueueItem(BaseModel):
    member_name: str
    member_id: str
    check_in: CheckInOut
    suggestion: SuggestionOut


class MemberSummary(BaseModel):
    id: str
    name: str
    status: str
    enrolled_at: datetime | None
    last_check_in_at: datetime | None
    open_flags: int


class FunnelReport(BaseModel):
    started: int
    eligibility_passed: int
    eligibility_failed: int
    consented: int
    enrolled: int
