# Auditoría de compatibilidad con OSAP Storage V6

**Estado:** revisión documental y de código fuente completada; criterio de cardinalidad Work → Resource → File confirmado por decisión de producto de Chorus.  
**Fecha:** 2026-11-08.  
**Repositorio revisado:** [recursosformacion/AI_osap-storage](https://github.com/recursosformacion/AI_osap-storage), rama `main`.  
**Alcance:** README, especificación de reconstrucción V6, propuesta OpenAPI V6, documentación de área personal, matriz de migración, migración SQL base y entidades/esquemas actuales.  
**No realizado:** no se ha ejecutado código, tests, migraciones ni consultas a producción; no se han modificado bases de datos ni objetos R2.

## 1. Conclusión ejecutiva

Chorus debe adoptar el **modelo lógico y el contrato V6 Work → Resource → File**, pero el repositorio `AI_osap-storage` todavía no contiene una implementación V6 utilizable como biblioteca de código o esquema SQL definitivo.

El README de Storage declara expresamente que el código actual conserva el modelo anterior y que los documentos V6 describen el objetivo, no una migración ya aplicada. La propuesta [OpenAPI V6](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-openapi-contract.md) es contractual y está marcada como propuesta, no como contrato desplegado ni DDL definitivo.

Por tanto:
- Chorus puede diseñar su dominio y sus adaptadores alrededor de Work, Resource y File.
- No debe copiar las clases, tablas ni DTO actuales de Storage como si fueran V6.
- No debe afirmar compatibilidad binaria o de serialización cerrada hasta que exista un esquema/contrato V6 congelado.
- La persistencia propia de Chorus debe mantener separadas las entidades musicales V6 y las relaciones privadas de usuario, biblioteca, versiones y permisos.

## 2. Evidencia: código actual frente a V6

El código versionado en `main` sigue siendo anterior a V6:

| Área | Código actual observado | Destino V6 documentado |
|---|---|---|
| Obra | `domain/entities/work.py` contiene campos mezclados de catálogo, origen, licencia y fichero | Work conserva identidad, metadatos catalográficos y autoría |
| Representación | `domain/entities/representation.py` define `Representation`; además define una clase `Resource` con `representation_id` | No existe Representation; Resource pertenece directamente a Work |
| File | `domain/entities/file.py` documenta SHA-256 como identificador único y deriva `storage_key()` del hash | SHA-256 es evidencia de integridad, no identidad ni clave física |
| Ubicación | `StorageLocation` y `StorageProvider` siguen en dominio y API | No son entidades del catálogo V6; File guarda el puntero físico opaco directamente |
| DTO/API | `api/schemas.py` expone `sha256`, `locations`, `provider_id` y estructuras `representations` | DTO V6 no exponen SHA, object_key, bucket, provider ni StorageLocation |

La migración base `infrastructure/db/migrations/001_baseline_schema.sql` confirma el esquema anterior: `files.sha256` tiene índice único, `storage_locations` mantiene `object_key` y `provider_id`, y las entidades Representation/Resource están separadas. Nada de eso debe trasladarse literalmente a Chorus.

## 3. Contrato lógico V6 que sí está documentado

La propuesta [v6-openapi-contract.md](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-openapi-contract.md) establece:

### Work
- Identidad canónica de la composición, metadatos catalográficos, clasificaciones y créditos de composición.
- No contiene licencia/derechos de un material, uploader, URL ni File.
- `reference_resource_id` es opcional y, si se usa, solo puede señalar un Resource hijo de esa Work.
- No se debe interpretar el Resource de referencia como el original histórico.

### Resource
- Pertenece directamente a una Work.
- Describe un material concreto: partitura, edición, arreglo, transcripción, grabación, interpretación u otro.
- Guarda procedencia/aportante y derechos/licencia cuando se conozcan.
- Puede tener cero Files; URL-only y materiales todavía no materializados son válidos.
- Sus créditos no admiten el rol composer. Arreglista, editor, adaptador, intérprete o traductor corresponden al Resource cuando estén documentados.

### File
- Pertenece a un único Resource.
- Un Resource puede tener varios Files (por ejemplo, PDF, MusicXML y MIDI).
- El DTO público contiene metadatos descriptivos y estado, no SHA-256 ni puntero físico.
- El puntero físico se conserva internamente en File; no se deriva del hash.
- El acceso/descarga se resuelve por separado mediante una operación autorizada.

### Identificadores
Work ID, Resource ID y File ID son tipos distintos y opacos. Los identificadores propios de Chorus deben pertenecer a su espacio de nombres y nunca presentarse como IDs del catálogo OSAP.

## 4. Cardinalidad vinculante para Chorus: Work → Resource → File

La decisión de producto para Chorus queda fijada:

- Una Work válida tiene uno o más Resources.
- Cada Resource válido tiene uno o más Files.
- Un File pertenece a un único Resource.
- Por tanto, no existe una Work completa/registrada en la biblioteca musical si no se puede recorrer Work → Resource → File.
- Un Resource sin File no constituye una obra utilizable y no debe persistirse como Resource válido en Chorus.

Una persona puede estar definiendo o componiendo una obra antes de guardar su primer fichero. Ese trabajo previo puede existir como estado de edición/borrador del proceso de creación, pero no debe confundirse con una Work musical completa del modelo V6. Al guardar el primer fichero se materializa la estructura Work → Resource → File.

La documentación antigua de Storage que admite Works sin Resources o Resources sin Files no se adopta para Chorus. Chorus parte del modelo V6 con esta cardinalidad estricta y servirá como implementación de prueba para validar su estructura antes de que OSAP Storage la implemente. La propuesta OpenAPI y los documentos de migración de Storage deberán armonizarse posteriormente con esta regla.

Esta decisión sustituye la sección anterior que trataba la cardinalidad como una contradicción pendiente. No se bloquea Chorus esperando a que OSAP termine su implementación: se implementa y prueba primero en Chorus, manteniendo explícita la compatibilidad semántica V6.

## 5. Área personal y privacidad: separación de responsabilidades

La especificación [v6-user-workspace-contributions.md](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-user-workspace-contributions.md) describe el espacio personal como una capa de aplicación distinta del catálogo:

- Incorporar una Work OSAP al espacio personal crea una relación, no una copia.
- Los borradores y materiales privados no aparecen en búsquedas ni índices públicos.
- Los Files privados/en revisión siguen el modelo File V6, pero su acceso está protegido por autorización en servidor.
- La identidad del usuario se obtiene de la sesión autenticada; no se acepta un `user_id` arbitrario del cliente.
- La aportación, revisión y publicación son procesos explícitos y auditables.
- La aceptación/promoción no debe duplicar entidades ni objetos físicos innecesariamente.

Para Chorus, esto significa que Work/Resource/File no deben convertirse en entidades con semántica musical distinta por ser privadas. La propiedad del espacio, las referencias personales, los permisos y el historial de versiones son relaciones/capas de Chorus. No se deben añadir a Work campos inventados como propietario editorial o uploader si el contrato V6 no los define.

La política de Chorus de conservar revisiones y no sobrescribir debe implementarse en su capa de aplicación/versionado, sin cambiar la semántica central de Work, Resource y File.

## 6. Almacenamiento físico

V6 elimina StorageLocation/StorageProvider como entidades del catálogo y guarda en File un puntero físico opaco. La migración de Storage conserva los objetos R2 y transforma referencias en base de datos; no copia, mueve, renombra ni borra objetos.

Chorus tiene almacenamiento propio. Puede usar un adaptador físico distinto, pero debe conservar la separación:
- File identifica el artefacto físico y sus metadatos.
- El puntero físico es interno y no forma parte del DTO público.
- El acceso se controla por Chorus API y permisos del objeto.
- No se debe usar SHA-256 como clave de almacenamiento, ID o mecanismo de deduplicación.

La forma exacta del puntero y la serialización interna deben esperar a que Storage publique el DDL/modelo V6 definitivo.

## 7. Qué puede implementarse ya en Chorus

Se puede avanzar sin inventar el esquema físico:
1. Interfaces de dominio para Work, Resource y File basadas solo en las semánticas confirmadas.
2. Adaptadores de lectura OSAP que traten los IDs externos como opacos y validen la cadena Work → Resource → File. Si el catálogo externo devuelve datos incompletos o incompatibles, Chorus debe señalarlos como tales; no crear entidades musicales vacías para acomodarlos.
3. Referencias de biblioteca personales separadas de las entidades musicales.
4. Autorización privada en servidor y pruebas que impidan fugas a búsquedas públicas.
5. Contratos de aplicación del generador de estudio, manteniendo `ScoreContract` como contrato especializado y no como modelo de biblioteca.
6. Pruebas de contrato con fixtures V6 explícitamente provisionales, identificadas como tales.

La consecuencia para Chorus es distinta de la que tendría una aplicación que esperase a consumir Storage ya desplegado: Chorus será la primera implementación práctica de estas reglas y permitirá probarlas antes de que OSAP Storage las adopte.

En Chorus sí se debe diseñar e implementar su propio DDL, serialización y restricciones Work → Resource → File, documentando que es la implementación piloto del contrato V6. No se debe copiar el DDL anterior de Storage ni afirmar que existe ya un DDL V6 oficial compartido.

No se debe implementar todavía:
- claves/IDs físicos asumidos;
- copia directa de clases V5;
- publicación o escritura en OSAP.

## 8. Bloqueos que deben cerrarse antes de la persistencia

- [x] Fijar para Chorus la cardinalidad Work → Resource → File. Queda pendiente que OSAP Storage armonice sus documentos y su implementación con esta regla.
- [ ] Publicar o aprobar un DDL V6 y modelo de dominio implementable.
- [ ] Congelar nombres, tipos, nulabilidad, vocabularios y restricciones de Work/Resource/File.
- [ ] Cerrar la serialización canónica y la política de IDs opacos/namespace.
- [ ] Precisar el contrato interno del puntero físico de File sin exponerlo en DTO.
- [ ] Definir cómo se separan versiones/revisiones de los Files V6.
- [ ] Definir cómo se relacionan usuario/espacio privado/contribución con Work/Resource/File sin alterar su semántica.
- [ ] Añadir pruebas contractuales verificables contra una versión V6 real.

## 9. Fuentes revisadas

- [README de AI_osap-storage](https://github.com/recursosformacion/AI_osap-storage/blob/main/README.md)
- [Reconstrucción, API, índice e implantación V6](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-reconstruction-api-index-cutover.md)
- [Contrato OpenAPI V6 propuesto](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-openapi-contract.md)
- [Área personal y aportaciones V6](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-user-workspace-contributions.md)
- [Inventario de migración V6](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-data-migration-mapping.md)
- [Matriz de campos Work](https://github.com/recursosformacion/AI_osap-storage/blob/main/docs/v6-work-field-mapping.md)
- [Esquema base versionado](https://github.com/recursosformacion/AI_osap-storage/blob/main/infrastructure/db/migrations/001_baseline_schema.sql)
- Código actual: `domain/entities/work.py`, `domain/entities/representation.py`, `domain/entities/file.py`, `api/schemas.py`.


## 10. Seguimiento: esquema piloto implementado en Chorus (2026-11-08)

Después de esta auditoría, Chorus ha incorporado una implementación SQLite de referencia en `migrations/sqlite/001_v6_work_resource_file.sql`, documentada en `docs/v6-pilot-schema.md`. No es un DDL oficial de AI_osap-storage ni pretende resolver los campos y relaciones que siguen pendientes en el contrato V6 completo.

La migración impone mediante claves foráneas diferidas la cadena Work → Resource → File al confirmar una transacción. Se han añadido seis pruebas en `tests/test_v6_schema.py` y un workflow de GitHub Actions. La ejecución del workflow terminó correctamente: **6 passed**.

Esto cierra el primer prototipo técnico de cardinalidad en Chorus. No cierra la definición del contrato V6 compartido, ni selecciona el motor definitivo de Chorus, ni implementa el almacenamiento físico o los borradores sin File.
