# AUREN Booking Engine

Motor de reservas multiempresa con portal de clientes, panel administrativo y API.

## Despliegue en Hostinger Shared

Esta rama incluye una implementación compatible con **PHP 8.1+ y MySQL** para alojar los portales y la API en el mismo hosting compartido, sin Python, Docker ni servidor externo.

Sigue la guía paso a paso: [docs/HOSTINGER-SHARED.md](docs/HOSTINGER-SHARED.md).

- Portal de clientes: `web/index.html`
- Panel administrativo: `web/admin.html`
- API PHP: `api/index.php`
- Configuración privada de ejemplo: `api/config.example.php` (copiar en el servidor como `config.php`; nunca subir secretos a GitHub)
- Reglas Apache: `.htaccess` y `api/.htaccess`

La API crea las tablas MySQL y el espacio de trabajo `default` al primer acceso. El administrador usa el token configurado como `default_admin_token`. La creación de empresas requiere el token privado `platform_token`.

## Funcionalidades incluidas

- Multi-tenant: separación de recursos y reservas por empresa.
- Alta de espacios de trabajo protegida por token de plataforma.
- Catálogo público y administración de recursos.
- Capacidad por recurso y validación de disponibilidad.
- Creación de reservas con folio.
- Consulta pública mediante folio + correo.
- Listado, filtros, edición de recursos y cancelación desde el panel.
- PWA con manifest y service worker.

## Compatibilidad de API

Se mantienen los endpoints y los nombres de campos de la versión FastAPI. Consulta [docs/API-COMPATIBILITY.md](docs/API-COMPATIBILITY.md).

## Desarrollo Python original

El backend FastAPI y sus pruebas siguen en el repositorio como referencia de desarrollo; no se ejecutan en Hostinger Shared. Para el despliegue Shared, publica únicamente los archivos indicados en la guía PHP/MySQL.

## Seguridad y estado

La rama de despliegue no contiene credenciales reales. Configura secretos aleatorios y diferentes en el archivo privado del servidor, activa HTTPS y realiza pruebas antes de utilizar reservas reales. La autenticación administrativa actual es un token compartido por espacio de trabajo; todavía no equivale a cuentas individuales con roles. Antes de comercializar ampliamente, añade rate limiting, auditoría, backups externos, rotación de secretos y recuperación de acceso.
