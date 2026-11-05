from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "booking-test.db"))
    monkeypatch.setattr(main, "PLATFORM_TOKEN", "platform-test-secret")
    monkeypatch.setattr(main, "LEGACY_ADMIN_TOKEN", "default-admin-secret")
    with TestClient(main.app) as test_client:
        yield test_client


def create_tenant(client, slug):
    response = client.post(
        "/api/v1/platform/tenants",
        headers={"X-Platform-Token": "platform-test-secret"},
        json={"name": f"Empresa {slug}", "slug": slug},
    )
    assert response.status_code == 201
    return response.json()["admin_token"]


def reservation_payload(resource="room-1"):
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(hours=1)
    return {
        "resource_id": resource,
        "customer_name": "Cliente de prueba",
        "customer_email": "cliente@example.com",
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "notes": "Prueba automatizada",
    }


def test_health_reports_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_platform_provisioning_requires_platform_token(client):
    response = client.post(
        "/api/v1/platform/tenants",
        json={"name": "Hotel Uno", "slug": "hotel-uno"},
    )
    assert response.status_code == 401


def test_platform_can_create_workspace_and_token_is_usable(client):
    admin_token = create_tenant(client, "hotel-uno")
    response = client.get(
        "/api/v1/reservations",
        headers={"X-Admin-Token": admin_token},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_duplicate_workspace_slug_is_rejected(client):
    create_tenant(client, "hotel-uno")
    response = client.post(
        "/api/v1/platform/tenants",
        headers={"X-Platform-Token": "platform-test-secret"},
        json={"name": "Hotel Duplicado", "slug": "hotel-uno"},
    )
    assert response.status_code == 409


def test_public_booking_requires_valid_tenant(client):
    response = client.post("/api/v1/reservations", json=reservation_payload())
    assert response.status_code == 400


def test_reservations_are_isolated_between_tenants(client):
    admin_one = create_tenant(client, "hotel-uno")
    admin_two = create_tenant(client, "hotel-dos")

    created_one = client.post(
        "/api/v1/reservations",
        headers={"X-Tenant-ID": "hotel-uno"},
        json=reservation_payload(),
    )
    created_two = client.post(
        "/api/v1/reservations",
        headers={"X-Tenant-ID": "hotel-dos"},
        json=reservation_payload(),
    )

    assert created_one.status_code == 201
    assert created_two.status_code == 201
    assert created_one.json()["reference_code"] != created_two.json()["reference_code"]

    list_one = client.get("/api/v1/reservations", headers={"X-Admin-Token": admin_one})
    list_two = client.get("/api/v1/reservations", headers={"X-Admin-Token": admin_two})
    assert len(list_one.json()) == 1
    assert len(list_two.json()) == 1
    assert list_one.json()[0]["id"] == created_one.json()["id"]
    assert list_two.json()[0]["id"] == created_two.json()["id"]


def test_overlap_is_blocked_within_tenant(client):
    admin_token = create_tenant(client, "hotel-uno")
    headers = {"X-Tenant-ID": "hotel-uno"}
    first = client.post("/api/v1/reservations", headers=headers, json=reservation_payload())
    second = client.post("/api/v1/reservations", headers=headers, json=reservation_payload())
    assert first.status_code == 201
    assert second.status_code == 409
    assert client.get("/api/v1/reservations", headers={"X-Admin-Token": admin_token}).status_code == 200


def test_admin_cannot_read_or_cancel_another_tenant_reservation(client):
    admin_one = create_tenant(client, "hotel-uno")
    admin_two = create_tenant(client, "hotel-dos")
    created = client.post(
        "/api/v1/reservations",
        headers={"X-Tenant-ID": "hotel-uno"},
        json=reservation_payload(),
    ).json()

    list_two = client.get("/api/v1/reservations", headers={"X-Admin-Token": admin_two})
    cancel_two = client.post(
        f"/api/v1/reservations/{created['id']}/cancel",
        headers={"X-Admin-Token": admin_two},
    )
    assert list_two.status_code == 200
    assert list_two.json() == []
    assert cancel_two.status_code == 404

    cancel_one = client.post(
        f"/api/v1/reservations/{created['id']}/cancel",
        headers={"X-Admin-Token": admin_one},
    )
    assert cancel_one.status_code == 200
    assert cancel_one.json()["status"] == "cancelled"


def test_public_lookup_requires_tenant_and_email(client):
    create_tenant(client, "hotel-uno")
    created = client.post(
        "/api/v1/reservations",
        headers={"X-Tenant-ID": "hotel-uno"},
        json=reservation_payload(),
    ).json()

    headers = {"X-Tenant-ID": "hotel-uno"}
    good = client.get(
        f"/api/v1/public/reservations/{created['reference_code']}",
        params={"email": "CLIENTE@example.com"},
        headers=headers,
    )
    wrong_tenant = client.get(
        f"/api/v1/public/reservations/{created['reference_code']}",
        params={"email": "cliente@example.com"},
        headers={"X-Tenant-ID": "hotel-dos"},
    )
    wrong_email = client.get(
        f"/api/v1/public/reservations/{created['reference_code']}",
        params={"email": "other@example.com"},
        headers=headers,
    )
    assert good.status_code == 200
    assert wrong_tenant.status_code == 404
    assert wrong_email.status_code == 404


def test_default_legacy_admin_token_stays_scoped_to_default(client):
    response = client.get(
        "/api/v1/reservations",
        headers={"X-Admin-Token": "default-admin-secret"},
    )
    assert response.status_code == 200
    assert response.json() == []



def test_resource_catalog_is_tenant_scoped_and_reservations_require_resource(client):
    admin_one = create_tenant(client, "hotel-uno")
    admin_two = create_tenant(client, "hotel-dos")
    headers_one = {"X-Tenant-ID": "hotel-uno"}
    public_resources = client.get("/api/v1/public/resources", headers=headers_one)
    assert public_resources.status_code == 200
    assert any(item["id"] == "room-1" for item in public_resources.json())

    created = client.post(
        "/api/v1/resources",
        headers={"X-Admin-Token": admin_one},
        json={"id": "spa-room", "name": "Sala de spa", "category": "room", "capacity": 2},
    )
    assert created.status_code == 201
    assert created.json()["capacity"] == 2

    other_resources = client.get("/api/v1/resources", headers={"X-Admin-Token": admin_two})
    assert all(item["id"] != "spa-room" for item in other_resources.json())

    invalid = client.post(
        "/api/v1/reservations",
        headers=headers_one,
        json=reservation_payload(resource="unknown-resource"),
    )
    assert invalid.status_code == 422


def test_customer_and_admin_portals_are_served_by_api_origin(client):
    customer = client.get("/web/index.html")
    admin = client.get("/web/admin.html")
    assert customer.status_code == 200
    assert 'id="customerForm"' in customer.text
    assert admin.status_code == 200
    assert 'AUREN Booking Engine' in admin.text


def test_capacity_allows_group_bookings_up_to_limit(client):
    admin = create_tenant(client, "capacity-hotel")
    resource = client.post(
        "/api/v1/resources",
        headers={"X-Admin-Token": admin},
        json={"id": "meeting-room", "name": "Meeting room", "category": "room", "capacity": 4},
    )
    assert resource.status_code == 201
    headers = {"X-Tenant-ID": "capacity-hotel"}
    first_payload = reservation_payload("meeting-room")
    first_payload["quantity"] = 3
    first = client.post("/api/v1/reservations", headers=headers, json=first_payload)
    assert first.status_code == 201
    second_payload = reservation_payload("meeting-room")
    second_payload["quantity"] = 2
    second = client.post("/api/v1/reservations", headers=headers, json=second_payload)
    assert second.status_code == 409


def test_public_availability_reports_remaining_capacity(client):
    admin = create_tenant(client, "availability-hotel")
    client.post(
        "/api/v1/resources",
        headers={"X-Admin-Token": admin},
        json={"id": "court", "name": "Tennis court", "category": "sport", "capacity": 3},
    )
    headers = {"X-Tenant-ID": "availability-hotel"}
    payload = reservation_payload("court")
    payload["quantity"] = 2
    created = client.post("/api/v1/reservations", headers=headers, json=payload)
    assert created.status_code == 201
    available = client.get(
        "/api/v1/public/availability",
        headers=headers,
        params={
            "resource_id": "court",
            "start_at": payload["start_at"],
            "end_at": payload["end_at"],
            "quantity": 2,
        },
    )
    assert available.status_code == 200
    assert available.json()["remaining"] == 1
    assert available.json()["available"] is False


def test_resource_can_be_updated_and_deactivated(client):
    admin = create_tenant(client, "resource-admin")
    headers = {"X-Admin-Token": admin}
    updated = client.put(
        "/api/v1/resources/room-1",
        headers=headers,
        json={"name": "Suite principal", "capacity": 5},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Suite principal"
    assert updated.json()["capacity"] == 5
    deactivated = client.put(
        "/api/v1/resources/room-1",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    public = client.get("/api/v1/public/resources", headers={"X-Tenant-ID": "resource-admin"})
    assert all(item["id"] != "room-1" for item in public.json())


def test_resource_capacity_cannot_be_reduced_below_confirmed_bookings(client):
    admin = create_tenant(client, "capacity-protection")
    headers = {"X-Tenant-ID": "capacity-protection"}
    admin_headers = {"X-Admin-Token": admin}
    client.post(
        "/api/v1/resources",
        headers=admin_headers,
        json={"id": "bus", "name": "Bus", "category": "vehicle", "capacity": 4},
    )
    booking = reservation_payload("bus")
    booking["quantity"] = 3
    assert client.post("/api/v1/reservations", headers=headers, json=booking).status_code == 201
    response = client.put("/api/v1/resources/bus", headers=admin_headers, json={"capacity": 2})
    assert response.status_code == 409
