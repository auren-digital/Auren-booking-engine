# AUREN Booking Engine — Roadmap

## v0.1 Foundation
- [x] FastAPI service and health endpoint
- [x] Create, list, and cancel reservations
- [x] Resource/time overlap protection for local SQLite
- [x] Timezone-aware timestamps
- [ ] Automated tests and CI

## v0.2 Availability
- [ ] Resource and capacity management
- [ ] Operating hours and blackout dates
- [ ] Availability search endpoint
- [ ] Lead-time, buffer, and timezone policies

## v0.3 Business rules
- [ ] Service catalog and configurable pricing
- [ ] Booking lifecycle and cancellation policies
- [ ] Customer and operator roles

## v0.4 Integrations
- [ ] Webhooks and notification adapters
- [ ] Payment adapter after requirements are defined
- [ ] External channel/API integration

## v1.0 Production readiness
- [ ] PostgreSQL and migrations
- [ ] Authentication, tenant isolation, and audit trail
- [ ] Concurrency/load tests
- [ ] Monitoring, backups, and security review

Do not expose publicly before production safeguards are implemented.
