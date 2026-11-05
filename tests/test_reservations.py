from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(main, "ADMIN_TOKEN", "test-admin-secret")
    with TestClient(main.app) as test_client:
        yield test_client


def payload(resource="vehicle-1", start=None, end=None, email="test@example.com"):
    start = start or datetime.now(timezone.utc) + timedelta(days=1)
    end = end or start + timedelta(hours=2)
    return {
        "resource_id": resource,
        "customer_name": "Test Customer",
        "customer_email": email,
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
    }


def admin_headers():
    return {"X-Admin-Token": "test-admin-secret"}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "auren-booking-engine"


def test_customer_create_and_private_lookup(client):
    created = client.post("/api/v1/reservations", json=payload())
    assert created.status_code == 201
    reservation = created.json()
    assert reservation["reference_code"].startswith("AUR-")

    found = client.get(
        f"/api/v1/public/reservations/{reservation['reference_code']}",
        params={"email": "TEST@example.com"},
    )
    assert found.status_code == 200
    assert found.json()["id"] == reservation["id"]

    wrong_email = client.get(
        f"/api/v1/public/reservations/{reservation['reference_code']}",
        params={"email": "wrong@example.com"},
    )
    assert wrong_email.status_code == 404


def test_admin_list_requires_token(client):
    client.post("/api/v1/reservations", json=payload())
    assert client.get("/api/v1/reservations").status_code == 401
    listed = client.get("/api/v1/reservations", headers=admin_headers())
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_reject_overlapping_reservation(client):
    start = datetime.now(timezone.utc) + timedelta(days=10)
    resource_id = f"vehicle-{uuid4()}"
    first = client.post(
        "/api/v1/reservations",
        json=payload(resource_id, start, start + timedelta(hours=2)),
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/reservations",
        json=payload(resource_id, start + timedelta(minutes=30), start + timedelta(hours=3)),
    )
    assert second.status_code == 409


def test_admin_cancel_requires_token_and_updates_reservation(client):
    created = client.post("/api/v1/reservations", json=payload()).json()
    url = f"/api/v1/reservations/{created['id']}/cancel"
    assert client.post(url).status_code == 401
    cancelled = client.post(url, headers=admin_headers())
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_reject_naive_datetime(client):
    data = payload()
    data["start_at"] = "2030-01-01T10:00:00"
    response = client.post("/api/v1/reservations", json=data)
    assert response.status_code == 422
