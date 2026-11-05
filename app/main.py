"""AUREN Booking Engine — generic resource reservation API."""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, field_validator

DB_PATH = os.getenv("BOOKING_DB_PATH", "bookings.db")
app = FastAPI(
    title="AUREN Booking Engine",
    description="Reusable reservation API for services and bookable resources",
    version="0.1.0",
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
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reservations_resource_range
            ON reservations(resource_id, start_at, end_at, status)
        """)
        db.commit()


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include a timezone offset.")
    return value.astimezone(timezone.utc).isoformat()


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
    created_at = datetime.now(timezone.utc)
    with closing(connect()) as db:
        try:
            # Serialize local SQLite writers to reduce overlapping-booking races.
            db.execute("BEGIN IMMEDIATE")
            conflict = db.execute(
                """
                SELECT id FROM reservations
                WHERE resource_id = ?
                  AND status = 'confirmed'
                  AND start_at < ?
                  AND end_at > ?
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
                (id, resource_id, customer_name, customer_email, start_at, end_at,
                 status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'confirmed', ?, ?)
                """,
                (
                    reservation_id,
                    payload.resource_id,
                    payload.customer_name,
                    payload.customer_email,
                    start_at,
                    end_at,
                    payload.notes,
                    created_at.isoformat(),
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
    resource_id: str | None = None,
    reservation_status: Literal["confirmed", "cancelled", "completed"] | None = None,
) -> list[Reservation]:
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


@app.post("/api/v1/reservations/{reservation_id}/cancel", response_model=Reservation)
def cancel_reservation(reservation_id: str) -> Reservation:
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
        db.execute(
            "UPDATE reservations SET status = 'cancelled' WHERE id = ?",
            (reservation_id,),
        )
        db.commit()
        updated = db.execute(
            "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
        ).fetchone()
    return Reservation(**dict(updated))
