"""Seed the demo database with synthetic members and check-ins.

Run: python -m app.seed   (idempotent — skips if members already exist)

All data is synthetic. No real PHI, ever.
"""

import logging
import random
from datetime import UTC, datetime, timedelta

from . import triage
from .db import Base, SessionLocal, engine
from .logging_setup import configure_logging
from .models import AuditLog, CheckIn, FunnelEvent, Member, TriageSuggestion
from .schemas import CheckInCreate

log = logging.getLogger("careloop.seed")

FIXED_DEMO_TOKEN = "demo-member-token"

ENROLLED = [
    ("Rosa", "Martinez", "sms"),
    ("Walter", "Okafor", "phone"),
    ("Priya", "Natarajan", "email"),
    ("James", "Whitfield", "phone"),
    ("Elaine", "Kowalski", "sms"),
]

# (scores: pain, fatigue, nausea, appetite, mood), free text, days ago
CHECK_INS = [
    ((1, 1, 0, 1, 1), "Feeling pretty good this week, just tired after chemo on Tuesday.", 6),
    ((0, 2, 1, 1, 0), None, 5),
    ((2, 2, 1, 2, 2), "Appetite has really dropped and food tastes metallic.", 3),
    (
        (3, 2, 1, 1, 2),
        "The pain in my back is much worse since yesterday, ibuprofen isn't touching it.",
        1,
    ),
    ((1, 3, 2, 2, 1), "So exhausted I couldn't get out of bed until noon.", 1),
    ((1, 1, 0, 0, 3), "Honestly feeling very low and hopeless this week.", 0),
    ((2, 1, 3, 2, 1), "Can't keep anything down since this morning.", 0),
    ((0, 1, 0, 1, 0), "Doing okay. Walked to the mailbox today!", 0),
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Member).count() > 0:
            log.info("database already seeded; skipping")
            return

        now = datetime.now(UTC)

        # Funnel dropouts: started-only, failed eligibility, consented-not-finished
        for _ in range(3):
            m = Member(status="in_progress", current_step="eligibility")
            db.add(m)
            db.flush()
            db.add(FunnelEvent(member_id=m.id, event="started"))
        m = Member(
            status="ineligible",
            current_step="ineligible",
            eligibility_answers={
                "cancer_diagnosis": False,
                "age_18_or_over": True,
                "insurance": "commercial",
            },
        )
        db.add(m)
        db.flush()
        db.add(FunnelEvent(member_id=m.id, event="started"))
        db.add(FunnelEvent(member_id=m.id, event="eligibility_failed"))
        m = Member(status="in_progress", current_step="contact", consented_at=now)
        db.add(m)
        db.flush()
        for event in ("started", "eligibility_passed", "consent_given"):
            db.add(FunnelEvent(member_id=m.id, event=event))

        # Enrolled members
        members: list[Member] = []
        for i, (first, last, pref) in enumerate(ENROLLED):
            m = Member(
                first_name=first,
                last_name=last,
                phone=f"555-01{i:02d}",
                email=f"{first.lower()}.{last.lower()}@example.com",
                contact_preference=pref,
                status="enrolled",
                current_step="done",
                consented_at=now - timedelta(days=20 - i),
                enrolled_at=now - timedelta(days=20 - i),
                eligibility_answers={
                    "cancer_diagnosis": True,
                    "age_18_or_over": True,
                    "insurance": "medicare_advantage",
                },
            )
            if i == 0:
                m.token = FIXED_DEMO_TOKEN  # stable token so the demo UI just works
            db.add(m)
            db.flush()
            for event in ("started", "eligibility_passed", "consent_given", "enrolled"):
                db.add(FunnelEvent(member_id=m.id, event=event))
            members.append(m)

        # Check-ins with rules-based triage (no API key needed to seed)
        rng = random.Random(42)
        for scores, text, days_ago in CHECK_INS:
            member = rng.choice(members)
            payload = CheckInCreate(
                pain=scores[0],
                fatigue=scores[1],
                nausea=scores[2],
                appetite=scores[3],
                mood=scores[4],
                free_text=text,
            )
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
                created_at=now - timedelta(days=days_ago, hours=rng.randint(0, 8)),
            )
            db.add(check_in)
            db.flush()
            if flagged:
                assessment = triage.rules_assessment(payload, reason)
                suggestion = TriageSuggestion(
                    check_in_id=check_in.id,
                    severity=assessment.severity,
                    suggested_action=assessment.suggested_action,
                    rationale=assessment.rationale,
                    source="rules",
                )
                db.add(suggestion)
                db.flush()
                db.add(
                    AuditLog(
                        event="suggestion_created",
                        entity="triage_suggestion",
                        entity_id=suggestion.id,
                        actor="system",
                        detail={"check_in_id": check_in.id, "source": "rules"},
                    )
                )

        db.commit()
        log.info(
            "seeded demo data",
            extra={"ctx": {"members": len(members), "check_ins": len(CHECK_INS)}},
        )
        print(f"\nSeeded. Demo member token: {FIXED_DEMO_TOKEN}\n")
    finally:
        db.close()


if __name__ == "__main__":
    configure_logging()
    seed()
