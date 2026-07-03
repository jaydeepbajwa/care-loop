import os

os.environ["DATABASE_URL"] = "sqlite://"  # in-memory; set before app imports read config

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory DB across sessions
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    # The app's own engine (DATABASE_URL=sqlite:// above) is a separate throwaway
    # in-memory DB; every request uses this fixture's engine via the override below.
    app = create_app()

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def enroll_member(client) -> str:
    """Walk a member through the full happy-path enrollment; returns the token."""
    token = client.post("/api/enrollment/start").json()["token"]
    client.post(
        f"/api/enrollment/{token}/eligibility",
        json={"cancer_diagnosis": True, "age_18_or_over": True, "insurance": "medicaid"},
    )
    client.post(f"/api/enrollment/{token}/consent")
    client.post(
        f"/api/enrollment/{token}/complete",
        json={
            "first_name": "Test",
            "last_name": "Member",
            "phone": "555-0100",
            "email": "test@example.com",
            "contact_preference": "sms",
        },
    )
    return token
