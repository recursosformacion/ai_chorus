# Espacios de trabajo y trabajos de preparación — Modelo técnico definitivo

**Estado:** consolidado e implementado sobre MariaDB 10.4.32  
**Fecha:** 2026-11-21  
**Alcance:** modelo de datos, API y experiencia de usuario de espacios personales, grupos y proyectos.

---

## 1. Entidades

| Entidad | Tabla | Descripción |
|---------|-------|-------------|
| **Space** | `spaces` | Ámbito de trabajo: `personal`, `group` o `project`. Contiene trabajos de preparación. |
| **PreparationWork** | `preparation_works` | Trabajo que se prepara dentro de un espacio. Pertenece a **un único** `space_id`. |
| **PreparationWorkItem** | `preparation_work_items` | Obra + Resource incorporadas a un trabajo, con voz/instrumento, orden y estado. |
| **PreparationWorkFile** | `preparation_work_files` | Referencia de un `File` a un trabajo, con propósito y orden. No es una copia. |
| **File** | `files` | Archivo físico registrado en Chorus (puntero a almacenamiento privado, sha256, tamaño). |
| **Resource** | `resources` | Interpretación/arreglo de una Work (V6). Puede compartirse con un grupo y restringirse a una sección. |
| **Work** | `works` | Obra canónica (V6). Puede ser privada (`owner_sub`) o compartida (`resources.group_id`). |

### 1.1 Identidad del espacio

- `spaces.id` — UUID hex opaco. Es la única referencia usada por la API.
- `spaces.space_type` — `personal` | `group` | `project`.
- `spaces.owner_sub` — propietario de espacios privados `personal` y `project`; es `NULL` en espacios colectivos.
- `spaces.group_id` — grupo asociado. `NOT NULL` para `group` y proyectos compartidos; `NULL` para espacios personales y proyectos privados.
- Un `project` puede ser privado (owner_sub del usuario y sin group_id) o compartido (group_id y sin owner_sub).
- `spaces.general_group_id` — columna generada (`IF(space_type='group', group_id, NULL)`) con índice único `uq_spaces_general_group`.

### 1.2 Espacio general de un grupo

Un grupo tiene **un único espacio general** (`space_type='group'`) y puede tener **varios** espacios `project`.

- La unicidad se garantiza en la base de datos mediante `uq_spaces_general_group`.
- `_group_space()` resuelve siempre ese espacio; nunca devuelve un proyecto.
- La creación es idempotente: si dos peticiones compiten, el índice único hace fallar el `INSERT` y se relee el espacio existente.
- Las rutas históricas `/api/v1/groups/{group_id}/preparation-works` operan sobre el espacio general.

---

## 2. Reglas de acceso

### 2.1 Visibilidad de espacios

| Tipo | Quién lo ve |
|------|-------------|
| `personal` | Sólo `owner_sub`. |
| Proyecto privado | Sólo `owner_sub`. |
| `group` / proyecto compartido | Miembros **activos** del grupo asociado. |
| Cualquiera | Admin de plataforma. |

`owner_sub` **no** concede visibilidad en espacios colectivos. Quien deja de ser miembro (abandono o expulsión) deja de ver el espacio en el listado **y** en el acceso directo por id, así como sus trabajos, items y archivos.

### 2.2 Gestión

| Operación | Permiso |
|-----------|---------|
| Gestión del espacio (nombre, descripción) | Admin, propietario (personal/proyecto privado), manager del grupo. |
| Crear/editar/borrar trabajos, items y referencias | Admin, propietario (personal/proyecto privado), manager del grupo, **director musical**. |
| Consultar | Admin, propietario, miembro activo. |

El creador de un espacio colectivo **no** conserva permisos de gestión por haberlo creado: derivan de su membresía.

### 2.3 Uso de Works, Resources y Files

Un usuario puede incorporar una Work/Resource a un espacio si:

- Es propietario de la Work (`works.owner_sub = user_id`), o
- La Resource está compartida con el grupo del espacio (`resources.group_id = spaces.group_id`), o
- Es admin de plataforma.

Además, si la Resource está restringida a una sección (`resources.group_section_id`):

- El manager del grupo accede a todas las secciones.
- Un miembro sólo accede si su `group_members.section_id` coincide.

Conocer un `file_id` **no** autoriza. La autorización de sección **se revalida en cada acceso** (listado y descarga), no se hereda del momento en que el archivo se incorporó a la preparación. La comprobación está centralizada en `_prep_file_section_allowed()`, que usan tanto `_list_prep_files()` (filtrando los elementos devueltos) como `_stream_prep_file()` (único punto de acceso al almacenamiento para archivos de preparación), del que cuelgan la ruta canónica por id y la ruta histórica por nombre con idéntica exigencia.

Efectos:

- Un miembro de otra sección no ve el archivo en el listado.
- Su descarga responde `403` sin entregar contenido, tanto por id como por nombre.
- Un archivo sin `group_section_id` mantiene la visibilidad normal del espacio.
- La pérdida de membresía elimina el acceso en la siguiente petición.

---

## 3. Archivos: modelo unificado

Todo archivo incorporado a una preparación queda registrado de forma coherente:

```
almacenamiento privado (bytes)
        ↓ storage_pointer
files (id, resource_id, name, sha256, size_bytes, mime_type)
        ↓ resource_id
resources (id, work_id, group_id, part_label)
        ↓ work_id
works (id = "pw-<preparation_work_id>", owner_sub = quien subió)
        ↑
preparation_work_files (preparation_work_id, file_id, purpose, sort_order)
```

- La Work contenedora es **determinista** (`pw-<work_id>`): varias subidas al mismo trabajo la reutilizan.
- `resources.group_id` se rellena con el grupo si el espacio es colectivo; en un proyecto privado queda `NULL` y el archivo permanece privado.
- `part_label` de la subida se guarda en `resources.part_label`.
- Identificadores estables: `preparation_work_files.id` (referencia) y `files.id` (File).

### 3.1 Borrado

- Eliminar una **referencia** (`preparation_work_files`) sólo quita el vínculo con ese trabajo.
- **No** se borra el archivo físico, ni el registro `files`, ni la `resources` contenedora.
- Eliminar un **trabajo** elimina en cascada sus items y referencias, pero nunca Works, Resources o Files.

### 3.2 Autorización de acceso

| Operación | Punto de control |
|-----------|------------------|
| Listar archivos | `_list_prep_files()` filtra por `_prep_file_section_allowed()` |
| Descargar por id | `download_prep_file_by_id()` → `_stream_prep_file()` |
| Descargar por nombre | `download_preparation_file()` → `_stream_prep_file()` |
| Incorporar archivo | `add_preparation_work_file()` → `_can_use_file_in_space()` |

`_stream_prep_file()` es el único camino hacia `_stream_stored_file()` para archivos de preparación: no existe una ruta alternativa que eluda la restricción de sección.

---

## 4. Semántica PATCH

Todos los endpoints de actualización aplican la misma regla:

| Envío del cliente | Efecto |
|-------------------|--------|
| Campo omitido | Conserva su valor actual. |
| Campo con valor | Se actualiza. |
| Campo explícitamente `null` | Se limpia, si la columna admite `NULL`. |
| Campo explícitamente `null` en columna `NOT NULL` | `400` (`Field '<x>' cannot be null`). |
| Cuerpo vacío | Sin efecto; devuelve el estado actual. |

Se implementa con `model_fields_set` de Pydantic y el helper `_apply_patch_fields`.

---

## 5. Endpoints

### 5.1 Espacios

| Método | Ruta |
|--------|------|
| GET | `/api/v1/spaces` |
| POST | `/api/v1/spaces` |
| GET/PATCH | `/api/v1/spaces/{space_id}` |
| POST | `/api/v1/spaces/{space_id}/convert` |

### 5.2 Trabajos de preparación

| Método | Ruta canónica | Ruta histórica (compatible) |
|--------|---------------|-----------------------------|
| GET | `/api/v1/spaces/{space_id}/preparation-works` | `/api/v1/groups/{group_id}/preparation-works` |
| POST | `/api/v1/spaces/{space_id}/preparation-works` | `/api/v1/groups/{group_id}/preparation-works` |
| GET | `/api/v1/spaces/{space_id}/preparation-works/{work_id}` | `/api/v1/groups/{group_id}/preparation-works/{work_id}` |
| PATCH | `/api/v1/spaces/{space_id}/preparation-works/{work_id}` | `/api/v1/groups/{group_id}/preparation-works/{work_id}` |
| DELETE | `/api/v1/spaces/{space_id}/preparation-works/{work_id}` | `/api/v1/groups/{group_id}/preparation-works/{work_id}` |

Ambos juegos **comparten implementación y autorización**. La ruta histórica resuelve el espacio general del grupo.

### 5.3 Items

| Método | Ruta |
|--------|------|
| GET/POST | `/api/v1/spaces/{space_id}/preparation-works/{work_id}/items` |
| PATCH/DELETE | `/api/v1/spaces/{space_id}/preparation-works/{work_id}/items/{item_id}` |

### 5.4 Archivos

| Método | Ruta | Notas |
|--------|------|-------|
| GET | `/api/v1/spaces/{space_id}/preparation-works/{work_id}/files` | Modelo unificado. |
| POST | `/api/v1/spaces/{space_id}/preparation-works/{work_id}/files` | Referencia un `file_id` existente. |
| DELETE | `/api/v1/spaces/{space_id}/preparation-works/{work_id}/files/{file_ref_id}` | Quita la referencia. |
| GET | `/api/v1/spaces/{space_id}/preparation-works/{work_id}/files/{file_id}/download` | Descarga por id estable. |
| POST | `/api/v1/groups/{group_id}/preparation-works/{work_id}/files` | Multipart; delega en el modelo unificado. |
| GET | `/api/v1/groups/{group_id}/preparation-works/{work_id}/files` | Mismo resultado que la ruta canónica. |
| GET | `/api/v1/groups/{group_id}/preparation-works/{work_id}/files/{file_name}/download` | Compatibilidad por nombre. |
| DELETE | `/api/v1/groups/{group_id}/preparation-works/{work_id}/files/{file_name}` | Quita la referencia por nombre. |

---

## 6. Migraciones relevantes

| Migración | Aporta |
|-----------|--------|
| `037_spaces.sql` | Tabla `spaces` + índices condicionales. |
| `038_preparation_work_items.sql` | Items con FK compuesta `(work_id, resource_id) → resources(work_id, id)`. |
| `039_preparation_work_files.sql` | Referencias a `files`. |
| `040_migrate_preparation_works_to_spaces.sql` | `group_id` → `space_id`; **aborta** si queda algún trabajo sin migrar; elimina `group_id`. |
| `041_consolidate_spaces.sql` | `owner_sub` nullable, normalización, espacio general único, resuelve duplicados. |

### 6.1 Idempotencia y aborto

- Todas comprueban `information_schema` antes de crear columnas, índices o FKs.
- MariaDB 10.4.32 no soporta `SIGNAL` en sentencias preparadas (error 1295), por lo que el aborto de la migración 040 se fuerza con una referencia a una tabla inexistente (error 1146). La migración falla, no se registra y el runner se detiene.
- El paso de reasignación de la migración 040 sólo se ejecuta si `group_id` todavía existe, de modo que la reejecución es inocua.

---

## 7. Protección de la base de datos de pruebas

`app/dbguard.py` centraliza la comprobación **sobre la conexión efectiva**:

- Base de datos: `osap_chorus_test`
- Usuario: `osap2027_test`
- Servidor: MariaDB línea 10.4

Lo usan tanto los fixtures `autouse` de `tests/conftest.py` como `scripts/rebuild_test_db.py`. Si la conexión es válida pero apunta a otro destino se aborta con error; si no hay MariaDB utilizable se reporta como no disponible para omitir los tests. Ninguna limpieza destructiva se ejecuta sin pasar por el guard.

---

## 8. Verificación del esquema

`scripts/rebuild_test_db.py` comprueba, además de tablas y columnas:

- Nulabilidad de `spaces.group_id`, `spaces.owner_sub` y `preparation_works.space_id`.
- Ausencia de `preparation_works.group_id` tras la migración.
- FKs esperadas (y ausencia de la FK antigua).
- Índices, incluido `uq_spaces_general_group`.
- Integridad: trabajos sin espacio, items sin trabajo, referencias sin archivo, Resources que no pertenecen a su Work, espacios personales con grupo, espacios colectivos sin grupo, `owner_sub` en espacios no personales, y grupos con más de un espacio general.

La reconstrucción falla si cualquiera de estas comprobaciones no se cumple.

---

## 9. Compatibilidad

- Las rutas históricas de grupos siguen operativas y delegan en la implementación canónica.
- El contrato de subida multipart se mantiene (`parts`, `part_label`, `purpose`) y añade `id` y `file_id` estables.
- El listado histórico conserva la clave `name`.

## 10. Proyectos personales independientes

Un usuario particular puede crear tantos espacios `project` privados como necesite, sin crear una entidad ni un grupo OSAP. Cada proyecto:
- Tiene `owner_sub` del usuario y `group_id = NULL`.
- Sólo aparece en el listado y en las rutas de ese propietario.
- Admite trabajos de preparación y sus archivos privados.
- No se comparte automáticamente con ningún grupo.

Los proyectos asociados a un grupo mantienen el modelo colectivo y sus permisos de membresía. La migración 042 sustituye la restricción de ownership para admitir ambos casos sin alterar los proyectos existentes.

## 11. Interfaz de usuario

- El formulario de eventos se muestra dentro de la ventana de Agenda; no abre una segunda ventana de aplicación.
- El botón `Añadir obra` del repertorio crea un trabajo de preparación en el espacio activo, no redirige a la biblioteca personal.
- La sección `Mis proyectos` permite crear y abrir proyectos privados.
- El botón de cuenta en la cabecera abre la edición del nombre y nickname del usuario.
- La gestión del grupo permite mantener la información colectiva y los datos de participación de sus miembros (voz/instrumento, sección, cargo y rol musical). Los datos personales de cuenta sólo los modifica el propio usuario.

## 12. Proyectos privados de particulares

`POST /api/v1/spaces` acepta `{"space_type":"project","name":"..." }` sin `group_id`. El propietario queda registrado en `owner_sub`; el proyecto se aísla de los grupos y admite trabajos y subidas privadas. La migración 042 sustituye la restricción anterior de ownership, con comprobación previa de las filas existentes.
