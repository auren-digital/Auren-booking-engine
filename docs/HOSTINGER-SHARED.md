# Hostinger Shared deployment — AUREN Booking Engine

This version runs on Hostinger Shared with PHP 8.1+ and MySQL/MariaDB. It does not need Python, Uvicorn, Node.js, Docker or an external API host.

## Files to upload

Upload the **contents** of repository folder `web/` directly into `public_html/`, so `index.html` and `admin.html` are at the document root. Also upload:
- root `.htaccess` to `public_html/.htaccess`
- `api/index.php` to `public_html/api/index.php`
- `api/.htaccess` to `public_html/api/.htaccess`
- `api/config.example.php` to `public_html/api/config.example.php`

Do not upload Python files, tests, Git metadata, Docker files, local databases or development secrets.

## 1. Create the database

In hPanel open **Databases → Management** and create a MySQL database and database user. Assign the user to the database with the required privileges. Record the exact database name, username, password and host shown by Hostinger. The PHP connection host is commonly `localhost`; use the value displayed in hPanel if it differs.

## 2. Configure the API

On the server, copy `public_html/api/config.example.php` to `public_html/api/config.php`. Edit only the server copy:
- database name
- database username
- database password
- a unique random `platform_token`
- a different unique random `default_admin_token`

Use long, unrelated secrets (at least 40 random characters each). Never commit `config.php`, expose it in screenshots or send secrets in chat. The `api/.htaccess` file denies HTTP access to `config.php`.

The API creates its MySQL tables and the default workspace on first access. Workspace identifier: `default`. Admin token: the value configured as `default_admin_token`.

## 3. PHP and SSL

In hPanel select PHP 8.1 or newer and confirm PDO MySQL and mbstring are enabled. Apache mod_rewrite must be available for the root `.htaccess` routes. Enable SSL and force HTTPS before using the portals.

## 4. URLs

- Customer portal: `https://YOUR-DOMAIN/`
- Admin panel: `https://YOUR-DOMAIN/admin.html`
- Health check: `https://YOUR-DOMAIN/health`
- API metadata: `https://YOUR-DOMAIN/api/v1`

Both portals call the API on the same domain. The customer page stores the workspace slug in browser local storage. The admin panel asks for workspace slug and its admin token; the token is kept in session storage.

## 5. Provision another business

Send `POST /api/v1/platform/tenants` with JSON `{"name":"Hotel Demo","slug":"hotel-demo"}` and header `X-Platform-Token: YOUR_PLATFORM_TOKEN`. Do this from a trusted server-side tool or administrator terminal; never put the platform token in public JavaScript. The response contains a one-time tenant admin token. Store it securely, then configure the customer portal with the tenant slug and the admin panel with that slug and token.

## 6. Smoke tests

1. Open `/health`; expect HTTP 200 and `"database":"connected"`.
2. Open the customer portal; the resource selector should load the default catalogue.
3. Create a test reservation with a future time range.
4. Save the folio and confirm lookup works with the same email.
5. Open the admin panel, enter workspace `default` and the configured default admin token.
6. Confirm the reservation appears; create a resource, edit its capacity, then cancel the test reservation.
7. Create a second test tenant and confirm its data is isolated from `default`.

## Production safeguards

This conversion preserves the existing booking routes and basic features. Before accepting real customer traffic, add rate limiting, individual user accounts and roles, audit logging, secret rotation, automated off-site database backups and a tested restore procedure. The admin token is currently a shared credential per workspace, not an individual login. Payments, email/SMS notifications, tax rules, operating hours and business timezone policies are not included in this version.
