# PHP/MySQL API compatibility

The Hostinger Shared implementation replaces the FastAPI/SQLite runtime with a PHP 8.1+ front controller and MySQL. Portal-facing routes and JSON field names remain compatible.

| Method | Route | Access |
|---|---|---|
| GET | `/health` | Public |
| GET | `/api/v1` | Public |
| POST | `/api/v1/platform/tenants` | `X-Platform-Token` |
| GET | `/api/v1/public/resources` | `X-Tenant-ID` |
| GET | `/api/v1/public/availability` | `X-Tenant-ID` |
| GET | `/api/v1/resources` | `X-Admin-Token` |
| POST | `/api/v1/resources` | `X-Admin-Token` |
| PUT | `/api/v1/resources/{resource_id}` | `X-Admin-Token` |
| POST | `/api/v1/reservations` | `X-Tenant-ID` |
| GET | `/api/v1/reservations` | `X-Admin-Token` |
| GET | `/api/v1/public/reservations/{reference_code}?email=...` | `X-Tenant-ID` + email |
| POST | `/api/v1/reservations/{id}/cancel` | `X-Admin-Token` |

Responses retain the existing reservation fields: `id`, `reference_code`, `resource_id`, `customer_name`, `customer_email`, `quantity`, `start_at`, `end_at`, `status`, `notes` and `created_at`. Datetimes are normalized to UTC ISO 8601. JSON errors use the `detail` field.

The PHP API uses PDO prepared statements, tenant-scoped queries, SHA-256 token hashes, MySQL transactions and row locks for capacity reservations. The schema is initialized once when first accessed. Existing SQLite records are not automatically migrated; export/import must be handled separately if they contain data that needs to be retained.
