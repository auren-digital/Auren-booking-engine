# Despliegue HTML estático — AUREN Booking Engine

Publica el contenido de `web/` en el directorio público: `index.html`, `admin.html`, `manifest.webmanifest`, `service-worker.js` e `icon.svg`. El portal cliente incluye **Conectar API** y permite configurar URL HTTPS y tenant. El panel administrativo tiene su propia configuración. No incluyas tokens de plataforma ni secretos en archivos públicos.

## Backend obligatorio
Disponibilidad, reservas, consulta de folios, catálogo y administración dependen de FastAPI:
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Configura `BOOKING_DB_PATH`, `BOOKING_PLATFORM_TOKEN`, `BOOKING_ADMIN_TOKEN` y `BOOKING_ALLOWED_ORIGINS` en el servidor. Usa HTTPS, almacenamiento persistente y respaldos.

## Verificación
Comprueba `GET /health`, carga de recursos, disponibilidad antes de reservar, creación de folio, consulta con correo y acceso administrativo por token del tenant.

La versión actual es base de desarrollo/staging. Antes de producción comercial faltan PostgreSQL, cuentas y roles individuales, rate limiting, auditoría, rotación de secretos, copias externas y pruebas de concurrencia/restauración.
