# Instalación de MuseEncore para el entorno de desarrollo

MuseEncore es una aplicación independiente del repositorio Chorus. No se copia su código dentro de Chorus ni se modifica su repositorio: se clona en un directorio propio, se instalan sus dependencias y se genera su frontend compilado. Apache sirve ese resultado estático.

Repositorio: https://github.com/pstaender/muse-encore

## Qué contiene

El repositorio tiene dos aplicaciones:

- `editor/`: editor de partituras MuseEncore (React + Vite).
- `viewer/`: visor, que no sustituye al editor.

El editor se construye con el script `build:editor` y Vite genera los ficheros en `dist-editor/`. El proyecto incluye el submódulo `MuseScore`, necesario para los recursos de traducción y sonido; por eso es imprescindible clonar con `--recurse-submodules`.

MuseEncore se distribuye bajo GPL-3.0-only. Mantener su licencia y avisos al desplegarlo; no integrar su código en Chorus como si fuera código propio.

## Clonar e instalar en Windows

Desde PowerShell:

```powershell
cd D:\Proyectos\AI_OSAP
git clone --recurse-submodules https://github.com/pstaender/muse-encore.git
cd muse-encore
npm ci
npm run build:editor
```

Comprobar que existe `dist-editor\index.html`. Si no existe, no configurar Apache todavía: revisar el error de compilación y el estado del submódulo.

Para actualizar una instalación existente:

```powershell
cd D:\Proyectos\AI_OSAP\muse-encore
git pull --ff-only
git submodule update --init --recursive
npm ci
npm run build:editor
```

No ejecutar `git pull` si hay cambios locales en el checkout; revisar primero `git status`.

## Servir el editor mediante Apache

Se utiliza un VirtualHost separado para que Vite pueda servir los assets desde la raíz `/` sin reescrituras ni cambios en el código del editor. Añadir al mismo `httpd-vhosts.conf`:

```apache
<VirtualHost *:80>
    ServerName muse-encore-app
    DocumentRoot "D:/Proyectos/AI_OSAP/muse-encore/dist-editor"

    <Directory "D:/Proyectos/AI_OSAP/muse-encore/dist-editor">
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
        DirectoryIndex index.html
    </Directory>

    ErrorLog  "logs/muse-encore-app-error.log"
    CustomLog "logs/muse-encore-app-access.log" combined
</VirtualHost>
```

Añadir al fichero hosts de Windows:

```text
127.0.0.1 muse-encore-app
```

Reiniciar Apache y abrir `http://muse-encore-app/`. Esta URL debe mostrar el editor ya compilado; Apache no ejecuta Node ni Vite.

## Conectar Chorus

En `ai_chorus/osap.toml`:

```toml
[editor]
base_url = "http://muse-encore-app"
origin = "http://muse-encore-app"
source_token_ttl_seconds = 300
```

El backend Chorus construye la URL de edición sobre este origen. El editor admite `?url=...` para cargar una partitura desde una URL temporal. El origen configurado debe coincidir exactamente con el origen del VirtualHost y con la allow-list CORS del endpoint temporal de Chorus.

La URL temporal de una partitura debe ser de corta duración y solo lectura. Nunca se pasa al editor el access token de OSAP ni el `storage_pointer` interno.

## Actualizar MuseEncore

Cuando se decida actualizar la versión:

1. Revisar los cambios y la licencia del repositorio upstream.
2. Actualizar el checkout y el submódulo.
3. Ejecutar `npm ci` y `npm run build:editor`.
4. Comprobar el editor directamente en `http://muse-encore-app/`.
5. Probar desde Chorus la apertura de un original y la exportación MusicXML comprimida (.mxl).

## Alcance y límites

- Este procedimiento instala y sirve el editor web. No instala MuseScore Desktop.
- No se modifica el repositorio upstream de MuseEncore.
- No se integra su almacenamiento local de partituras con la biblioteca Chorus; el intercambio inicial sigue siendo por URL temporal de lectura y exportación/subida MXL.
- El build debe realizarse cada vez que se actualice el repositorio; Apache sirve el directorio `dist-editor`, no los fuentes TypeScript.

## Estado local (2026-11-11)

- Dependencias instaladas con el npm real (`C:\Program Files\nodejs\npm.cmd`); el alias `npm` del PATH apunta a pnpm y falla con `ci`.
- `npm run build:editor` completado: `dist-editor/` generado (~102 MB).
- Para probar sin tocar el fichero `hosts` (requiere administrador), el editor se sirve con un servidor estático:

```powershell
python -m http.server 9601 --bind 127.0.0.1 --directory D:\Proyectos\AI_OSAP\muse-encore\dist-editor
```

  y en `ai_chorus/osap.toml`:

```toml
[editor]
base_url = "http://127.0.0.1:9601"
origin = "http://127.0.0.1:9601"
```

- El VirtualHost `muse-encore-app` ya está añadido a `httpd-vhosts.conf`. Para usarlo: añadir `127.0.0.1 muse-encore-app` al fichero `hosts` como administrador, reiniciar Apache y cambiar `base_url`/`origin` a `http://muse-encore-app`.
- La vhost de Chorus se corrigió a `D:/Proyectos/AI_OSAP/Chorus/web`; hasta el próximo reinicio de Apache se usa un junction `ai_chorus -> Chorus` para no bloquear las pruebas.

## Flujo de prueba con el editor

1. Abrir `http://chorus-app/` e iniciar sesión con una cuenta OSAP.
2. Buscar una obra, elegir una representación y crear el borrador.
3. Pulsar “Abrir en MuseEncore”: Chorus entrega una URL temporal de solo lectura (5 minutos, CORS limitado al origen del editor).
4. Editar, exportar `.mxl` y subirlo en Chorus; la cadena Work → Resource → File se materializa y aparece en la biblioteca.

## Guardado y vuelta a Chorus

MuseEncore guarda las partituras **en el navegador** (IndexedDB vía Dexie), recuerda la partitura abierta en `localStorage` y mantiene autosaves en IndexedDB. “Guardar en el ordenador” descarga un `.mscz`; “Exportar” descarga PDF/PNG/SVG/MIDI/MusicXML. **No escribe en la base de datos ni en el almacenamiento de Chorus**: el puente es exportar `.mxl` y subirlo desde Chorus. Hasta esa subida no existe copia en Chorus; borrar los datos del sitio elimina las copias del navegador.

La web de Chorus abre el editor en `/editor.html`, una página propia con barra superior “← Volver a Chorus”, el título del borrador y un `iframe` con MuseEncore. Así se recupera la pantalla de Chorus sin depender de que el editor tenga un botón de vuelta propio (no lo tiene). El título se muestra en esa barra; dentro del editor solo aparece si el fichero cargado lo contiene: `?url=` carga la partitura, no un título.
