# AUREN Booking Engine — Domain Model

## Purpose
A reusable booking core. Industry-specific policies should be layered on top of the generic reservation model.

## Core concepts
- **Resource:** reservable capacity such as a vehicle, room, appointment slot, or piece of equipment.
- **Reservation:** customer, resource, start/end timestamps, status, and optional notes.
- **Availability policy (planned):** operating windows, blackout dates, lead time, buffers, and capacity.
- **Pricing policy (planned):** service catalog, rate rules, fees, and currency.

## API v0.1
- `GET /health`
- `POST /api/v1/reservations`
- `GET /api/v1/reservations?resource_id=...`
- `POST /api/v1/reservations/{id}/cancel`

All supplied timestamps must include timezone information and are normalized to UTC.

## Current limitations
SQLite is for local development. Before production, migrate to PostgreSQL with transaction-safe overlap constraints, authentication, tenant isolation, audit logging, and backups. Payments and customer notifications are intentionally out of scope for this foundation.
