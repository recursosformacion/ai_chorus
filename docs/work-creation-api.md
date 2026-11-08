# Flujo API de creación y edición de obras

**Alcance:** solo Chorus. No se modifican módulos ni repositorios externos.  
**Principio:** el navegador y las herramientas se comunican con Chorus por API; Chorus consulta OSAP por su API. Ningún cliente accede directamente a bases de datos ni a rutas físicas.

## 1. Dos formas de empezar

El usuario no tiene que decidir de antemano si va a crear desde cero:

1. Puede buscar una Work en OSAP y examinar sus representaciones.
2. Puede elegir una representación compatible y usarla como punto de partida.
3. También puede saltarse la búsqueda y crear una partitura nueva con MuseEncore.

La selección de un original OSAP no modifica OSAP. La edición y el fichero final pertenecen a Chorus. La referencia de origen se conserva como procedencia del Resource propio. No se presupone que la licencia permita cualquier transformación: se conserva la información de derechos que devuelva OSAP cuando esté disponible; si no está disponible, queda desconocida, no se inventa.

## 2. Contratos OSAP verificados

La API actual de OSAP expone:

- `POST /api/v1/searches`: crea una búsqueda. El cuerpo admite `query`, `limit`, `page`, `composer`, `title`, `catalogue`, `instrumentation`, `language`, `formats`, `providers`, `voices` y `genres`.
- `GET /api/v1/searches/{search_id}`: recupera resultados y estado de la búsqueda.
- `GET /api/v1/representations/{representation_id}`: ficha de la representación.
- `GET /api/v1/representations/{representation_id}/download`: descarga el fichero o redirige al proveedor.
- `GET /api/v1/works/public/{work_id}`: ficha pública de una Work del índice.

Chorus encapsulará estas llamadas en su adaptador OSAP. No consulta tablas de OSAP ni construye URLs de proveedores a partir de datos no verificados.

## 3. Contratos API de Chorus

Todos los endpoints de biblioteca y borradores requieren identidad autenticada y autorización por propietario. El sujeto propietario se toma del token validado por Chorus, nunca de un `owner_id` enviado por el cliente.

### Búsqueda y selección OSAP

- `POST /api/v1/catalog/searches`: proxy de creación de búsqueda OSAP.
- `GET /api/v1/catalog/searches/{search_id}`: proxy de resultados.
- `GET /api/v1/catalog/representations/{representation_id}`: detalle de representación.

La interfaz muestra Work, compositor cuando OSAP lo proporciona, título de representación, proveedor, formato y disponibilidad. No se ofrece «abrir en editor» para PDF u otros formatos que MuseEncore no pueda importar.

### Crear borrador

`POST /api/v1/drafts`

Cuerpo:
- `title` opcional;
- `resource_type` opcional, con valor inicial `score`;
- no se envía `owner_sub`: lo establece la identidad autenticada.

Respuesta: identificador local, estado `editing` y metadatos del borrador. No crea filas Work, Resource ni File.

### Elegir una representación OSAP

`POST /api/v1/drafts/{draft_id}/source`

Cuerpo:
- `work_id`;
- `representation_id`.

Chorus consulta la ficha de la representación y descarga los bytes mediante la API OSAP. Verifica que el contenido es importable por MuseEncore y lo guarda temporalmente en el área de trabajo del borrador, no en la tabla V6 File. El borrador conserva los IDs externos, proveedor, formato, nombre y derechos conocidos.

El original no se modifica. Si la descarga no está disponible, el formato no es importable o el proveedor devuelve una página HTML/reto en vez del fichero, Chorus informa del problema y no simula una importación correcta.

### Abrir MuseEncore

`GET /api/v1/drafts/{draft_id}/editor`

Devuelve el enlace del editor configurado. Para un borrador vacío, abre MuseEncore en su pantalla inicial. Para un borrador con original OSAP, añade el parámetro `url` apuntando a un endpoint temporal firmado de Chorus.

MuseEncore documenta `?url=...` para abrir un fichero desde una URL. Su editor obtiene los bytes mediante `fetch`; por ello el endpoint temporal debe permitir CORS únicamente desde el origen del editor y el token debe expirar. No se entrega al editor la clave física del fichero ni un token OIDC reutilizable.

### Guardar el resultado

MuseEncore es una aplicación web externa. Su interfaz de exportación permite MusicXML comprimido `.mxl`, pero el editor no expone en su API pública actual un callback para enviar el resultado directamente a Chorus. Por tanto, sin modificar MuseEncore:

1. el usuario usa **File → Export → MusicXML** y selecciona el formato comprimido `.mxl`;
2. el navegador descarga el fichero;
3. el usuario lo selecciona en Chorus;
4. Chorus lo envía por `POST /api/v1/drafts/{draft_id}/files` como `multipart/form-data`.

Este es el único paso manual de intercambio de fichero. La validación, persistencia y materialización se realizan en el backend Chorus por API.

## 4. Materialización atómica Work → Resource → File

El endpoint de carga:

1. comprueba que el borrador pertenece al sujeto autenticado y sigue en estado `editing`;
2. valida extensión, MIME y estructura ZIP/MusicXML del `.mxl`;
3. guarda los bytes en el almacenamiento privado de Chorus con un puntero opaco;
4. en una única transacción inserta Work, Resource y File y cambia el borrador a `materialized`;
5. si falla la transacción, elimina el objeto recién escrito; un proceso de reconciliación podrá limpiar huérfanos en caso de caída abrupta.

Work, Resource y File se crean con IDs locales opacos de Chorus. El Resource conserva la procedencia OSAP si el borrador partía de una representación. Los derechos solo se rellenan si se conocen y han sido devueltos por una fuente fiable. SHA-256 sirve para integridad y no es único.

El endpoint es idempotente respecto a un borrador materializado: no debe crear otra Work si el cliente reintenta una carga ya confirmada. Una segunda versión del trabajo se crea como una nueva revisión/Resource según la política de versiones que se cierre; nunca sobrescribe el File anterior.

## 5. Formatos del editor

El README y el código público de MuseEncore confirman importación de MusicXML, MIDI, Capella, Guitar Pro y Power Tab, además de `.mscz`/`.mscx`; y exportación de MusicXML, MIDI, PDF, PNG, SVG y ficheros MuseScore. El exportador MusicXML dispone de `writeMxl` para producir el archivo comprimido `.mxl`.

PDF no es un formato de importación musical editable de MuseEncore. Un PDF OSAP puede consultarse/archivarse, pero no se ofrecerá como fuente de apertura directa en el editor.

## 6. Límites explícitos

- No se modifica el repositorio MuseEncore ni se incorpora una copia de su código a Chorus.
- La integración usa el editor web de MuseEncore y su parámetro documentado `?url`.
- No se afirma que el editor tenga una API de exportación remota: hoy no se ha encontrado ese contrato.
- La carga final del `.mxl` a Chorus se realiza por la API de Chorus.
- No se escribe en OSAP ni se cambia el Resource original.
- La referencia y licencia de origen se conservan; la licencia desconocida permanece desconocida.
- El espacio de borradores es aplicación Chorus, no una Work V6 incompleta.
- El primer File crea la cadena V6 completa en una transacción.


## 7. Estado de implementación del runtime

El primer servidor FastAPI está implementado en app/main.py. Los endpoints anteriores están disponibles en el piloto, con persistencia SQLite y ficheros locales privados. Las migraciones se registran para no ejecutarse dos veces. La carga MXL comprueba el contenedor ZIP, META-INF/container.xml, rootfile y raíz MusicXML; la materialización crea Work, Resource y File en una transacción.

La autenticación se describe en authentication-runtime.md. Chorus delega la validación del Bearer a osap-auth /auth/me y utiliza el user_id devuelto por Auth. La URL pública de Chorus, el origen de MuseEncore y los endpoints reales deben configurarse en osap.toml.

El runtime no resuelve aún la política de revisiones, las colecciones personales, el motor definitivo, el almacenamiento distribuido, los límites de concurrencia de producción ni el ciclo de recuperación/limpieza de objetos huérfanos. No se debe considerar listo para producción.
