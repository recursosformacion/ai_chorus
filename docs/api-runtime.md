# Chorus API runtime (piloto)

## Arranque del backend

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
$env:CHORUS_CONFIG="osap.toml"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 9600
```

La API inicializa las migraciones SQLite locales al arrancar. El almacenamiento privado y la base de datos están dentro de Chorus; no se accede a bases de datos OSAP ni a Cloudflare/R2.

## Interfaz web y Apache de desarrollo

La interfaz HTML/CSS/JavaScript está en `web/` y no se sirve desde FastAPI. El entorno local replica el patrón documentado para `osap-app`: Apache/XAMPP sirve `web/` como `DocumentRoot` y hace reverse proxy de `/api/` hacia `127.0.0.1:9600/api/`. El host local propuesto es `http://chorus-app`. No se usa Vite ni otro servidor de frontend. La configuración completa de VirtualHost, hosts de Windows y comprobaciones está en [apache-dev.md](apache-dev.md).

Arranque del backend: ver el comando de la sección siguiente. Una vez levantado, Apache puede servir la interfaz y las peticiones API por el mismo origen.

## Endpoints

- POST /api/v1/auth/login: proxy backend a osap-auth; valida el access token consultando /auth/me y guarda el refresh en cookie HttpOnly.
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

Todas las rutas de catálogo, borradores y carga requieren un access token de usuario válido y onboarding completado. Chorus lo valida mediante osap-auth /auth/me y lo reenvía a osap-api al consultar o descargar para conservar cuotas y analítica de usuario. El propietario se deriva del user_id devuelto por Auth, nunca del cuerpo de la petición.

## Límites del piloto

- El motor de persistencia es SQLite para pruebas y desarrollo, no una decisión de producción.
- Los ficheros se guardan en almacenamiento local privado. No hay aún backend de almacenamiento distribuido ni recuperación ante desastre.
- La API de catálogo depende de los endpoints actuales documentados en work-creation-api.md; la forma de los DTO debe seguir contrastándose con respuestas de la instancia desplegada.
- La integración de MuseEncore requiere exportar .mxl y subirlo a Chorus; no hay callback remoto de exportación.
- La audiencia chorus-api debe habilitarse en osap-auth. No se modifica ni la API ni la configuración de Auth desde este repositorio.
