import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def registered_operator(client):
    payload = {
        "company_name": "Test Aerial Co.",
        "contact_email": "test@testaerial.example",
        "password": "TestPass1234",
        "faa_certificate_number": "1234567",
        "phone_number": "+1-555-555-0100",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    return payload


@pytest.fixture()
def auth_headers(client, registered_operator):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "contact_email": registered_operator["contact_email"],
            "password": registered_operator["password"],
        },
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
