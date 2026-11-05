"""AUREN Booking Engine — shared reservation API."""
from __future__ import annotations

import os
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
ADMIN_TOKEN = os.getenv("BOOKING_ADMIN_TOKEN", "")
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
    description="Shared reservation API for customer and administrative portals",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def initialize_database() -> None:
    with closing(connect()) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id TEXT PRIMARY KEY,
                reference_code TEXT,
                resource_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('confirmed', 'cancelled', 'completed')),
                notes TEXT,
                created_at TEXT NOT NULL
            )
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(reservations)")}
        if "reference_code" not in columns:
            db.execute("ALTER TABLE reservations ADD COLUMN reference_code TEXT")
        legacy_rows = db.execute(
            "SELECT id FROM reservations WHERE reference_code IS NULL OR reference_code = ''"
        ).fetchall()
        for legacy in legacy_rows:
            db.execute(
                "UPDATE reservations SET reference_code = ? WHERE id = ?",
                (f"AUR-{uuid4().hex[:8].upper()}", legacy["id"]),
            )
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reservations_resource_range
            ON reservations(resource_id, start_at, end_at, status)
        """)
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reservations_reference
            ON reservations(reference_code) WHERE reference_code IS NOT NULL
        """)
        db.commit()


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include a timezone offset.")
    return value.astimezone(timezone.utc).isoformat()


def require_admin(x_admin_token: str | None) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Administrative access is not configured. Set BOOKING_ADMIN_TOKEN on the server.",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing administrative token.")


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


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "auren-booking-engine",
        "version": app.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post(
    "/api/v1/reservations",
    response_model=Reservation,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(payload: ReservationCreate) -> Reservation:
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
            conflict = db.execute(
                """
                SELECT id FROM reservations
                WHERE resource_id = ? AND status = 'confirmed'
                  AND start_at < ? AND end_at > ?
                LIMIT 1
                """,
                (payload.resource_id, end_at, start_at),
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
                (id, reference_code, resource_id, customer_name, customer_email,
                 start_at, end_at, status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?)
                """,
                (
                    reservation_id, reference_code, payload.resource_id,
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
    require_admin(x_admin_token)
    query = "SELECT * FROM reservations WHERE 1=1"
    params: list[str] = []
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
) -> Reservation:
    with closing(connect()) as db:
        row = db.execute(
            """
            SELECT * FROM reservations
            WHERE reference_code = ? AND lower(customer_email) = lower(?)
            """,
            (reference_code.upper(), email.strip()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Reservation not found. Check the folio and email.")
    return Reservation(**dict(row))


@app.post("/api/v1/reservations/{reservation_id}/cancel", response_model=Reservation)
def cancel_reservation(
    reservation_id: str,
    x_admin_token: str | None = Header(default=None),
) -> Reservation:
    require_admin(x_admin_token)
    with closing(connect()) as db:
        row = db.execute(
            "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Reservation not found.")
        if row["status"] == "cancelled":
            return Reservation(**dict(row))
        if row["status"] == "completed":
            raise HTTPException(status_code=409, detail="Completed reservations cannot be cancelled.")
        db.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (reservation_id,))
        db.commit()
        updated = db.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
    return Reservation(**dict(updated))
