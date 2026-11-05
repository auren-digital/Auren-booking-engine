# AUREN Booking Engine — Domain Model

## Purpose
A reusable booking core for multiple businesses. Industry-specific policies should be layered on top of the generic reservation model.

## Core concepts
- **Tenant / workspace:** isolated business account identified by a unique slug.
- **Resource:** reservable capacity belonging to one tenant, such as a vehicle, room, appointment slot, professional, or equipment.
- **Reservation:** customer, tenant, resource, start/end timestamps, status, and optional notes.
- **Platform provisioning:** privileged endpoint creates tenant workspaces and returns a one-time administrative token.
- **Availability policy (planned):** operating windows, blackout dates, lead time, buffers, capacity, and timezone rules.
- **Pricing policy (planned):** service catalog, rate rules, fees, taxes, and currency.

## API v0.4
- `GET /health` — API and database health.
- `GET /api/v1` — API metadata.
- `POST /api/v1/platform/tenants` — create tenant; platform token required.
- `GET /api/v1/public/resources` — active resources for the tenant.
- `POST /api/v1/reservations` — create a reservation; tenant header required.
- `GET /api/v1/public/reservations/{folio}?email=...` — customer lookup, tenant + email scoped.
- `GET /api/v1/resources` — tenant resource catalog; tenant admin token required.
- `POST /api/v1/resources` — create tenant resource; tenant admin token required.
- `GET /api/v1/reservations` — list tenant reservations; tenant admin token required.
- `POST /api/v1/reservations/{id}/cancel` — cancel within authenticated tenant.

All supplied timestamps must include timezone information and are normalized to UTC. Reservation overlap checks are scoped by tenant and resource.

## Security boundaries
- Platform token is only for tenant provisioning and must remain server-side.
- Each tenant has an independently generated administrative token; only its hash is persisted.
- Public endpoints require a tenant identifier and only return that tenant's resources/reservations.
- Admin list/cancel/resource operations resolve the tenant from the admin token.
- The current admin token is a shared tenant credential, not individual user authentication.

## Current limitations
SQLite is suitable for local development and small single-instance testing, not a horizontally scaled SaaS. Before commercial production, migrate to PostgreSQL, add individual users/roles, rate limiting, audit logging, secret rotation, monitoring, backups, and end-to-end security testing. Payments and notifications remain out of scope until providers and policies are selected.
