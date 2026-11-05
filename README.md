# AUREN Booking Engine

Motor genérico de reservas desarrollado por AUREN. Incluye una API FastAPI y una interfaz web de demostración.

## Ver y utilizar la demostración

La interfaz está en `web/index.html`. No necesita instalar paquetes ni una API para probar el flujo visual.

### En computadora (Windows, macOS o Linux)

1. Descarga el repositorio desde **Code → Download ZIP** y descomprime el archivo.
2. Abre una terminal dentro de la carpeta del proyecto.
3. Ejecuta:

```bash
python -m http.server 5500
```

4. Abre en tu navegador: http://localhost:5500/web/

La demostración incluye reservas de ejemplo. Puedes crear reservas, buscar, filtrar, cancelar y comprobar que el mismo recurso no se reserve en horarios que se traslapan. Los cambios se guardan en el almacenamiento local del navegador.

## Ejecutar la API

Requiere Python 3.12 o compatible.

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
``

API: http://127.0.0.1:8000  
Documentación interactiva: http://127.0.0.1:8000/docs  
Health check: http://127.0.0.1:8000/health

## Estado actual

- API FastAPI con creación, consulta y cancelación de reservas.
- SQLite local para persistencia de la API.
- Validación de zona horaria y prevención de solapamientos.
- Interfaz web de demostración con almacenamiento local del navegador.
- CI: pruebas automatizadas ejecutadas correctamente en GitHub Actions.

**Importante:** la interfaz de demostración todavía no está conectada a la API. Sus datos son locales al navegador. La API usa su propia base SQLite. La integración entre ambas, autenticación, multiempresa, despliegue y base de datos de producción son etapas pendientes.
