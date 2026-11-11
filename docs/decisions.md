# Decisiones de diseño de Chorus

## CH-001 — Chorus es una aplicación independiente

**Estado:** Aceptada.

Chorus tiene interfaz, API, repositorio, configuración y base de datos propios. No es una sección de la aplicación OSAP. Se conecta a servicios externos mediante APIs.

## CH-002 — La biblioteca personal es el núcleo

**Estado:** Aceptada.

Chorus debe ser útil para un músico individual. La colaboración no es requisito para usarlo.

## CH-003 — Un espacio personal por usuario

**Estado:** Aceptada.

Cada identidad de osap-auth se vincula a un único espacio personal permanente en Chorus.

## CH-004 — Capacidades contextuales

**Estado:** Aceptada.

No hay perfiles globales excluyentes de músico, director o compositor. Las responsabilidades dependen del grupo y del contexto.

## CH-005 — OSAP es catálogo externo; Chorus lo consulta en lectura

**Estado:** Aceptada.

En la primera etapa Chorus puede buscar, consultar y leer Works y Resources OSAP. Conserva referencias externas y no modifica el catálogo ni escribe en su base de datos.

## CH-006 — Las obras propias usan el modelo y formato V6

**Estado:** Aceptada.

Las obras propias del usuario se guardan en la base de datos y almacenamiento propios de Chorus, utilizando el modelo y formato V6 de osap-storage (Work, Resource y File). No se desarrollará un formato propietario Chorus alternativo. Los identificadores de esas entidades pertenecen a la instancia Chorus y no se presentarán como identificadores del catálogo OSAP.

## CH-007 — Editar no sobrescribe

**Estado:** Aceptada.

Cada modificación conserva las versiones anteriores y crea la revisión/fichero correspondiente conforme a las reglas V6. Una partitura consultada en OSAP nunca se modifica desde Chorus.

## CH-008 — Persistencia propia, contrato V6 compartido

**Estado:** Aceptada.

Chorus mantiene su propia base de datos y almacenamiento. La independencia de la aplicación no implica duplicar ni modificar el formato V6. La implementación debe ajustarse al esquema y las restricciones reales de osap-storage.

## CH-009 — Herramientas con biblioteca común

**Estado:** Aceptada.

Muse-encore y Chorus Study son herramientas dentro de la aplicación Chorus. Comparten identidad, biblioteca, autorización, base de datos y almacenamiento. Chorus Study no tiene usuarios ni biblioteca propios.

## CH-010 — Publicación OSAP posterior y explícita

**Estado:** Aceptada.

La primera etapa es de lectura de OSAP. La publicación de obras propias se diseñará posteriormente como una operación explícita que use los contratos oficiales OSAP; nunca sobrescribirá obras o Resources existentes.

## CH-011 — Cardinalidad obligatoria Work → Resource → File

**Estado:** Aceptada.

Una Work musical no está completa ni tiene entidad útil en la biblioteca si no dispone de al menos un Resource, y cada Resource debe contener al menos un File. La estructura válida es Work → uno o más Resources → uno o más Files por Resource. Un Resource sin File no se considera un Resource musical válido en Chorus.

Durante la composición el usuario puede definir una obra antes de grabar su primer fichero. Ese estado de trabajo puede mantenerse como borrador incompleto, pero no se confunde con una Work musical completa del modelo V6. Al guardar el primer fichero se materializa la cadena Work/Resource/File.

Chorus implementará y probará esta regla como primera implementación práctica del modelo V6, antes de que OSAP Storage lo despliegue. No se adoptan para Chorus los textos antiguos que permiten Work sin Resource o Resource sin File.

## CH-012 — DDL SQLite como banco de pruebas V6, no como motor definitivo

**Estado:** Aceptada para el piloto.

Se incorpora una migración SQLite de referencia en migrations/sqlite/001_v6_work_resource_file.sql. Las claves foráneas diferidas forman una cadena obligatoria Work → Resource → File y permiten crearla en una única transacción. Cada Resource tiene su propio File; un File no puede pertenecer a dos Resources.

SQLite se utiliza para probar las invariantes con el mínimo de infraestructura. Esta decisión no selecciona SQLite como motor definitivo de Chorus ni pretende congelar el DDL oficial de OSAP Storage. Los nombres y tipos de columnas del piloto son una base técnica explícita que deberá contrastarse con el contrato V6 completo antes de adoptarse como persistencia de producción.

El SHA-256 es nullable y no único; storage_pointer es opaco e interno y no se expone en DTO. El borrador anterior al primer fichero no se guarda como Work musical en estas tablas.

## Decisiones técnicas pendientes

- Congelar el modelo V6 completo, incluidos créditos, clasificaciones, serialización e IDs.
- Elegir motor definitivo de base de datos y estrategia de migraciones para Chorus.
- Definir la persistencia y recuperación de ficheros del almacenamiento propio.
- Contratos reales de osap-auth y lectura OSAP.
- Integración de Muse-encore.
- Contrato de entrada/salida del módulo Chorus Study.
- Compartición, permisos y publicación futura.
- Ejecutar pytest sobre el repositorio y cerrar cualquier fallo antes de considerar validada la migración.


## CH-013 — Draft de aplicación antes de materializar V6

**Estado:** Aceptada.

El trabajo previo al primer fichero se representa mediante `CreationDraft`, una entidad de aplicación Chorus separada de las tablas V6. Puede guardar título provisional y una referencia a una Work/Representation de OSAP, pero no crea una Work, Resource o File musical incompleta. Solo al recibir un fichero válido se materializa la cadena Work → Resource → File en una única transacción. Los borradores pertenecen al subject autenticado y no aceptan un propietario enviado por el cliente.

## CH-014 — MuseEncore como editor externo sin modificarlo

**Estado:** Aceptada.

Chorus utilizará el editor web oficial de MuseEncore sin copiar ni modificar su repositorio. MuseEncore permite abrir una partitura mediante el parámetro `?url` y exportar MusicXML comprimido `.mxl`. Chorus entrega el fichero de origen mediante una URL temporal firmada, con expiración y CORS limitado al origen del editor. El usuario exporta el `.mxl` y lo carga a Chorus mediante su API autenticada. No se presupone una API remota de exportación que MuseEncore no documenta actualmente.

## CH-015 — Búsqueda OSAP y uso de originales en modo lectura

**Estado:** Aceptada.

Chorus consulta OSAP mediante `POST /api/v1/searches`, `GET /api/v1/searches/{search_id}`, `GET /api/v1/representations/{representation_id}` y `GET /api/v1/representations/{representation_id}/download`. El usuario puede elegir una representación compatible con MuseEncore como base de trabajo. Chorus conserva los identificadores externos y la procedencia/derechos conocidos; nunca modifica el original ni escribe en OSAP.
## CH-016 — Audiencia del piloto: la predeterminada de osap-auth

**Estado:** Aceptada para el piloto.

Chorus no solicita una audiencia propia en `POST /auth/login`: usa la audiencia predeterminada de osap-auth (`osap-api`) y delega la validación de cada sesión en `GET /auth/me`. Esto permite ejecutar el piloto sin cambios en Auth ni en su configuración desplegada.

Una audiencia `chorus-api` es el endurecimiento previsto: requiere añadirla a `allowed_token_audiences`, aceptarla en `/auth/me` y solicitarla desde Chorus. No es requisito para la primera entrega y no debe presentarse como ya habilitada.
