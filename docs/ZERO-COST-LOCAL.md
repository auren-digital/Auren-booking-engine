# Ejecutar AUREN Booking Engine gratis en Windows

No necesitas VPS, dominio, Docker ni tarjeta bancaria para desarrollar y probar el motor en tu propia computadora.

## Requisitos
- Windows 10/11.
- Python 3.12 (si no lo tienes, instálalo desde https://www.python.org/downloads/windows/ y marca "Add Python to PATH").
- Conexión a internet solo la primera vez para descargar dependencias.

## Iniciar
1. Descarga el repositorio desde GitHub: https://github.com/auren-digital/Auren-booking-engine
2. Descomprime el ZIP.
3. Abre la carpeta del proyecto en el Explorador.
4. Haz clic derecho en Inicio y abre Terminal o PowerShell.
5. Entra a la carpeta del proyecto con `cd ruta\Auren-booking-engine`.
6. Si Windows bloquea scripts en esa terminal, ejecuta `Set-ExecutionPolicy -Scope Process Bypass`.
7. Ejecuta `./scripts/start-local.ps1`.

El script crea el entorno Python, instala dependencias, genera secretos locales y arranca el servidor. Los secretos quedan en `.local-secrets.ps1`, excluido de Git.

## Abrir
- Portal de clientes: http://127.0.0.1:8000/web/
- Panel administrativo: http://127.0.0.1:8000/web/admin.html
- Documentación interactiva de API: http://127.0.0.1:8000/docs

El token administrativo local se muestra en la terminal al iniciar. En el panel, pulsa "Conectar admin" y pégalo. No compartas ese token.

## Detener y volver a iniciar
Pulsa Ctrl+C en la terminal. Para volver a iniciar, ejecuta el mismo script; la base de datos y los secretos se conservan en tu carpeta local.

## Límites
Esto funciona en tu computadora y solo es accesible desde ella. Para mostrarlo a otra persona sin pagar hosting se puede usar temporalmente un túnel HTTPS gratuito, pero la computadora debe permanecer encendida y no se debe exponer una base de datos con información real. Esta configuración es para desarrollo y demostración, no para producción comercial.
