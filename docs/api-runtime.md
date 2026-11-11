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
- GET /api/v1/works/{id}/integrity: comprueba que el fichero privado existe y que su SHA-256 y tamaño coinciden con la base de datos.
- GET /api/v1/library y POST /api/v1/library/references: biblioteca personal y referencias OSAP sin duplicar contenido.
- POST /api/v1/library/works/{id}: añade una obra propia a la biblioteca; se crea automáticamente al materializar.
- GET/POST /api/v1/collections y POST/DELETE /api/v1/collections/{id}/items: colecciones personales.\n- GET /api/v1/works/{id}/integrity: comprueba que el fichero privado existe y que su SHA-256 y tamaño coinciden con la base de datos.\n- GET /api/v1/library y POST /api/v1/library/references: biblioteca personal y referencias OSAP sin duplicar contenido.\n- POST /api/v1/library/works/{id}: añade una obra propia a la biblioteca; se crea automáticamente al materializar.\n- GET/POST /api/v1/collections y POST/DELETE /api/v1/collections/{id}/items: colecciones personales.

Todas las rutas de catálogo, borradores y carga requieren un access token de usuario válido y onboarding completado. Chorus lo valida mediante osap-auth /auth/me y lo reenvía a osap-api al consultar o descargar para conservar cuotas y analítica de usuario. El propietario se deriva del user_id devuelto por Auth, nunca del cuerpo de la petición.

## Límites del piloto

- El motor de persistencia es SQLite para pruebas y desarrollo, no una decisión de producción.
- Los ficheros se guardan en almacenamiento local privado. No hay aún backend de almacenamiento distribuido ni recuperación ante desastre.
- La API de catálogo depende de los endpoints actuales documentados en work-creation-api.md; la forma de los DTO debe seguir contrastándose con respuestas de la instancia desplegada.
- La integración de MuseEncore requiere exportar .mxl y subirlo a Chorus; no hay callback remoto de exportación.
- El piloto usa la audiencia predeterminada de osap-auth (`osap-api`) y valida cada sesión en `/auth/me`. La audiencia propia `chorus-api` queda como endurecimiento posterior (CH-016); no se modifica Auth desde este repositorio.

## Verificación del piloto (2026-11-11)

Con `osap.toml` apuntando a los hosts locales `http://osap-app` y `http://osap-auth/auth-api`:

- `GET /health` → 200 `{"status":"ok","service":"chorus-api"}`.
- `GET /api/v1/auth/me` sin token → 401 (cierre por defecto).
- `GET /api/v1/catalog/searches/x` sin token → 401.
- `GET /api/v1/auth/legal/current` → 200 (proxy a Auth).
- `POST /api/v1/auth/login` con credenciales inválidas → 401 (Auth alcanzable, sin 502).

La prueba con credenciales reales y el puente a MuseEncore quedan pendientes de disponer del editor configurado.

## Página web de prueba (2026-11-11)

La web se sirve en `http://chorus-app/` con Apache y el backend en `127.0.0.1:9600`:

```powershell
# backend
cd D:\Proyectos\AI_OSAP\Chorus
$env:CHORUS_CONFIG="osap.toml"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 9600

# editor MuseEncore (sin tocar hosts)
python -m http.server 9601 --bind 127.0.0.1 --directory D:\Proyectos\AI_OSAP\muse-encore\dist-editor
```

Comprobaciones: `GET http://chorus-app/health` → 200; `GET http://chorus-app/api/v1/library` sin sesión → 401; `http://127.0.0.1:9601/` → editor. La vhost de Apache apunta a `Chorus/web`; si Apache aún no se ha reiniciado, el junction `ai_chorus` mantiene el servicio.
