"""Integration tests for the products router.

Uses an in-memory SQLite database. The DATABASE_URL environment variable is
set BEFORE the application modules are imported so that ``database.py`` picks
up the test connection string.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Configure test database BEFORE importing application modules.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Make the service package importable when running pytest from any cwd.
SERVICE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402

# Build a dedicated test engine that shares a single connection across the
# whole test session — required for SQLite in-memory.
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
    """Truncate all tables between tests to keep them independent."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _sample_payload(**overrides) -> dict:
    payload = {
        "name": "Widget",
        "description": "A useful widget",
        "price": 9.99,
        "stock": 5,
    }
    payload.update(overrides)
    return payload


def test_create_product_returns_201_and_full_record(client: TestClient) -> None:
    response = client.post("/products/", json=_sample_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "Widget"
    assert body["price"] == 9.99
    assert body["stock"] == 5
    assert "created_at" in body
    assert "updated_at" in body


def test_list_products_returns_array(client: TestClient) -> None:
    client.post("/products/", json=_sample_payload(name="A"))
    client.post("/products/", json=_sample_payload(name="B"))

    response = client.get("/products/")
    assert response.status_code == 200
    products = response.json()
    assert isinstance(products, list)
    assert len(products) == 2
    names = {p["name"] for p in products}
    assert names == {"A", "B"}


def test_get_product_by_id_returns_200(client: TestClient) -> None:
    created = client.post("/products/", json=_sample_payload()).json()
    response = client.get(f"/products/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_nonexistent_product_returns_404(client: TestClient) -> None:
    response = client.get("/products/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_product_changes_the_name(client: TestClient) -> None:
    created = client.post("/products/", json=_sample_payload()).json()
    new_payload = _sample_payload(name="Renamed Widget", price=19.99, stock=10)
    response = client.put(f"/products/{created['id']}", json=new_payload)
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Widget"
    assert response.json()["price"] == 19.99


def test_patch_product_only_changes_supplied_fields(client: TestClient) -> None:
    created = client.post("/products/", json=_sample_payload()).json()
    response = client.patch(
        f"/products/{created['id']}",
        json={"price": 42.42},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == 42.42
    assert body["name"] == created["name"]


def test_delete_product_returns_success_message(client: TestClient) -> None:
    created = client.post("/products/", json=_sample_payload()).json()
    response = client.delete(f"/products/{created['id']}")
    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()
    assert client.get(f"/products/{created['id']}").status_code == 404


def test_health_endpoint_returns_status_healthy(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "api-service"
    assert body["version"] == "1.0.0"
