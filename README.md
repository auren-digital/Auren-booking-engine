# AUREN Booking Engine

Motor de reservas multiempresa con portal de clientes, panel de administración y API compartida.

## Componentes
- Cliente: `web/index.html` — crea reservas y consulta una reserva mediante folio + correo.
- Administración: `web/admin.html` — consulta, filtra, crea y cancela reservas.
- API: FastAPI con aislamiento por espacio de trabajo (tenant).
- PWA: manifest, service worker e icono; instalación mediante HTTPS.
- Documentación OpenAPI: `/docs`.

## Ejecutar con Docker\n\n1. Copia `.env.example` a `.env`.\n2. Sustituye ambos secretos por valores aleatorios distintos y largos.\n3. Ejecuta `docker compose up --build -d`.\n4. Abre `http://localhost:8000/web/` para el portal de clientes y `http://localhost:8000/web/admin.html` para administración.\n\nDocker Compose conserva SQLite en un volumen persistente `booking-data`. En producción, utiliza almacenamiento persistente real y respaldos externos; no despliegues el contenedor con un filesystem efímero. El mismo servidor entrega la API y ambos portales, por lo que normalmente no necesitas CORS entre ellos.\n\n## Despliegue en servidor
Consulta [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) para preparar una instancia de staging en un VPS con Docker, DNS y HTTPS. La guía deja claro qué falta antes de producción comercial.

## Desarrollo local
Requiere Python 3.12 o compatible.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Configura secretos distintos para administración de plataforma y operación del backend.

Windows PowerShell:
```powershell
$env:BOOKING_PLATFORM_TOKEN="un-secreto-largo-para-provisionar-empresas"
$env:BOOKING_ADMIN_TOKEN="un-secreto-largo-para-el-espacio-default"
uvicorn app.main:app --reload
```

macOS/Linux:
```bash
export BOOKING_PLATFORM_TOKEN="un-secreto-largo-para-provisionar-empresas"
export BOOKING_ADMIN_TOKEN="un-secreto-largo-para-el-espacio-default"
uvicorn app.main:app --reload
```

En otra terminal ejecuta el frontend:
```bash
python -m http.server 5500
```
- Cliente: http://localhost:5500/web/
- Administración: http://localhost:5500/web/admin.html
- API: http://127.0.0.1:8000\n- Portal de clientes servido por API: http://127.0.0.1:8000/web/\n- Panel administrativo servido por API: http://127.0.0.1:8000/web/admin.html
- Swagger: http://127.0.0.1:8000/docs

## Crear un espacio de trabajo empresarial

La creación de empresas está protegida por `BOOKING_PLATFORM_TOKEN`. Usa el endpoint `POST /api/v1/platform/tenants` con `X-Platform-Token`:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/platform/tenants \\
  -H "Content-Type: application/json" \\
  -H "X-Platform-Token: $BOOKING_PLATFORM_TOKEN" \\
  -d '{"name":"Hotel Demo","slug":"hotel-demo"}'
```

La respuesta entrega el identificador y el token administrativo una sola vez. Guarda el token en un gestor de secretos; la API almacena únicamente su hash. No lo compartas con clientes. El slug es el `X-Tenant-ID` que se configura en los portales.

## Endpoints principales

| Método | Ruta | Acceso |
|---|---|---|
| GET | `/health` | Público; comprueba API y DB |
| GET | `/api/v1` | Público; metadatos |\n| GET | `/api/v1/public/resources` | `X-Tenant-ID` |
| GET | `/api/v1/public/availability` | `X-Tenant-ID` + recurso + rango horario |\n| GET | `/api/v1/resources` | Token admin del tenant |\n| POST | `/api/v1/resources` | Token admin del tenant |
| PUT | `/api/v1/resources/{id}` | Token admin del tenant |
| POST | `/api/v1/platform/tenants` | Token de plataforma |
| POST | `/api/v1/reservations` | `X-Tenant-ID` (admite `quantity`) |
| GET | `/api/v1/public/reservations/{folio}?email=...` | `X-Tenant-ID` + correo |
| GET | `/api/v1/reservations` | Token admin del tenant |
| POST | `/api/v1/reservations/{id}/cancel` | Token admin del tenant |

Los listados, cancelaciones y conflictos de disponibilidad quedan limitados al tenant autenticado. El token de plataforma nunca se utiliza en los portales.

## Variables de entorno
- `BOOKING_DB_PATH`: ruta de SQLite (por defecto `bookings.db`).
- `BOOKING_PLATFORM_TOKEN`: secreto para crear espacios de trabajo.
- `BOOKING_ADMIN_TOKEN`: compatibilidad del espacio `default`; no sustituye la creación de tokens independientes.
- `BOOKING_ALLOWED_ORIGINS`: orígenes CORS separados por coma.

## Seguridad y despliegue
Usa HTTPS, secretos aleatorios fuertes, base de datos persistente y respaldos. Mantén el token de plataforma solo en el servidor. La autenticación administrativa actual utiliza un token por empresa; antes de comercializar se debe añadir inicio de sesión individual, roles, recuperación de acceso, rate limiting, auditoría y rotación de credenciales. SQLite sirve para pruebas y despliegues pequeños; para un SaaS con múltiples instancias, migra a PostgreSQL.

La PWA almacena solo recursos estáticos; las operaciones de reservas requieren conexión. Publica la carpeta completa `web/` bajo HTTPS para instalarla.

## Estado
Base multi-tenant, disponibilidad pública, capacidad por recurso y gestión de recursos implementadas. No se considera lista para producción hasta completar pruebas de extremo a extremo, despliegue HTTPS, respaldos, controles de abuso, observabilidad y autenticación individual.
