# Chorus API runtime (piloto)

## Arranque

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
$env:CHORUS_CONFIG="osap.toml"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 9600
```

La API inicializa las migraciones SQLite locales al arrancar. El almacenamiento privado y la base de datos están dentro de Chorus; no se accede a bases de datos OSAP ni a Cloudflare/R2.

## Endpoints

- POST /api/v1/auth/login: proxy backend a osap-auth con audiencia Chorus; refresh en cookie HttpOnly.
- POST /api/v1/auth/refresh: rotación de refresh.
- GET /api/v1/auth/me y GET /api/v1/auth/legal/current: perfil y versiones legales.
- POST /api/v1/auth/onboarding: completa nickname y aceptación legal en osap-auth.
- POST /api/v1/auth/logout: revoca la sesión actual.
- POST /api/v1/catalog/searches, GET /api/v1/catalog/searches/{id}.
- GET /api/v1/catalog/representations/{id}.
- POST /api/v1/drafts, GET /api/v1/drafts/{id}.
- POST /api/v1/drafts/{id}/source: descarga una representación mediante API OSAP y la conserva en staging privado.
- GET /api/v1/drafts/{id}/editor: crea enlace temporal para MuseEncore.
- GET /api/v1/editor-sources/{token}: fuente temporal CORS restringida al origen configurado del editor.
- POST /api/v1/drafts/{id}/files: valida y guarda un archivo .mxl; materializa Work → Resource → File en una transacción.

Todas las rutas de catálogo, borradores y carga requieren un access token de usuario válido y onboarding completado. El propietario se deriva de sub, nunca del cuerpo de la petición.

## Límites del piloto

- El motor de persistencia es SQLite para pruebas y desarrollo, no una decisión de producción.
- Los ficheros se guardan en almacenamiento local privado. No hay aún backend de almacenamiento distribuido ni recuperación ante desastre.
- La API de catálogo depende de los endpoints actuales documentados en work-creation-api.md; la forma de los DTO debe seguir contrastándose con respuestas de la instancia desplegada.
- La integración de MuseEncore requiere exportar .mxl y subirlo a Chorus; no hay callback remoto de exportación.
- La audiencia chorus-api debe habilitarse en osap-auth. No se modifica ni la API ni la configuración de Auth desde este repositorio.
