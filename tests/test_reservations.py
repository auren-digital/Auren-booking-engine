from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(resource="vehicle-1", start=None, end=None):
    start = start or datetime.now(timezone.utc) + timedelta(days=1)
    end = end or start + timedelta(hours=2)
    return {
        "resource_id": resource,
        "customer_name": "Test Customer",
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
    }


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "auren-booking-engine"


def test_create_and_list_reservation():
    response = client.post("/api/v1/reservations", json=payload())
    assert response.status_code == 201
    reservation = response.json()
    assert reservation["status"] == "confirmed"
    listed = client.get("/api/v1/reservations", params={"resource_id": reservation["resource_id"]})
    assert listed.status_code == 200
    assert any(item["id"] == reservation["id"] for item in listed.json())


def test_reject_overlapping_reservation():
    start = datetime.now(timezone.utc) + timedelta(days=10)
    first = client.post("/api/v1/reservations", json=payload("vehicle-overlap", start, start + timedelta(hours=2)))
    assert first.status_code == 201
    second = client.post("/api/v1/reservations", json=payload("vehicle-overlap", start + timedelta(minutes=30), start + timedelta(hours=3)))
    assert second.status_code == 409


def test_reject_naive_datetime():
    data = payload()
    data["start_at"] = "2030-01-01T10:00:00"
    response = client.post("/api/v1/reservations", json=data)
    assert response.status_code == 422
