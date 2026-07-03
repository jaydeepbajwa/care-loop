"""Core invariant #2: triage suggests, humans decide.

- A suggestion never changes state on its own; only /decision does.
- Overrides preserve the original suggestion verbatim.
- Every lifecycle event lands in the audit log.
- LLM failure degrades to rules and never blocks a check-in.
"""

import pytest
from conftest import enroll_member

from app import triage
from app.schemas import CheckInCreate

CARE = {"X-Care-Team": "nurse-rivera"}

SEVERE_CHECKIN = {"pain": 3, "fatigue": 1, "nausea": 0, "appetite": 1, "mood": 1,
                  "free_text": "Pain flared up badly overnight."}
MILD_CHECKIN = {"pain": 0, "fatigue": 1, "nausea": 0, "appetite": 0, "mood": 0,
                "free_text": "Feeling pretty good today."}


# ---- rules classifier ------------------------------------------------------

def test_urgent_phrase_flags_regardless_of_low_scores():
    payload = CheckInCreate(pain=0, fatigue=0, nausea=0, appetite=0, mood=0,
                            free_text="Having chest pain since lunch")
    flagged, reason = triage.flag(payload)
    assert flagged and "chest pain" in reason
    assert triage.rules_assessment(payload, reason).severity == "urgent"


def test_severe_score_flags_as_high():
    payload = CheckInCreate(**SEVERE_CHECKIN)
    flagged, reason = triage.flag(payload)
    assert flagged and "pain" in reason
    assert triage.rules_assessment(payload, reason).severity == "high"


def test_two_moderate_symptoms_flag_as_moderate():
    payload = CheckInCreate(pain=2, fatigue=2, nausea=0, appetite=0, mood=0, free_text=None)
    flagged, reason = triage.flag(payload)
    assert flagged
    assert triage.rules_assessment(payload, reason).severity == "moderate"


def test_mild_checkin_is_not_flagged():
    flagged, reason = triage.flag(CheckInCreate(**MILD_CHECKIN))
    assert not flagged and reason is None


# ---- degradation -----------------------------------------------------------

def test_llm_failure_degrades_to_rules_and_checkin_still_lands(client, monkeypatch):
    def boom(check_in):
        raise RuntimeError("simulated API outage")

    monkeypatch.setattr(triage, "_llm_assessment", boom)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    triage.get_settings.cache_clear()  # pick up the env var
    try:
        token = enroll_member(client)
        resp = client.post(f"/api/members/{token}/checkins", json=SEVERE_CHECKIN)
        assert resp.status_code == 201  # the member's report survived the outage

        queue = client.get("/api/care/queue", headers=CARE).json()
        assert len(queue) == 1
        assert queue[0]["suggestion"]["source"] == "rules"  # degraded, not dropped
        assert queue[0]["suggestion"]["model"] is None
    finally:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
        triage.get_settings.cache_clear()


# ---- human-in-the-loop invariant -------------------------------------------

@pytest.fixture()
def pending_suggestion(client):
    token = enroll_member(client)
    client.post(f"/api/members/{token}/checkins", json=SEVERE_CHECKIN)
    queue = client.get("/api/care/queue", headers=CARE).json()
    assert len(queue) == 1
    return queue[0]["suggestion"]


def test_suggestion_starts_pending_and_never_auto_acts(pending_suggestion):
    assert pending_suggestion["status"] == "pending"
    assert pending_suggestion["final_severity"] is None
    assert pending_suggestion["final_action"] is None
    assert pending_suggestion["decided_by"] is None


def test_accept_records_the_human_and_mirrors_the_suggestion(client, pending_suggestion):
    resp = client.post(
        f"/api/care/suggestions/{pending_suggestion['id']}/decision",
        json={"action": "accept", "note": "Agree, calling now."},
        headers=CARE,
    )
    decided = resp.json()
    assert decided["status"] == "accepted"
    assert decided["decided_by"] == "nurse-rivera"
    assert decided["final_severity"] == decided["severity"]
    assert decided["final_action"] == decided["suggested_action"]


def test_override_preserves_the_original_suggestion(client, pending_suggestion):
    resp = client.post(
        f"/api/care/suggestions/{pending_suggestion['id']}/decision",
        json={
            "action": "override",
            "severity": "urgent",
            "suggested_action": "Escalating to on-call NP immediately.",
            "note": "Member has a history that makes this urgent.",
        },
        headers=CARE,
    )
    decided = resp.json()
    assert decided["status"] == "overridden"
    # The model's original words are untouched — that's the audit contract
    assert decided["severity"] == pending_suggestion["severity"]
    assert decided["suggested_action"] == pending_suggestion["suggested_action"]
    assert decided["final_severity"] == "urgent"


def test_override_without_correction_is_rejected_with_guidance(client, pending_suggestion):
    resp = client.post(
        f"/api/care/suggestions/{pending_suggestion['id']}/decision",
        json={"action": "override"},
        headers=CARE,
    )
    assert resp.status_code == 422
    assert "severity" in resp.json()["detail"]


def test_decisions_are_final(client, pending_suggestion):
    url = f"/api/care/suggestions/{pending_suggestion['id']}/decision"
    client.post(url, json={"action": "accept"}, headers=CARE)
    resp = client.post(url, json={"action": "accept"}, headers=CARE)
    assert resp.status_code == 409


def test_care_endpoints_require_identity(client):
    resp = client.get("/api/care/queue")
    assert resp.status_code == 401
    assert "X-Care-Team" in resp.json()["detail"]


def test_unflagged_checkin_creates_no_suggestion(client):
    token = enroll_member(client)
    client.post(f"/api/members/{token}/checkins", json=MILD_CHECKIN)
    queue = client.get("/api/care/queue", headers=CARE).json()
    assert queue == []
