# AUREN Booking Engine — Roadmap

## v0.1 Foundation — completed
- [x] FastAPI service and health endpoint
- [x] Create, list, and cancel reservations
- [x] Resource/time overlap protection
- [x] Timezone-aware timestamps
- [x] Automated tests and GitHub Actions CI

## v0.4 SaaS foundation — in progress
- [x] Workspace provisioning protected by platform secret
- [x] Tenant-isolated reservation reads, writes, and cancellations
- [x] Per-workspace administrative token hashes
- [x] Tenant resource catalog and active-resource validation
- [x] Customer portal and admin panel connected to tenant context
- [x] Installable PWA shell
- [ ] Individual user accounts, roles, and session management
- [x] Resource edit/deactivate API endpoint
- [x] Public availability search by resource and time range
- [x] Capacity-aware group reservations
- [ ] Resource management UI and operating hours

## v0.5 Booking operations
- [x] Resource capacity and group booking rules
- [ ] Operating hours, blackout dates, lead time, and buffers
- [ ] Customer profiles and reservation history
- [ ] Booking lifecycle, reschedule, and cancellation policies
- [ ] Audit events and exportable reports

## v0.6 Commercial features
- [ ] Service catalog, pricing, taxes, and currencies
- [ ] Subscription plans, quotas, and tenant billing
- [ ] Email/WhatsApp notification adapters
- [ ] Webhooks and external channel integrations
- [ ] Payment adapter after provider and compliance requirements are defined

## v1.0 Production readiness
- [ ] PostgreSQL and managed migrations
- [ ] Rate limiting, abuse protection, and security review
- [ ] Backups, restore drills, monitoring, and alerting
- [ ] Load/concurrency tests and end-to-end browser tests
- [ ] HTTPS deployment and operational runbooks

Do not expose publicly or sell as production-ready before the remaining security, operations, and deployment safeguards are complete.
