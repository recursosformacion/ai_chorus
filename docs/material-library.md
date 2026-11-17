# Biblioteca de material en curso (análisis y diseño)

> Estado: **implementación parcial en dev**. Migraciones 012/013 y API/UI básicas aplicadas; no desplegado.
> Este documento es el paso previo obligatorio del prompt de importación.

## 1. Implementación actual

### Modelo

`Work → Resource → File` ya existe en `Chorus/migrations/sqlite/001_v6_work_resource_file.sql`:

- `works`: obra canónica y `required_resource_id`.
- `resources`: versión/material asociado a la obra y `required_file_id`.
- `files`: fichero físico, `storage_pointer`, `sha256`, `size_bytes`, `status`.

`003_owner_and_library.sql` añade:

- `works.owner_sub`;
- `library_items` (`local_work` / `osap_reference`);
- `collections` y `collection_items`.

`creation_drafts` y `editor_source_tokens` cubren el flujo MuseEncore/borradores.

### Almacenamiento

- Ficheros privados en `settings.storage_root` (`var/private`), puntero relativo en `files.storage_pointer`.
- `_save_private()` guarda objetos planos con UUID; no hay jerarquía física.
- `_read_private()` valida que el puntero no salga del root.
- `sha256` se calcula para el editor MXL; no hay deduplicación general.
- Descarga actual: `/api/v1/library/{item_id}/download`, `/drafts/{id}/source-file`.

### Endpoints existentes

- `GET /api/v1/library`, `POST /api/v1/library/references`, `POST /api/v1/library/works/{id}`.
- `POST /api/v1/drafts`, `POST /api/v1/drafts/{id}/source`, `POST /api/v1/drafts/{id}/files`.
- `GET /api/v1/drafts/{id}/editor`, `GET /api/v1/editor-sources/{token}`.
- `GET /api/v1/works/{id}/integrity`.
- Catálogo OSAP vía `osap_call` y biblioteca de referencias.

## 2. Huecos frente al prompt

1. No existe jerarquía **obra / versión / parte o instrumento / fichero**.
2. No hay importación múltiple ni de carpetas.
3. No se conserva el nombre original ni se propone un nombre normalizado.
4. No hay clasificación automática de formato más allá de MXL.
5. No hay cola de revisión con estados.
6. No hay deduplicación por SHA-256 ni resolución de conflictos de nombre.
7. No hay publicación selectiva a miembros ni estados `en preparación / revisado / publicado / retirado`.
8. No hay asociación de material a partes configurables por agrupación.
9. No hay UI de biblioteca jerárquica ni de revisión.
10. No hay sincronización offline.

## 3. Diseño propuesto

### 3.1. Principio

No crear una segunda jerarquía ni una tabla por carpeta. La estructura se deriva del modelo existente:

```
Work
  └── Resource (versión/interpretación)
        └── File (fichero)
```

Campos nuevos mínimos:

- `resources.version_label` (p. ej. “Original”, “Arreglo coro mixto”).
- `resources.part_label` (p. ej. “Soprano”, “Director”, “Todas”).
- `resources.material_status` (`draft`, `reviewed`, `published`, `retired`).
- `files.folder_path` (ruta relativa dentro de la versión; p. ej. `Soprano`, `Director`).
- `files.display_name` (nombre visible; `Partitura.pdf`).
- `files.original_name`.
- `files.sha256` ya existe.

No se repite obra/versión/voz en `display_name`; ya están en `Work`/`Resource`/`folder_path`.

### 3.2. Ruta lógica

```
/repertorio/{work_id}/{version_label}/{part_label}/
```

Los nombres de fichero solo describen el contenido:

- `Partitura.pdf`
- `Partitura.mxl`
- `Partitura.mid`
- `Audio.mp3`
- `Partitura-completa.pdf`
- `Todas.mid`

Si el usuario cambia el nombre de una parte, cambia la carpeta, no el nombre del fichero.

### 3.3. Importación

`POST /api/v1/material/import` (multipart):

- `metadata`: JSON con `work_id` o `work_title`, `version_label`, `part_label`, `status`.
- `files[]`: uno o varios ficheros, con `relative_path` opcional para carpetas.

Pasos:

1. Validar extensión y contenido (MXL con `validate_mxl`, XML con comprobación de raíz MusicXML, audio por extensión/MIME).
2. Calcular SHA-256.
3. Detectar duplicado exacto por `sha256` y advertir; enlazar o pedir confirmación.
4. Resolver Work existente o crear uno nuevo con confirmación del usuario.
5. Resolver Resource por `work_id + version_label`; crear si no existe.
6. Proponer `display_name` según tipo y `folder_path` según parte.
7. Guardar en un área temporal; después mover a `storage_root`.
8. Insertar File/Resource de forma transaccional.
9. Devolver un resumen con avisos y estado de revisión.

No sobrescribir: si hay conflicto, proponer `Partitura-2.pdf` o `Partitura-revisada.pdf`.

### 3.4. Revisión y publicación

- La importación crea `material_status = draft`.
- El gestor revisa y cambia a `reviewed`.
- `published` solo lo ven miembros autorizados; `retired` conserva historial.
- El director mantiene acceso completo.
- Las asignaciones por parte/agrupación se toman de `group_members.section_id`/roles.

### 3.5. API prevista

Reutilizar:

- `_save_private`, `_read_private`, `validate_mxl`, `sha256`.
- `GET /library` y `POST /library/works/{id}` para el índice.

Nuevos:

- `POST /api/v1/material/import` (multipart y revisión).
- `GET /api/v1/material/tree?work_id=&group_id=`.
- `PATCH /api/v1/material/resources/{id}` (versión, parte, estado).
- `PATCH /api/v1/material/files/{id}` (nombre, carpeta, estado).
- `POST /api/v1/material/resources/{id}/publish`.
- `GET /api/v1/material/files/{id}/download` con permisos.

### 3.6. UI

- Árbol de biblioteca: obra → versión → parte → ficheros.
- Importador con arrastrar/soltar, selección de carpeta y revisión en tabla.
- Chips de estado y advertencias (duplicado, formato dudoso, nombre repetido).
- Panel de publicación para gestores.
- Vista móvil de una columna con navegación hacia atrás.

## 4. Tests previstos

- Importación individual y múltiple.
- Carpeta con rutas relativas.
- Formatos válidos/erróneos (PDF, XML, MXL, MIDI, audio).
- SHA-256 y duplicados.
- Conflicto de nombres.
- Error a mitad de guardado: no dejar recursos huérfanos.
- Permisos: miembro, gestor, admin.
- Integridad Work→Resource→File.
- Descarga y publicación selectiva.

## 5. Implementado en dev

- `GET /api/v1/material/tree` (biblioteca propia y material publicado de grupo).
- `POST /api/v1/material/import` con vista previa, carpetas, validación, SHA-256 y duplicados.
- `PATCH /api/v1/material/resources/{id}`, `POST .../publish` y `PATCH /api/v1/material/files/{id}`.
- Descarga autenticada con permisos de grupo/sección.
- `GET /api/v1/material/manifest?group_id=` para preparar la descarga offline con rutas, SHA-256 y revisión.
- UI en Biblioteca: árbol, previsualización, revisión, publicación y vista por grupo.
- Tests en `tests/test_material.py`.

## 6. Decisión pendiente antes de migrar

1. ¿La importación crea automáticamente Works nuevos o exige confirmación?
2. ¿La versión inicial se llama “Original” o se deja vacía hasta que el usuario la nombre?
3. ¿Los estados se aplican a Resource o a File? Propuesta: Resource para publicación; File para revisión individual.
4. ¿Se permite adjuntar imágenes/PDF auxiliares además de partituras/audio?
5. ¿La estructura de carpetas se refleja en disco o solo lógicamente? Propuesta: solo lógica, con punteros planos en almacenamiento privado.


