"""Core invariant #1: the enrollment funnel is monotonic and gate-ordered.

started >= eligibility_passed >= consented >= enrolled, and no step can be
skipped — you cannot enroll without consent, or consent without eligibility.
"""

from conftest import enroll_member

CARE = {"X-Care-Team": "nurse-rivera"}

ELIGIBLE = {"cancer_diagnosis": True, "age_18_or_over": True, "insurance": "medicaid"}
CONTACT = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "phone": "555-0199",
    "email": "ada@example.com",
    "contact_preference": "email",
}


def funnel(client) -> dict:
    return client.get("/api/care/funnel", headers=CARE).json()


def test_happy_path_emits_every_funnel_event_in_order(client):
    token = client.post("/api/enrollment/start").json()["token"]
    assert funnel(client) == {
        "started": 1,
        "eligibility_passed": 0,
        "eligibility_failed": 0,
        "consented": 0,
        "enrolled": 0,
    }

    client.post(f"/api/enrollment/{token}/eligibility", json=ELIGIBLE)
    client.post(f"/api/enrollment/{token}/consent")
    resp = client.post(f"/api/enrollment/{token}/complete", json=CONTACT)
    assert resp.status_code == 200
    assert resp.json()["status"] == "enrolled"

    f = funnel(client)
    assert f["started"] == f["eligibility_passed"] == f["consented"] == f["enrolled"] == 1


def test_cannot_consent_before_eligibility(client):
    token = client.post("/api/enrollment/start").json()["token"]
    resp = client.post(f"/api/enrollment/{token}/consent")
    assert resp.status_code == 409
    assert "eligibility" in resp.json()["detail"].lower()


def test_cannot_enroll_before_consent(client):
    token = client.post("/api/enrollment/start").json()["token"]
    client.post(f"/api/enrollment/{token}/eligibility", json=ELIGIBLE)
    resp = client.post(f"/api/enrollment/{token}/complete", json=CONTACT)
    assert resp.status_code == 409
    assert funnel(client)["enrolled"] == 0


def test_ineligible_member_is_stopped_and_counted(client):
    token = client.post("/api/enrollment/start").json()["token"]
    resp = client.post(
        f"/api/enrollment/{token}/eligibility",
        json={"cancer_diagnosis": False, "age_18_or_over": True, "insurance": "none"},
    )
    assert resp.json()["status"] == "ineligible"
    assert funnel(client)["eligibility_failed"] == 1

    consent = client.post(f"/api/enrollment/{token}/consent")
    assert consent.status_code == 409


def test_funnel_is_monotonic_across_a_mixed_cohort(client):
    # 4 start; 1 drops at eligibility, 1 fails, 1 stops after consent, 1 enrolls
    tokens = [client.post("/api/enrollment/start").json()["token"] for _ in range(4)]
    client.post(f"/api/enrollment/{tokens[1]}/eligibility",
                json={"cancer_diagnosis": False, "age_18_or_over": True, "insurance": "none"})
    for t in tokens[2:]:
        client.post(f"/api/enrollment/{t}/eligibility", json=ELIGIBLE)
        client.post(f"/api/enrollment/{t}/consent")
    client.post(f"/api/enrollment/{tokens[3]}/complete", json=CONTACT)

    f = funnel(client)
    assert f["started"] >= f["eligibility_passed"] >= f["consented"] >= f["enrolled"]
    assert f == {
        "started": 4,
        "eligibility_passed": 2,
        "eligibility_failed": 1,
        "consented": 2,
        "enrolled": 1,
    }


def test_enrollment_is_resumable_with_autosaved_state(client):
    token = client.post("/api/enrollment/start").json()["token"]
    client.patch(
        f"/api/enrollment/{token}",
        json={"first_name": "Rosa", "current_step": "eligibility"},
    )

    # Simulate coming back later: GET returns everything saved so far
    state = client.get(f"/api/enrollment/{token}").json()
    assert state["first_name"] == "Rosa"
    assert state["status"] == "in_progress"
    assert state["current_step"] == "eligibility"


def test_complete_is_idempotent(client):
    token = enroll_member(client)
    again = client.post(f"/api/enrollment/{token}/complete", json=CONTACT)
    assert again.status_code == 200
    assert funnel(client)["enrolled"] == 1  # no double-count
