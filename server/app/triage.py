"""Triage: turn a symptom check-in into a suggested next step for a human.

Two-layer design, and the layering is the point:

1. `flag()` — deterministic rules decide IF a check-in needs attention.
   The LLM never gets to un-flag something the rules caught.
2. `assess()` — the LLM (when configured) drafts severity + a suggested
   action for the care team. If the API key is missing, the call fails,
   or the response is malformed, we degrade to `rules_assessment()`.
   A check-in submission must NEVER fail because triage did.

Suggestions are exactly that — suggestions. Nothing here mutates member
state; only a care-team decision endpoint does.
"""

import logging

from anthropic import Anthropic

from .config import get_settings
from .metrics import METRICS
from .schemas import CheckInCreate, TriageAssessment

log = logging.getLogger("careloop.triage")

# Free-text phrases that always warrant urgent attention regardless of scores.
# Deliberately broad: in triage, a false positive costs a phone call; a false
# negative costs much more.
URGENT_PHRASES = (
    "chest pain",
    "can't breathe",
    "cannot breathe",
    "trouble breathing",
    "shortness of breath",
    "coughing blood",
    "blood in",
    "bleeding",
    "fever",
    "103",
    "suicid",
    "end my life",
    "kill myself",
    "passed out",
    "fainted",
)

SCORE_LABELS = {0: "none", 1: "mild", 2: "moderate", 3: "severe"}


def flag(check_in: CheckInCreate) -> tuple[bool, str | None]:
    """Deterministic flagging rules. Returns (flagged, reason)."""
    text = (check_in.free_text or "").lower()
    for phrase in URGENT_PHRASES:
        if phrase in text:
            return True, f"urgent phrase in free text: '{phrase}'"

    scores = _scores(check_in)
    severe = [name for name, s in scores.items() if s == 3]
    if severe:
        return True, f"severe symptom(s): {', '.join(severe)}"

    moderate = [name for name, s in scores.items() if s == 2]
    if len(moderate) >= 2:
        return True, f"multiple moderate symptoms: {', '.join(moderate)}"

    return False, None


def rules_assessment(check_in: CheckInCreate, flag_reason: str | None) -> TriageAssessment:
    """Deterministic fallback assessment — used when the LLM is unavailable."""
    text = (check_in.free_text or "").lower()
    if any(p in text for p in URGENT_PHRASES):
        return TriageAssessment(
            severity="urgent",
            suggested_action="Call member immediately; free text mentions a red-flag symptom.",
            rationale=f"Rules classifier: {flag_reason}.",
        )
    scores = _scores(check_in)
    if any(s == 3 for s in scores.values()):
        return TriageAssessment(
            severity="high",
            suggested_action="Call member today to assess the severe symptom(s).",
            rationale=f"Rules classifier: {flag_reason}.",
        )
    return TriageAssessment(
        severity="moderate",
        suggested_action="Reach out within 48h via the member's preferred contact channel.",
        rationale=f"Rules classifier: {flag_reason}.",
    )


def assess(
    check_in: CheckInCreate, flag_reason: str | None
) -> tuple[TriageAssessment, str, str | None]:
    """Produce an assessment. Returns (assessment, source, model_id).

    source is "llm" or "rules"; model_id is set only for LLM assessments.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return rules_assessment(check_in, flag_reason), "rules", None

    try:
        assessment = _llm_assessment(check_in)
        return assessment, "llm", settings.triage_model
    except Exception:
        # Whatever went wrong (network, rate limit, malformed output), the
        # member's check-in must still land. Degrade loudly, not silently.
        METRICS.incr("triage_llm_failures_total")
        log.exception(
            "LLM triage failed; falling back to rules classifier",
            extra={"ctx": {"fallback": "rules"}},
        )
        return rules_assessment(check_in, flag_reason), "rules", None


def _llm_assessment(check_in: CheckInCreate) -> TriageAssessment:
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)
    scores = _scores(check_in)
    score_lines = "\n".join(f"- {name}: {SCORE_LABELS[s]} ({s}/3)" for name, s in scores.items())

    response = client.messages.parse(
        model=settings.triage_model,
        max_tokens=1024,
        system=(
            "You are a triage assistant for an oncology care-navigation team. "
            "You draft a severity assessment and ONE concrete suggested next step "
            "for a nurse to review. You never contact the member and your output "
            "is always reviewed by a human before any action is taken. "
            "Severity scale: low (routine), moderate (contact within 48h), "
            "high (contact today), urgent (contact immediately)."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Symptom self-report:\n{score_lines}\n\n"
                    f"Member's own words: {check_in.free_text or '(none provided)'}"
                ),
            }
        ],
        output_format=TriageAssessment,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError("model returned no parsable assessment")
    return parsed


def _scores(check_in: CheckInCreate) -> dict[str, int]:
    return {
        "pain": check_in.pain,
        "fatigue": check_in.fatigue,
        "nausea": check_in.nausea,
        "appetite": check_in.appetite,
        "mood": check_in.mood,
    }
