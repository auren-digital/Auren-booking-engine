from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    # Entering TestClient as a context manager runs the application's
    # startup lifecycle, which creates the SQLite schema before each test.
    with TestClient(app) as test_client:
        yield test_client


def payload(resource="vehicle-1", start=None, end=None):
    start = start or datetime.now(timezone.utc) + timedelta(days=1)
    end = end or start + timedelta(hours=2)
    return {
        "resource_id": resource,
        "customer_name": "Test Customer",
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
    }


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "auren-booking-engine"


def test_create_and_list_reservation(client):
    response = client.post("/api/v1/reservations", json=payload())
    assert response.status_code == 201
    reservation = response.json()
    assert reservation["status"] == "confirmed"
    listed = client.get(
        "/api/v1/reservations",
        params={"resource_id": reservation["resource_id"]},
    )
    assert listed.status_code == 200
    assert any(item["id"] == reservation["id"] for item in listed.json())


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
        json=payload(
            resource_id,
            start + timedelta(minutes=30),
            start + timedelta(hours=3),
        ),
    )
    assert second.status_code == 409


def test_reject_naive_datetime(client):
    data = payload()
    data["start_at"] = "2030-01-01T10:00:00"
    response = client.post("/api/v1/reservations", json=data)
    assert response.status_code == 422
