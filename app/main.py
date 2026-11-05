"""AUREN Booking Engine — multi-tenant reservation API."""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

DB_PATH = os.getenv("BOOKING_DB_PATH", "bookings.db")
LEGACY_ADMIN_TOKEN = os.getenv("BOOKING_ADMIN_TOKEN", "")
PLATFORM_TOKEN = os.getenv("BOOKING_PLATFORM_TOKEN", "")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "BOOKING_ALLOWED_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")
    if origin.strip()
]

app = FastAPI(
    title="AUREN Booking Engine",
    description="Multi-tenant reservation API for customer and business portals",
    version="0.5.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Tenant-ID", "X-Admin-Token", "X-Platform-Token"],
)


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def initialize_database() -> None:
    with closing(connect()) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                admin_token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                capacity INTEGER NOT NULL DEFAULT 1 CHECK(capacity > 0),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id TEXT PRIMARY KEY,
                reference_code TEXT,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                resource_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('confirmed', 'cancelled', 'completed')),
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(reservations)")}
        if "reference_code" not in columns:
            db.execute("ALTER TABLE reservations ADD COLUMN reference_code TEXT")
        if "tenant_id" not in columns:
            db.execute("ALTER TABLE reservations ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
        legacy_rows = db.execute(
            "SELECT id FROM reservations WHERE reference_code IS NULL OR reference_code = ''"
        ).fetchall()
        for legacy in legacy_rows:
            db.execute(
                "UPDATE reservations SET reference_code = ? WHERE id = ?",
                (f"AUR-{uuid4().hex[:8].upper()}", legacy["id"]),
            )
        default = db.execute("SELECT id FROM tenants WHERE id = 'default'").fetchone()
        if default is None:
            if not LEGACY_ADMIN_TOKEN:
                # A disabled default workspace prevents accidentally exposing
                # legacy data until an administrator explicitly provisions it.
                token_hash = hash_secret(secrets.token_urlsafe(32))
            else:
                token_hash = hash_secret(LEGACY_ADMIN_TOKEN)
            db.execute(
                "INSERT INTO tenants (id, slug, name, admin_token_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                ("default", "default", "Default Workspace", token_hash, datetime.now(timezone.utc).isoformat()),
            )
        for tenant_row in db.execute("SELECT id FROM tenants").fetchall():
            for resource_id, resource_name, category in (
                ("vehicle-1", "Vehículo 1", "vehicle"),
                ("room-1", "Habitación 1", "room"),
                ("room-2", "Habitación 2", "room"),
                ("service-1", "Servicio 1", "service"),
            ):
                db.execute(
                    """INSERT OR IGNORE INTO resources
                    (id, tenant_id, name, category, capacity, is_active, created_at)
                    VALUES (?, ?, ?, ?, 1, 1, ?)""",
                    (resource_id, tenant_row["id"], resource_name, category, datetime.now(timezone.utc).isoformat()),
                )
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reservations_tenant_resource_range
            ON reservations(tenant_id, resource_id, start_at, end_at, status)
        """)
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reservations_reference
            ON reservations(tenant_id, reference_code) WHERE reference_code IS NOT NULL
        """)
        db.commit()


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include a timezone offset.")
    return value.astimezone(timezone.utc).isoformat()


def require_tenant(tenant_id: str | None) -> str:
    if not tenant_id or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", tenant_id):
        raise HTTPException(status_code=400, detail="A valid X-Tenant-ID header is required.")
    with closing(connect()) as db:
        tenant = db.execute("SELECT id FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return tenant["id"]


def require_admin(x_admin_token: str | None) -> str:
    if not x_admin_token:
        raise HTTPException(status_code=401, detail="Missing administrative token.")
    token_hash = hash_secret(x_admin_token)
    with closing(connect()) as db:
        tenant = db.execute(
            "SELECT id FROM tenants WHERE admin_token_hash = ?", (token_hash,)
        ).fetchone()
    # Keep legacy deployments working only for the explicitly configured default tenant.
    if tenant is None and LEGACY_ADMIN_TOKEN and secrets.compare_digest(x_admin_token, LEGACY_ADMIN_TOKEN):
        return "default"
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid administrative token.")
    return tenant["id"]


def require_platform(x_platform_token: str | None) -> None:
    if not PLATFORM_TOKEN:
        raise HTTPException(status_code=503, detail="Platform provisioning is disabled. Set BOOKING_PLATFORM_TOKEN.")
    if not x_platform_token or not secrets.compare_digest(x_platform_token, PLATFORM_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid platform token.")


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]+$")
    
    @field_validator("name", "slug")
    @classmethod
    def trim_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class TenantCreated(BaseModel):
    id: str
    name: str
    admin_token: str
    created_at: datetime


class ResourceCreate(BaseModel):
    id: str = Field(min_length=2, max_length=120, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(default="general", min_length=2, max_length=40)
    capacity: int = Field(default=1, ge=1, le=10000)

    @field_validator("id", "name", "category")
    @classmethod
    def trim_resource_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class Resource(BaseModel):
    id: str
    name: str
    category: str
    capacity: int
    is_active: bool


class ReservationCreate(BaseModel):
    resource_id: str = Field(min_length=1, max_length=120)
    customer_name: str = Field(min_length=1, max_length=200)
    customer_email: str | None = Field(default=None, max_length=254)
    start_at: datetime
    end_at: datetime
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("start_at", "end_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        utc_iso(value)
        return value

    @field_validator("customer_name", "resource_id")
    @classmethod
    def trim_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class Reservation(BaseModel):
    id: str
    reference_code: str
    resource_id: str
    customer_name: str
    customer_email: str | None
    start_at: datetime
    end_at: datetime
    status: Literal["confirmed", "cancelled", "completed"]
    notes: str | None
    created_at: datetime


@app.get("/api/v1")
def api_info() -> dict:
    return {
        "service": "AUREN Booking Engine",
        "version": app.version,
        "status": "operational",
        "multi_tenant": True,
        "docs": "/docs",
        "health": "/health",
        "customer_portal": "/web/index.html",
        "admin_portal": "/web/admin.html",
    }


@app.get("/health")
def health() -> dict:
    with closing(connect()) as db:
        db.execute("SELECT 1").fetchone()
    return {
        "status": "ok",
        "service": "auren-booking-engine",
        "version": app.version,
        "database": "connected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/platform/tenants", response_model=TenantCreated, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    x_platform_token: str | None = Header(default=None),
) -> TenantCreated:
    require_platform(x_platform_token)
    tenant_id = payload.slug
    admin_token = secrets.token_urlsafe(36)
    created_at = datetime.now(timezone.utc)
    with closing(connect()) as db:
        try:
            db.execute(
                "INSERT INTO tenants (id, slug, name, admin_token_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (tenant_id, payload.slug, payload.name.strip(), hash_secret(admin_token), created_at.isoformat()),
            )
            for resource_id, resource_name, category in (
                ("vehicle-1", "Vehículo 1", "vehicle"),
                ("room-1", "Habitación 1", "room"),
                ("room-2", "Habitación 2", "room"),
                ("service-1", "Servicio 1", "service"),
            ):
                db.execute(
                    """INSERT INTO resources
                    (id, tenant_id, name, category, capacity, is_active, created_at)
                    VALUES (?, ?, ?, ?, 1, 1, ?)""",
                    (resource_id, tenant_id, resource_name, category, created_at.isoformat()),
                )
            db.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="A workspace with this slug already exists.")
    # The clear-text admin token is returned once and is never stored.
    return TenantCreated(id=tenant_id, name=payload.name.strip(), admin_token=admin_token, created_at=created_at)


@app.get("/api/v1/public/resources", response_model=list[Resource])
def list_public_resources(x_tenant_id: str | None = Header(default=None)) -> list[Resource]:
    tenant_id = require_tenant(x_tenant_id)
    with closing(connect()) as db:
        rows = db.execute(
            "SELECT id, name, category, capacity, is_active FROM resources WHERE tenant_id = ? AND is_active = 1 ORDER BY name",
            (tenant_id,),
        ).fetchall()
    return [Resource(**{**dict(row), "is_active": bool(row["is_active"])}) for row in rows]


@app.get("/api/v1/resources", response_model=list[Resource])
def list_resources(x_admin_token: str | None = Header(default=None)) -> list[Resource]:
    tenant_id = require_admin(x_admin_token)
    with closing(connect()) as db:
        rows = db.execute(
            "SELECT id, name, category, capacity, is_active FROM resources WHERE tenant_id = ? ORDER BY name",
            (tenant_id,),
        ).fetchall()
    return [Resource(**{**dict(row), "is_active": bool(row["is_active"])}) for row in rows]


@app.post("/api/v1/resources", response_model=Resource, status_code=status.HTTP_201_CREATED)
def create_resource(
    payload: ResourceCreate,
    x_admin_token: str | None = Header(default=None),
) -> Resource:
    tenant_id = require_admin(x_admin_token)
    with closing(connect()) as db:
        try:
            db.execute(
                """INSERT INTO resources
                (id, tenant_id, name, category, capacity, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (payload.id, tenant_id, payload.name.strip(), payload.category.strip(), payload.capacity, datetime.now(timezone.utc).isoformat()),
            )
            db.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="A resource with this ID already exists in the workspace.")
    return Resource(id=payload.id, name=payload.name.strip(), category=payload.category.strip(), capacity=payload.capacity, is_active=True)


@app.post(
    "/api/v1/reservations",
    response_model=Reservation,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(
    payload: ReservationCreate,
    x_tenant_id: str | None = Header(default=None),
) -> Reservation:
    tenant_id = require_tenant(x_tenant_id)
    start_at = utc_iso(payload.start_at)
    end_at = utc_iso(payload.end_at)
    if end_at <= start_at:
        raise HTTPException(status_code=422, detail="end_at must be later than start_at")

    reservation_id = str(uuid4())
    reference_code = f"AUR-{uuid4().hex[:8].upper()}"
    created_at = datetime.now(timezone.utc)
    with closing(connect()) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            resource = db.execute(
                "SELECT id FROM resources WHERE tenant_id = ? AND id = ? AND is_active = 1",
                (tenant_id, payload.resource_id),
            ).fetchone()
            if resource is None:
                db.rollback()
                raise HTTPException(status_code=422, detail="Resource not found or inactive for this workspace.")
            conflict = db.execute(
                """
                SELECT id FROM reservations
                WHERE tenant_id = ? AND resource_id = ? AND status = 'confirmed'
                  AND start_at < ? AND end_at > ?
                LIMIT 1
                """,
                (tenant_id, payload.resource_id, end_at, start_at),
            ).fetchone()
            if conflict:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="The resource is already reserved during that time range.",
                )
            db.execute(
                """
                INSERT INTO reservations
                (id, reference_code, tenant_id, resource_id, customer_name, customer_email,
                 start_at, end_at, status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?)
                """,
                (
                    reservation_id, reference_code, tenant_id, payload.resource_id,
                    payload.customer_name, payload.customer_email, start_at,
                    end_at, payload.notes, created_at.isoformat(),
                ),
            )
            db.commit()
        except HTTPException:
            raise
        except Exception:
            db.rollback()
            raise

    return Reservation(
        id=reservation_id,
        reference_code=reference_code,
        resource_id=payload.resource_id,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        start_at=start_at,
        end_at=end_at,
        status="confirmed",
        notes=payload.notes,
        created_at=created_at,
    )


@app.get("/api/v1/reservations", response_model=list[Reservation])
def list_reservations(
    x_admin_token: str | None = Header(default=None),
    resource_id: str | None = None,
    reservation_status: Literal["confirmed", "cancelled", "completed"] | None = None,
) -> list[Reservation]:
    tenant_id = require_admin(x_admin_token)
    query = "SELECT * FROM reservations WHERE tenant_id = ?"
    params: list[str] = [tenant_id]
    if resource_id:
        query += " AND resource_id = ?"
        params.append(resource_id)
    if reservation_status:
        query += " AND status = ?"
        params.append(reservation_status)
    query += " ORDER BY start_at"
    with closing(connect()) as db:
        rows = db.execute(query, params).fetchall()
    return [Reservation(**dict(row)) for row in rows]


@app.get("/api/v1/public/reservations/{reference_code}", response_model=Reservation)
def get_public_reservation(
    reference_code: str,
    email: str = Query(min_length=3, max_length=254),
    x_tenant_id: str | None = Header(default=None),
) -> Reservation:
    tenant_id = require_tenant(x_tenant_id)
    with closing(connect()) as db:
        row = db.execute(
            """
            SELECT * FROM reservations
            WHERE tenant_id = ? AND reference_code = ? AND lower(customer_email) = lower(?)
            """,
            (tenant_id, reference_code.upper(), email.strip()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Reservation not found. Check the folio and email.")
    return Reservation(**dict(row))


@app.post("/api/v1/reservations/{reservation_id}/cancel", response_model=Reservation)
def cancel_reservation(
    reservation_id: str,
    x_admin_token: str | None = Header(default=None),
) -> Reservation:
    tenant_id = require_admin(x_admin_token)
    with closing(connect()) as db:
        row = db.execute(
            "SELECT * FROM reservations WHERE id = ? AND tenant_id = ?",
            (reservation_id, tenant_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Reservation not found.")
        if row["status"] == "cancelled":
            return Reservation(**dict(row))
        if row["status"] == "completed":
            raise HTTPException(status_code=409, detail="Completed reservations cannot be cancelled.")
        db.execute(
            "UPDATE reservations SET status = 'cancelled' WHERE id = ? AND tenant_id = ?",
            (reservation_id, tenant_id),
        )
        db.commit()
        updated = db.execute(
            "SELECT * FROM reservations WHERE id = ? AND tenant_id = ?",
            (reservation_id, tenant_id),
        ).fetchone()
    return Reservation(**dict(updated))
