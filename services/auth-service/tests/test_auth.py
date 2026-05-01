"""Integration tests for the auth-service."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Configure the test environment BEFORE importing the application.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-only-for-pytest"

SERVICE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine
)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _clean_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _register(client: TestClient, email: str = "alice@example.com") -> dict:
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": "Alice Example",
        },
    ).json()


def test_register_new_user_returns_201_and_email(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "bob@example.com",
            "password": "supersecret123",
            "full_name": "Bob",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "bob@example.com"
    assert body["full_name"] == "Bob"
    assert body["is_active"] is True
    assert "id" in body


def test_register_duplicate_email_returns_400(client: TestClient) -> None:
    _register(client)
    response = client.post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "password": "anotherpassword",
            "full_name": "Other",
        },
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_login_with_correct_credentials_returns_access_token(
    client: TestClient,
) -> None:
    _register(client)
    response = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "supersecret123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 20


def test_login_with_wrong_password_returns_401(client: TestClient) -> None:
    _register(client)
    response = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_me_endpoint_with_valid_token_returns_user_data(
    client: TestClient,
) -> None:
    _register(client)
    token = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "supersecret123"},
    ).json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_endpoint_with_no_token_returns_401(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_verify_with_valid_token_returns_valid_true(client: TestClient) -> None:
    _register(client)
    token = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "supersecret123"},
    ).json()["access_token"]

    response = client.get("/auth/verify", params={"token": token})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["email"] == "alice@example.com"


def test_verify_with_garbage_token_returns_valid_false(
    client: TestClient,
) -> None:
    response = client.get("/auth/verify", params={"token": "not-a-real-token"})
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_health_endpoint_returns_status_healthy(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "auth-service"
