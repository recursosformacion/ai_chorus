# Chorus — interfaz web en el Apache de desarrollo

## Patrón que sigue

El entorno de desarrollo de OSAP está descrito en `AI_GAMEPC2/docs/osap/dev-environment.md`:

- Apache/XAMPP sirve los ficheros del frontend desde un `DocumentRoot`.
- Apache hace de reverse proxy para las rutas API hacia Uvicorn en `127.0.0.1`.
- El navegador utiliza un único origen y no necesita CORS para llamar al backend.
- No se utiliza `vite dev` ni un servidor de desarrollo de frontend.

Chorus adopta el mismo patrón. Su web es HTML, CSS y JavaScript estático; FastAPI sigue siendo responsable de la API y de la persistencia. No se monta la web desde FastAPI.

## Host local

Añadir al fichero de hosts de Windows:

```text
127.0.0.1 chorus-app
```

## VirtualHost Apache

Añadir un bloque propio en `C:\\xampp\\apache\\conf\\extra\\httpd-vhosts.conf`:

```apache
<VirtualHost *:80>
    ServerName chorus-app
    DocumentRoot "D:/Proyectos/AI_OSAP/ai_chorus/web"

    <Directory "D:/Proyectos/AI_OSAP/ai_chorus/web">
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
        DirectoryIndex index.html

        <IfModule mod_headers.c>
            <FilesMatch "\\.(html|js|css)$">
                Header set Cache-Control "no-store, no-cache, must-revalidate, max-age=0"
            </FilesMatch>
        </IfModule>
    </Directory>

    ProxyPreserveHost On
    ProxyPass        /api/  http://127.0.0.1:9600/api/
    ProxyPassReverse /api/  http://127.0.0.1:9600/api/

    ProxyPass        /health  http://127.0.0.1:9600/health
    ProxyPassReverse /health  http://127.0.0.1:9600/health

    ProxyPass        /docs  http://127.0.0.1:9600/docs
    ProxyPassReverse /docs  http://127.0.0.1:9600/docs

    ProxyPass        /openapi.json  http://127.0.0.1:9600/openapi.json
    ProxyPassReverse /openapi.json  http://127.0.0.1:9600/openapi.json

    ErrorLog  "logs/chorus-app-error.log"
    CustomLog "logs/chorus-app-access.log" combined
</VirtualHost>
```

Comprobar que Apache tiene activos `mod_proxy`, `mod_proxy_http` y `mod_headers`. No se necesita `mod_rewrite`: esta primera interfaz utiliza una única página HTML y no tiene rutas cliente profundas.

## Configuración de Chorus

Crear `osap.toml` a partir de `osap.toml.example`. Para el entorno local, completar las URL de Auth, OSAP y MuseEncore que correspondan a los servicios que se estén ejecutando. Valores específicos del frontal local:

```toml
[editor]
# URL real de MuseEncore; completar con el origen que se use en desarrollo.
base_url = ""
origin = ""

[app]
cors_origins = []
public_base_url = "http://chorus-app"
secure_cookies = false
```

`secure_cookies = false` solo es válido para este host HTTP local. En cualquier entorno HTTPS debe volver a `true`. Si se carga un original de OSAP en MuseEncore, el origen configurado en `editor.origin` debe coincidir exactamente con el origen real del editor; el endpoint temporal limita CORS a ese origen.

## Arranque y comprobación

Terminal 1, desde `D:\\Proyectos\\AI_OSAP\\ai_chorus`:

```powershell
$env:CHORUS_CONFIG = "osap.toml"
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 9600
```

Terminal 2 / navegador:

- `http://chorus-app/` — interfaz HTML.
- `http://chorus-app/health` — healthcheck del backend a través de Apache.
- `http://chorus-app/docs` — OpenAPI del backend a través de Apache.

Tras editar HTML, CSS o JavaScript basta recargar la página (Ctrl+F5); Apache sirve directamente los ficheros. Los cambios Python requieren que Uvicorn los recargue o reinicie.

## Límites actuales

- La interfaz es una primera versión funcional en HTML/CSS/JavaScript sin framework ni proceso de build.
- Login, búsqueda, creación de borrador, selección de original, apertura de MuseEncore y subida MXL consumen exclusivamente la API Chorus bajo `/api/v1`.
- El access token solo se mantiene en memoria del navegador; el refresh token queda en cookie HttpOnly gestionada por el backend.
- El flujo de onboarding de cuentas que aún no lo hayan completado debe resolverse antes de usar Chorus.
- La configuración local de Apache no se modifica automáticamente desde el repositorio: hay que añadir el VirtualHost y el host local en el equipo de desarrollo.
