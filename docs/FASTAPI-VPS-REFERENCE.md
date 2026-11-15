# Deploy AUREN Booking Engine

This guide deploys a **staging instance** on a Linux VPS. Do not use the current SQLite deployment for a high-volume or multi-instance commercial production service. PostgreSQL, user accounts/roles, rate limiting, backups, and monitoring are still required before accepting real customer traffic.

## 1. Prepare a VPS

Use an Ubuntu 24.04 LTS VPS with a public IPv4 address. For an initial staging environment, 2 vCPU and 4 GB RAM is a practical starting point. A production sizing decision should follow load tests.

Create DNS records at your domain provider:
- A record: booking -> VPS IPv4 address.
- Optional A record: www.booking -> same IPv4 address.

## 2. Install Docker

Connect over SSH as a sudo-enabled user, install Docker Engine and the Docker Compose plugin using Docker's official Ubuntu instructions, then verify:

```bash
docker --version
docker compose version
```

## 3. Get the application

```bash
git clone https://github.com/auren-digital/Auren-booking-engine.git
cd Auren-booking-engine
cp .env.example .env
```

Edit .env and replace both example secrets with different, cryptographically random values. Never commit .env or share the platform token with tenant administrators.

## 4. Start a staging instance

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f auren-booking
```

The app listens on port 8000. Verify /health, then check the customer portal at /web/, admin portal at /web/admin.html, and API docs at /docs.

## 5. Put HTTPS in front

Use a reverse proxy such as Caddy or Nginx to terminate HTTPS and forward requests to the application. Open only SSH and web ports (80/443) in the VPS firewall. Do not expose the application port publicly once the reverse proxy is configured. Use a valid TLS certificate before enabling PWA installation or sharing the portal.

## 6. Before production

- Migrate SQLite to PostgreSQL and use managed/persistent database storage.
- Add individual accounts, role-based permissions, password recovery, and secure sessions.
- Add rate limiting, audit logs, secret rotation, and security review.
- Configure automated off-server backups and test restoration.
- Add monitoring, error alerts, and load/concurrency tests.
- Configure a deployment pipeline and rollback procedure.

The current Compose volume preserves the SQLite file across container recreation, but a Docker volume on one VPS is not a backup. The current configuration is suitable for development and staging only until the production safeguards above are completed.
