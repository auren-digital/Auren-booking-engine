# AUREN Booking Engine

Motor genérico de reservas con dos portales separados y una API compartida.

## Portales

- App instalable (PWA): el portal web puede instalarse desde el navegador compatible en Android y escritorio. Incluye caché de la interfaz; las operaciones de reservas requieren conexión con la API.

- Cliente: `web/index.html` — crea reservas y consulta una reserva propia mediante folio + correo.
- Administración: `web/admin.html` — consulta todas las reservas, filtra, crea y cancela. Requiere token administrativo.
- Ambos portales utilizan la misma API y la misma base SQLite del servidor.

## Ejecutar localmente

Requiere Python 3.12 o compatible.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Configura un token administrativo antes de iniciar el backend.

Windows PowerShell:
```powershell
$env:BOOKING_ADMIN_TOKEN="reemplaza-por-una-clave-larga-y-aleatoria"
uvicorn app.main:app --reload
```

macOS/Linux:
```bash
export BOOKING_ADMIN_TOKEN="reemplaza-por-una-clave-larga-y-aleatoria"
uvicorn app.main:app --reload
```

La API estará en http://127.0.0.1:8000, su documentación en http://127.0.0.1:8000/docs y el índice de API en http://127.0.0.1:8000/api/v1.

En el portal cliente puedes usar **Conectar API** para guardar la URL del backend. La primera vez que publiques el backend, configura `BOOKING_ALLOWED_ORIGINS` con el dominio exacto donde publiques la web.

En otra terminal, desde la raíz del repositorio:
```bash
python -m http.server 5500
```

Abre:
- Cliente: http://localhost:5500/web/
- Administración: http://localhost:5500/web/admin.html

En el panel administrativo pulsa **Conectar admin** e introduce la URL de la API y el mismo token definido en el servidor. El token se conserva solo en la sesión de esa pestaña/navegador.

## Flujo

1. El cliente envía la reserva a `POST /api/v1/reservations`.
2. El backend valida fechas, genera folio y bloquea solapamientos mediante una transacción SQLite.
3. El cliente consulta su reserva en `GET /api/v1/public/reservations/{folio}?email=...`; se exige coincidencia del correo.
4. Administración consulta el listado y cancela reservas mediante endpoints protegidos por `X-Admin-Token`.

## Configuración

- `BOOKING_DB_PATH`: ruta del archivo SQLite (por defecto `bookings.db`).
- `BOOKING_ADMIN_TOKEN`: clave obligatoria para las operaciones administrativas.
- `BOOKING_ALLOWED_ORIGINS`: orígenes CORS separados por coma. Por defecto permite localhost y 127.0.0.1 en puerto 5500.

## App instalable

La carpeta `web/` incluye `manifest.webmanifest`, `service-worker.js` e `icon.svg`. Publica la carpeta completa bajo HTTPS para habilitar la instalación. La caché guarda únicamente la interfaz estática; no almacena ni simula respuestas de la API. Crear, consultar y administrar reservas requiere conexión activa.

## Límites actuales

Esta es una primera integración funcional para desarrollo local. Aún no incluye usuarios/roles individuales, aislamiento multiempresa, pagos, notificaciones, recuperación de acceso, rate limiting, auditoría avanzada, PostgreSQL ni despliegue público. No uses una clave de demostración en producción; despliega con HTTPS, secretos seguros y una estrategia de autenticación robusta.
