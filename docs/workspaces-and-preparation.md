# Espacios de trabajo y trabajos de preparación — Especificación técnica y funcional

**Versión:** 1.0 (Borrador consolidado)  
**Fecha:** 2026-11-21  
**Estado:** Especificación — pendiente de revisión y aprobación funcional  
**Compatibilidad:** Modelo de datos OSAP V6 (Work → Resource → File)

---

## 1. Alcance y propósito

Este documento define la especificación técnica y funcional para los **espacios de trabajo** y los **trabajos de preparación** en Chorus. Su objetivo es permitir que tanto un músico independiente como una agrupación musical puedan organizar, preparar y gestionar sus repertorios de forma simultánea y aislada, manteniendo la coherencia con el modelo de datos V6 de OSAP.

**Lo que cubre esta especificación:**
- Concepto y tipos de espacios (Personal, Grupo, Proyecto).
- Trabajo de preparación: definición, ciclo de vida, aislamiento y relación con bibliotecas y actuaciones.
- Correcciones técnicas obligatorias sobre el estado actual del repositorio (migración 035, library_items, integridad Work/Resource, políticas de borrado, conversión de espacio, migraciones idempotentes).
- Integración con OSAP V6 (Work → Resource → File).
- Modelo de permisos y jerarquía de roles.
- Experiencia de usuario y navegación.

**Lo que NO cubre (fuera de alcance):**
- Implementación de código, migraciones, esquemas, configuración de base de datos.
- Endpoints de API concretos (se referencian solo cuando son necesarios para ilustrar el diseño).
- Decisiones de UI/UX detalladas (flujos, pantallas, componentes).

---

## 2. Concepto de espacios de trabajo

### 2.1 Tipos de espacio

Chorus distingue **tres tipos de espacio**, cada uno con identidad propia y reglas de acceso:

| Tipo | Descripción | Propietario inicial | Casos de uso típicos |
|------|-------------|---------------------|----------------------|
| **Personal** | Espacio unipersonal, sin membresías ni invitaciones. | Usuario autenticado (owner_sub). | Músico independiente, preparación individual, estudio privado. |
| **Grupo** | Agrupación musical estable con membresías, roles y secciones. | Creador del grupo (manager). | Coro, orquesta, banda, ensemble estable. |
| **Proyecto** | Formación temporal para una actividad concreta (concierto, gira, grabación). | Creador del proyecto (manager). | Proyecto sinfónico puntual, ensemble para festival, grabación de álbum. |

### 2.2 Identidad de espacio (space_id)

**Situación comprobada en el repositorio actual:**  
La migración 035 define `preparation_works.group_id NOT NULL FK → groups(id)`. No existe tabla `spaces` ni columna `space_type`.

**Diseño propuesto:**  
Introducir una tabla **`spaces`** que actúe como entidad contenedora común para los tres tipos.

```sql
CREATE TABLE spaces (
    id            CHAR(32) PRIMARY KEY,           -- UUID hex
    space_type    ENUM('personal','group','project') NOT NULL,
    owner_sub     CHAR(36) NOT NULL,              -- UUID del propietario (osap-auth user_id)
    group_id      CHAR(32) NULL,                  -- FK a groups(id) SOLO para space_type='group'
    project_id    CHAR(32) NULL,                  -- FK a projects(id) SOLO para space_type='project'
    name          VARCHAR(160) NOT NULL,
    description   TEXT NULL,
    created_at    DATETIME(6) NOT NULL,
    updated_at    DATETIME(6) NOT NULL,
    CONSTRAINT chk_space_group CHECK (
        (space_type = 'group' AND group_id IS NOT NULL AND project_id IS NULL) OR
        (space_type = 'project' AND project_id IS NOT NULL AND group_id IS NULL) OR
        (space_type = 'personal' AND group_id IS NULL AND project_id IS NULL)
    ),
    CONSTRAINT fk_space_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT,
    CONSTRAINT fk_space_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE RESTRICT
);
```

**Reglas de identidad:**
- Cada espacio tiene un `space_id` único e inmutable.
- `space_type` determina qué tabla de detalle aplica (`groups`, `projects`, o ninguna para `personal`).
- **Espacio personal:** no requiere fila en `groups` ni `projects`. Su identidad vive exclusivamente en `spaces` con `space_type='personal'`.
- **Espacio grupo:** `group_id` apunta a `groups(id)`. La membresía y roles se gestionan en `group_members`.
- **Espacio proyecto:** `project_id` apunta a `projects(id)` (tabla a crear). Membresía y roles en `project_members` (análoga a `group_members`).

### 2.3 Relación preparation_works → spaces

**Corrección obligatoria (punto 4.1):**  
`preparation_works.group_id` **no** se vuelve nullable. En su lugar:

```sql
ALTER TABLE preparation_works
    DROP FOREIGN KEY fk_prepworks_group,
    DROP COLUMN group_id,
    ADD COLUMN space_id CHAR(32) NOT NULL AFTER id,
    ADD CONSTRAINT fk_prepworks_space FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE RESTRICT;
```

- `ON DELETE RESTRICT` evita borrar un espacio que tenga trabajos de preparación asociados.
- Cada trabajo pertenece a **exactamente un espacio**.
- La autorización se resuelve vía `spaces` + membresía/rol en la entidad subyacente (group/project) o `owner_sub` para personal.

### 2.4 Selección de espacio de trabajo (UX)

- **Un solo espacio:** no se muestra selector; el usuario entra directamente a su espacio.
- **Varios espacios:** selector visible en cabecera/navegación lateral con nombre y tipo (icono: 👤 Personal, 👥 Grupo, 📁 Proyecto).
- Cambio de espacio: recarga el contexto (trabajos, biblioteca, actuaciones) sin perder estado de navegación dentro del espacio.

### 2.5 No obligar a crear grupo ficticio

- Un usuario registrado tiene automáticamente un **espacio personal** creado al primer acceso (lazy initialization).
- Puede crear trabajos de preparación, usar su biblioteca personal y gestionar actuaciones **sin** crear grupo ni proyecto.
- La conversión a grupo/proyecto es una acción explícita y posterior (ver §6).

---

## 3. Trabajos de preparación

### 3.1 Definición

Un **trabajo de preparación** (preparation_work) es un contenedor lógico dentro de un espacio que agrupa una selección de obras con organización propia (órdenes, versiones, asignaciones de voces/instrumentos, estado de ensayo, notas) para un propósito concreto: un concierto, un programa, una audición, un estudio personal, etc.

### 3.2 Atributos principales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | CHAR(32) | PK UUID hex |
| `space_id` | CHAR(32) | FK → spaces(id), NOT NULL |
| `title` | VARCHAR(200) | Nombre del trabajo (ej. "Concierto Navidad 2026") |
| `description` | TEXT | Notas generales |
| `status` | ENUM | `draft` \| `active` \| `archived` \| `completed` |
| `sort_order` | INT | Orden de presentación en lista |
| `starts_at` / `ends_at` | DATETIME | Ventana temporal opcional (fechas de conciertos) |
| `created_by` | CHAR(36) | user_id del creador |
| `created_at` / `updated_at` | DATETIME(6) | Auditoría |

### 3.3 Aislamiento entre trabajos

- Cada trabajo tiene su **propia selección de elementos** (ver §3.4).
- Modificar un trabajo **no afecta** a otros trabajos del mismo espacio.
- Eliminar un trabajo elimina **solo sus elementos de preparación** (ver §4.4).
- La biblioteca (personal o compartida) **no se modifica** al añadir/quitar obras de un trabajo.

### 3.4 Elementos de un trabajo (preparation_work_items)

**Situación comprobada:**  
Migración 035 define `preparation_work_items` con `work_id`, `resource_id`, `voice_label`, `instrument`, `custom_title`, `sort_order`, `status`, `notes`.

**Diseño propuesto (corrección 4.3 — integridad Work/Resource):**

```sql
CREATE TABLE preparation_work_items (
    id                  CHAR(32) PRIMARY KEY,
    preparation_work_id CHAR(32) NOT NULL,
    work_id             CHAR(32) NOT NULL,        -- FK → works(id)  (obra canónica)
    resource_id         CHAR(32) NOT NULL,        -- FK → resources(id) (versión/arreglo)
    voice_label         VARCHAR(64) NULL,         -- Soprano, Tenor, Violín I, etc.
    instrument          VARCHAR(64) NULL,         -- Para partes instrumentales
    custom_title        VARCHAR(200) NULL,        -- Título personalizado para este trabajo
    sort_order          INT NOT NULL DEFAULT 0,
    status              ENUM('pending','rehearsing','ready','archived') NOT NULL DEFAULT 'pending',
    notes               TEXT NULL,
    created_at          DATETIME(6) NOT NULL,
    updated_at          DATETIME(6) NOT NULL,
    CONSTRAINT fk_pwi_prepwork FOREIGN KEY (preparation_work_id)
        REFERENCES preparation_works(id) ON DELETE CASCADE,
    CONSTRAINT fk_pwi_work FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE RESTRICT,
    CONSTRAINT fk_pwi_resource FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    -- Comprobación de coherencia Work → Resource:
    CONSTRAINT fk_pwi_work_resource FOREIGN KEY (work_id, resource_id)
        REFERENCES resources(work_id, id) ON DELETE RESTRICT
);
```

**Puntos clave:**
- `resource_id` **NOT NULL** — no se permite `NULL` como solución provisional.
- **FK compuesta `(work_id, resource_id) → resources(work_id, id)`** garantiza que la Resource pertenece a la Work indicada. Requiere índice único en `resources(work_id, id)` (ya existe en V6).
- `ON DELETE RESTRICT` en `work_id` y `resource_id` protege referencias existentes (ver §4.4).
- `voice_label` / `instrument` son metadatos de **asignación en este trabajo**, no propiedades de la Resource.

### 3.5 Distinción de conceptos (no confundir)

| Concepto | Tabla / Entidad | Propietario / Ámbito | Persistencia |
|----------|-----------------|----------------------|--------------|
| **Biblioteca personal** | `library_items` (owner_sub) | Usuario individual | Propia del usuario, no se comparte automáticamente |
| **Biblioteca compartida** | `group_library_items` (propuesta) / `project_library_items` | Grupo / Proyecto | Compartida entre miembros con permiso |
| **Elemento de preparación** | `preparation_work_items` | Trabajo de preparación (space) | Vinculado a Work/Resource existentes, no duplica archivos |
| **Actuación / Evento** | `events` + `event_groups` | Grupo / Proyecto / Personal | Concepto independiente, agenda/calendario |

**Regla:** Incorporar una obra a un trabajo **no** la añade a ninguna biblioteca. La biblioteca es explícita (acción del usuario "Guardar en mi biblioteca" / "Compartir con el grupo").

---

## 4. Correcciones técnicas obligatorias

### 4.1 preparation_works.group_id → space_id

**Estado actual (migración 035):**
```sql
CREATE TABLE preparation_works (
    id CHAR(32) PRIMARY KEY,
    group_id CHAR(32) NOT NULL,
    CONSTRAINT fk_prepworks_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    ...
);
```

**Problemas:**
- Obliga a que todo trabajo pertenezca a un `group` (excluye espacio personal/proyecto).
- `ON DELETE CASCADE` borra trabajos al borrar el grupo — inaceptable para conservación de historial.

**Solución (diseño propuesto):** Ver §2.3.  
- Nueva tabla `spaces` como contenedor común.
- `preparation_works.space_id NOT NULL FK → spaces(id) ON DELETE RESTRICT`.
- Migración: crear `spaces`, migrar datos existentes (un `space` por `group` actual con `space_type='group'`), recrear `preparation_works` con `space_id`, dropear `group_id`.

### 4.2 Biblioteca personal vs. compartida

**Situación comprobada:**  
`library_items` usa `owner_sub` → **biblioteca personal**. No existe tabla de biblioteca compartida.

**Diseño propuesto:**

| Biblioteca | Tabla | Clave de ámbito | Compartida |
|------------|-------|-----------------|------------|
| Personal | `library_items` | `owner_sub` (user_id) | No |
| Grupo | `group_library_items` (nueva) | `group_id` | Sí, miembros con permiso |
| Proyecto | `project_library_items` (nueva) | `project_id` | Sí, miembros con permiso |

**Reglas de conversión (§6):**
- Al convertir espacio personal → grupo/proyecto: **no** se copian/mueven `library_items` a la biblioteca compartida.
- El usuario decide qué obras compartir (acción explícita "Compartir con el grupo").
- La biblioteca personal sigue siendo privada y accesible desde cualquier espacio.

### 4.3 Integridad Work → Resource (FK compuesta)

**Estado actual:**  
`preparation_work_items` tiene `work_id` y `resource_id` con FK simples independientes. **No** se valida que la Resource pertenezca a la Work.

**Solución (diseño propuesto):** Ver §3.4.  
FK compuesta `(work_id, resource_id) REFERENCES resources(work_id, id)`.  
Requiere que `resources` tenga índice único en `(work_id, id)` — confirmar en esquema V6.

**Validación en aplicación (capa de servicio):**  
Antes de insertar/actualizar `preparation_work_items`, verificar:
```python
resource = conn.execute(
    "SELECT work_id FROM resources WHERE id = ?", (resource_id,)
).fetchone()
if not resource or resource["work_id"] != work_id:
    raise ValueError("La resource no pertenece a la work indicada")
```
La FK compuesta en BD es la garantía final.

### 4.4 Política de borrado

| Entidad | Acción de borrado | Efecto en referencias |
|---------|-------------------|----------------------|
| **Work** (canónica) | `DELETE FROM works WHERE id = ?` | **RESTRICT** si existe `preparation_work_items.work_id` o `resources.work_id`. No se borra silenciosamente. |
| **Resource** | `DELETE FROM resources WHERE id = ?` | **RESTRICT** si existe `preparation_work_items.resource_id` o `files.resource_id`. |
| **File** | `DELETE FROM files WHERE id = ?` | **RESTRICT** si existe `preparation_work_files.file_id` (ver abajo). |
| **PreparationWork** | `DELETE FROM preparation_works WHERE id = ?` | **CASCADE** → elimina sus `preparation_work_items` y `preparation_work_files`. **No** toca Works/Resources/Files compartidos. |
| **PreparationWorkItem** | `DELETE FROM preparation_work_items WHERE id = ?` | Elimina solo la fila. No afecta Work/Resource/File. |

**Archivos adjuntos a un trabajo (propuesta):**
```sql
CREATE TABLE preparation_work_files (
    id                  CHAR(32) PRIMARY KEY,
    preparation_work_id CHAR(32) NOT NULL,
    file_id             CHAR(32) NOT NULL,        -- FK → files(id)
    purpose             ENUM('score','audio','video','other') NOT NULL,
    sort_order          INT NOT NULL DEFAULT 0,
    created_at          DATETIME(6) NOT NULL,
    CONSTRAINT fk_pwf_prepwork FOREIGN KEY (preparation_work_id)
        REFERENCES preparation_works(id) ON DELETE CASCADE,
    CONSTRAINT fk_pwf_file FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE RESTRICT
);
```
- `ON DELETE RESTRICT` en `file_id`: un File compartido no se borra al eliminar el trabajo.
- El borrado de un trabajo elimina solo la **referencia** en `preparation_work_files`.

### 4.5 Conversión de espacio personal a proyecto o grupo

**Operación:** Transacción atómica que ejecuta:

1. **Crear entidad destino:**
   - Grupo: `INSERT INTO groups (...) VALUES (...)` → `group_id`.
   - Proyecto: `INSERT INTO projects (...) VALUES (...)` → `project_id` (tabla `projects` a crear, análoga a `groups` pero sin jerarquía de secciones fija).

2. **Crear/actualizar space:**
   - `UPDATE spaces SET space_type='group', group_id=? WHERE id=? AND space_type='personal'`
   - O `space_type='project', project_id=?`.

3. **Membresía del propietario:**
   - Grupo: `INSERT INTO group_members (id, group_id, user_sub, role, status, granted_by, joined_at, updated_at) VALUES (..., 'manager', 'active', owner_sub, ...)`
   - Proyecto: `INSERT INTO project_members (..., 'manager', 'active', owner_sub, ...)`.

4. **Permisos iniciales:**
   - Propietario = `manager` (control total).
   - Roles musicales por defecto: ninguno (se crean bajo demanda).

5. **Bibliotecas:**
   - **No** migrar `library_items` → `group_library_items`.
   - Crear `group_library_items` vacía.
   - Acción explícita posterior: "Compartir selección con el grupo".

6. **Configuración:**
   - Heredar nombre/descripción del espacio personal.
   - Zona horaria, localidad, etc. desde perfil del usuario o defaults.

**Rollback:** Si cualquier paso falla, transacción completa se revierte. No quedan estados intermedios.

### 4.6 Migraciones idempotentes y recuperables

**Requisitos:**
- Cada migración debe poder ejecutarse múltiples veces sin error.
- Debe detectar estado parcial (tabla creada pero índices no, FK creada pero columnas no, etc.) y completarlo.
- No basta con `CREATE TABLE IF NOT EXISTS`.

**Patrón recomendado (MySQL/MariaDB 10.4):**

```sql
-- 1. Verificar existencia de tabla
CREATE TABLE IF NOT EXISTS spaces (...);

-- 2. Verificar y añadir columnas faltantes (una por ALTER TABLE)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spaces' AND COLUMN_NAME = 'project_id');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE spaces ADD COLUMN project_id CHAR(32) NULL AFTER group_id',
    'SELECT "Column project_id already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. Verificar y crear índices
SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spaces' AND INDEX_NAME = 'idx_spaces_owner');
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_spaces_owner ON spaces(owner_sub)',
    'SELECT "Index idx_spaces_owner already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4. Verificar y crear FK (requiere comprobar que no existe ya)
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_NAME = 'fk_spaces_group');
SET @sql = IF(@fk_exists = 0,
    'ALTER TABLE spaces ADD CONSTRAINT fk_spaces_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT',
    'SELECT "FK fk_spaces_group already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 5. Migrar datos existentes (idempotente: INSERT IGNORE o ON DUPLICATE KEY UPDATE)
INSERT IGNORE INTO spaces (id, space_type, owner_sub, group_id, name, created_at, updated_at)
SELECT g.id, 'group', g.owner_sub, g.id, g.name, g.created_at, g.updated_at
FROM groups g
LEFT JOIN spaces s ON s.group_id = g.id AND s.space_type = 'group'
WHERE s.id IS NULL;

-- 6. Actualizar preparation_works (añadir space_id, migrar, dropear group_id)
--    Requiere pasos intermedios con columna nullable, UPDATE, luego ALTER NOT NULL + FK.
```

**Detección de estado parcial:**  
Consultar `INFORMATION_SCHEMA` antes de cada operación. Registrar en `chorus_schema_migrations` solo cuando **todos** los pasos de la migración han completado con éxito.

---

## 5. Integración obligatoria con OSAP V6

### 5.1 Modelo Work → Resource → File

**Situación comprobada:**  
OSAP V6 define:
- `works` — obra canónica (metadatos, compositor, título, etc.).
- `resources` — interpretación/arreglo/versión para un propósito (`work_id` FK).
- `files` — archivo físico o referencia de almacenamiento (`resource_id` FK, `storage_path`, `sha256`, `mime_type`).

**Regla de diseño:**  
Los trabajos de preparación **referencian** Works y Resources existentes. **No** crean Works/Resources/Files paralelos.

### 5.2 Incorporación de obras a un trabajo

**Flujo:**
1. Usuario busca/selecciona una **Work** (desde biblioteca personal, compartida, o catálogo OSAP).
2. Usuario elige una **Resource** de esa Work (partitura, arreglo, pista de ensayo).
3. Sistema valida: `resource.work_id == work_id` (FK compuesta en BD + validación en servicio).
4. Se crea `preparation_work_item` con `(preparation_work_id, work_id, resource_id, voice_label, ...)`.
5. Opcionalmente, se asocian **Files** de esa Resource al trabajo vía `preparation_work_files` (referencia, no copia).

**Permisos:**
- Usuario debe tener **lectura** sobre la Work y la Resource (visibilidad en biblioteca personal, compartida, o catálogo público).
- No se requiere permiso de escritura sobre Work/Resource para añadirlas a un trabajo propio.

### 5.3 No duplicar archivos ni alterar almacenamiento externo

- `preparation_work_files.file_id` referencia `files(id)` existente.
- El archivo físico sigue en su ubicación original (storage_path, bucket, etc.).
- Chorus solo gestiona la **relación** trabajo↔file.
- Borrar un trabajo elimina la fila en `preparation_work_files`, **no** el File ni el blob de almacenamiento.

### 5.4 files.resource_id = NULL — prohibido

**Diseño propuesto:**  
`files.resource_id` sigue siendo **NOT NULL** en esquema V6.  
No se permite `NULL` como solución provisional para "archivos sueltos de preparación".  
Si un usuario sube un PDF suelto para un trabajo:
1. Se crea Work mínimo (título, tipo "preparation_asset").
2. Se crea Resource vinculada a ese Work.
3. Se crea File vinculado a la Resource.
4. Se referencia en `preparation_work_files`.

Esto mantiene la integridad del modelo V6 y evita archivos huérfanos.

---

## 6. Permisos y jerarquía

### 6.1 Estado actual

- `group_roles` tiene `parent_id` (jerarquía de roles).
- Permisos actuales **no recorren** la jerarquía: un rol "Jefe de sección" hijo de "Director musical" no hereda permisos automáticamente.
- Tabla `group_members` tiene `admin_role_id`, `musical_role_id`, `section_id`.

### 6.2 Diseño propuesto: autorización basada en capacidades (capabilities)

**Concepto:**  
Cada rol (`group_roles`, `project_roles`) declara un conjunto de **capabilities** (cadenas). La autorización verifica si el usuario (vía sus roles y jerarquía) posee la capability requerida.

**Estructura de capabilities (ejemplo):**
```
preparation_work:create
preparation_work:read
preparation_work:update
preparation_work:delete
preparation_work:manage_files
preparation_work:assign_voices
library_personal:read
library_personal:write
library_shared:read
library_shared:write
library_shared:manage
member:invite
member:remove
member:manage_roles
section:manage
event:create
event:manage
space:convert_personal_to_group
space:convert_personal_to_project
```

**Resolución de capacidades (algoritmo):**
1. Obtener roles activos del usuario en el espacio (`group_members` + `group_roles` vía `admin_role_id`/`musical_role_id`).
2. Para cada rol, recorrer `parent_id` recursivamente (hasta raíz) y acumular `capabilities` (columna JSON en `group_roles`).
3. Unificar (UNION) todas las capabilities.
4. Verificar `required_capability IN user_capabilities`.

**Jerarquía de prevalencia:**
- Capabilities de rol **admin** (ámbito espacio) > capabilities de rol **musical** (ámbito sección/voz).
- Dentro del mismo ámbito, rol más específico (hijo en jerarquía) prevalece sobre padre para restricciones, pero hereda permisos.
- `section_id` en `group_members` acota capacidades de tipo `section:*` a esa sección.

**Extensibilidad:**  
Nuevas responsabilidades (ej. "Jefe de archivo", "Coordinador de logística") = nuevo rol con sus capabilities. **No** requiere cambio de esquema ni código de autorización central.

### 6.3 Permisos por tipo de espacio

| Capability | Personal | Grupo | Proyecto |
|------------|----------|-------|----------|
| preparation_work:* | Owner (siempre) | Manager + Musical Director + Section Lead (según capabilities) | Manager + Project Lead |
| library_personal:* | Owner | Owner (solo su propia) | Owner (solo su propia) |
| library_shared:* | — | Manager + Library Manager | Manager + Library Manager |
| member:* | — | Manager | Manager |
| space:convert_* | Owner | — | — |

---

## 7. Interfaz y experiencia de usuario

### 7.1 Navegación principal (vista espacio)

```
[Selector de espacio: 👤 Personal | 👥 Coral Aurora | 📁 Proyecto Navidad]
├── Trabajos de preparación
│   ├── 🎵 Concierto Navidad 2026 (activo)
│   │   ├── Obras (lista con voice_label, status, notas)
│   │   ├── Archivos adjuntos
│   │   └── Acciones: editar, duplicar, archivar, exportar programa
│   ├── 🎵 Audición Tenor (borrador)
│   └── [+ Nuevo trabajo]
├── Biblioteca
│   ├── 📚 Personal (mis obras, mis archivos)
│   ├── 📚 Compartida (grupo/proyecto) — solo si space_type != personal
│   └── [+ Añadir desde catálogo OSAP]
├── Actuaciones y agenda
│   ├── Próximos eventos
│   ├── Historial
│   └── [+ Nuevo evento personal / de grupo]
└── Configuración del espacio
    ├── Miembros y roles (solo grupo/proyecto)
    ├── Roles y capabilities
    ├── Secciones (grupo)
    └── Convertir a grupo / proyecto (solo personal)
```

### 7.2 Principios de UX

- **Cero fricción para músico independiente:** al registrarse, tiene espacio personal listo. Crea trabajo → añade obras → ensaya. Sin invitaciones, sin códigos, sin roles.
- **Escalabilidad natural:** cuando necesita colaborar, "Convertir a grupo" invita a miembros y crea biblioteca compartida. Sus datos personales no se mezclan.
- **Aislamiento visual:** cada trabajo muestra solo sus obras, sus archivos, su estado. No hay "fugas" entre trabajos.
- **Actuaciones independientes:** un evento de agenda no requiere trabajo de preparación. Puede crearse directamente. Si existe trabajo relacionado, se vincula opcionalmente (UI: "Vincular a trabajo de preparación").

### 7.3 Estados de trabajo y acciones

| Estado | Descripción | Acciones permitidas |
|--------|-------------|---------------------|
| `draft` | Borrador, solo visible para creador y managers | Editar, añadir/quitar obras, cambiar estado a `active` |
| `active` | En ensayo activo, visible para miembros con permiso `read` | Editar (restringido), actualizar status items, añadir notas, adjuntar archivos |
| `archived` | Completado, solo lectura | Consultar, duplicar, restaurar a `active` |
| `completed` | Cerrado definitivamente (concierto realizado) | Solo consulta, exportar programa |

---

## 8. Esquema de base de datos — Resumen de tablas propuestas

### 8.1 Tablas nuevas / modificadas

| Tabla | Estado | Propósito |
|-------|--------|-----------|
| `spaces` | **Nueva** | Contenedor común Personal/Grupo/Proyecto |
| `projects` | **Nueva** | Entidad detalle para espacio tipo proyecto (análoga a `groups`) |
| `project_members` | **Nueva** | Membresías de proyecto (análoga a `group_members`) |
| `project_roles` | **Nueva** | Roles de proyecto con capabilities JSON |
| `group_library_items` | **Nueva** | Biblioteca compartida de grupo |
| `project_library_items` | **Nueva** | Biblioteca compartida de proyecto |
| `preparation_works` | **Modificada** | `group_id` → `space_id` FK → spaces |
| `preparation_work_items` | **Modificada** | FK compuesta `(work_id, resource_id)` → resources |
| `preparation_work_files` | **Nueva** | Archivos referenciados en un trabajo |
| `group_roles` | **Modificada** | Añadir columna `capabilities JSON` |
| `project_roles` | **Nueva** | Con `capabilities JSON` |

### 8.2 Columnas clave (resumen)

```sql
-- spaces
id CHAR(32) PK
space_type ENUM('personal','group','project') NOT NULL
owner_sub CHAR(36) NOT NULL
group_id CHAR(32) NULL FK→groups
project_id CHAR(32) NULL FK→projects
name VARCHAR(160) NOT NULL
created_at/updated_at DATETIME(6)

-- preparation_works (cambio)
space_id CHAR(32) NOT NULL FK→spaces ON DELETE RESTRICT
-- DROP group_id

-- preparation_work_items (cambio)
CONSTRAINT fk_pwi_work_resource FOREIGN KEY (work_id, resource_id)
    REFERENCES resources(work_id, id) ON DELETE RESTRICT

-- group_roles / project_roles
capabilities JSON NOT NULL DEFAULT '[]'  -- array de strings
parent_id CHAR(32) NULL FK→mismo tabla (jerarquía)
```

---

## 9. Decisiones de diseño consolidadas

1. **Tabla `spaces` como entidad unificadora** — evita `group_id` nullable y da identidad propia a espacio personal.
2. **`preparation_works.space_id` NOT NULL FK → spaces ON DELETE RESTRICT** — protege trabajos al borrar espacio.
3. **Bibliotecas separadas** — personal (`library_items`), grupo (`group_library_items`), proyecto (`project_library_items`). No migración automática al convertir.
4. **FK compuesta Work+Resource en preparation_work_items** — garantiza coherencia V6.
5. **Política de borrado RESTRICT para Works/Resources/Files** — no borrado silencioso en cascada.
6. **Conversión personal→grupo/proyecto = transacción atómica** — crea entidad, membership manager, space update, bibliotecas vacías.
7. **Migraciones idempotentes con checks INFORMATION_SCHEMA** — no solo `IF NOT EXISTS`.
8. **Integración V6 estricta** — Work→Resource→File, sin duplicados, sin `files.resource_id=NULL`.
9. **Permisos por capabilities + jerarquía recursiva** — extensible sin cambiar esquema.
10. **UX: selector de espacio solo si >1; espacio personal por defecto al registro.**

---

## 10. Cambios respecto al documento original (placeholder)

- Documento completo reescrito desde cero (el original era `__PLACEHOLDER__`).
- Incorporadas todas las correcciones técnicas obligatorias (puntos 4.1–4.6).
- Definido modelo de espacios de tres tipos con tabla `spaces`.
- Especificada integridad Work/Resource mediante FK compuesta.
- Definida política de borrado protectora.
- Diseñada conversión transaccional de espacio personal.
- Establecido patrón de migraciones idempotentes reales.
- Integrado modelo V6 sin duplicación.
- Diseñado sistema de permisos por capabilities con recorrido de jerarquía.
- Descrita navegación y principios de UX.

---

## 11. Cuestiones que siguen necesitando decisión funcional

| Tema | Pregunta | Impacto |
|------|----------|---------|
| **Tabla `projects`** | ¿Se crea tabla `projects` independiente o se reutiliza `groups` con `type_code='project'`? | Esquema, migraciones, código de membresía. |
| **Capabilities por defecto** | ¿Qué capabilities vienen predefinidas en roles estándar (manager, director_musical, jefe_seccion, miembro)? | Semilla de datos, UI de roles. |
| **Notificaciones en trabajos** | ¿Notificar a miembros asignados (voice_label) cuando cambian ítems/archivos? | Tabla `notifications`, preferencias por usuario. |
| **Exportar programa** | Formato(s) de exportación: PDF, MusicXML, CSV, JSON? | Servicios de generación, plantillas. |
| **Duplicar trabajo** | ¿Copiar solo ítems o también archivos referenciados? ¿Mantener links a mismos Files? | Lógica de duplicado, UX. |
| **Límites de almacenamiento** | ¿Cuota por espacio/usuario para `preparation_work_files`? | Políticas, monitoring. |
| **Búsqueda global** | ¿Buscar en trabajos de preparación de todos los espacios del usuario? | Índices, permisos de visibilidad. |
| **Versionado de trabajos** | ¿Historial de cambios en preparation_work_items (auditoría fina)? | Tabla `preparation_work_item_history`, triggers. |

---

## 12. Propuesta de orden de implementación

| Fase | Entregable | Dependencias |
|------|------------|--------------|
| **0** | Migración idempotente: crear `spaces`, migrar `groups` existentes → spaces tipo group, alterar `preparation_works` (space_id), dropear group_id. | Esquema V6 estable. |
| **1** | Tablas `projects`, `project_members`, `project_roles`, `group_library_items`, `project_library_items`, `preparation_work_files`. | Fase 0. |
| **2** | FK compuesta en `preparation_work_items` + migración de datos (validar coherencia existente). | Fase 1. |
| **3** | Capabilities en `group_roles`/`project_roles` + servicio de resolución recursiva. | Fase 1. |
| **4** | Endpoints CRUD spaces, conversión personal→grupo/proyecto (transacción). | Fases 0-1. |
| **5** | Endpoints CRUD preparation_works + items + files (con validación Work/Resource). | Fases 0-2. |
| **6** | Biblioteca compartida: endpoints CRUD `group_library_items`, acción "Compartir con grupo". | Fase 1. |
| **7** | UI: selector de espacio, navegación por espacio, trabajos, biblioteca, actuaciones. | Fases 4-6. |
| **8** | Permisos por capabilities en endpoints existentes (agenda, artículos, mensajes, roles). | Fase 3. |
| **9** | Tests de integración: aislamiento trabajos, conversión espacio, integridad FK compuesta, borrado RESTRICT. | Fases 0-8. |

---

## 13. Riesgos técnicos a verificar antes de implementar

| Riesgo | Verificación necesaria |
|--------|------------------------|
| **FK compuesta `resources(work_id, id)`** | Confirmar que `resources` tiene índice único en `(work_id, id)` en esquema V6 actual. Sin él, la FK no se puede crear. |
| **Migración de `preparation_works` existente** | Verificar que todos los `group_id` actuales tienen `groups` correspondientes y pueden mapearse a `spaces` 1:1. |
| **Datos huérfanos en `preparation_work_items`** | Ejecutar query de validación: `SELECT * FROM preparation_work_items pwi LEFT JOIN resources r ON r.id=pwi.resource_id AND r.work_id=pwi.work_id WHERE r.id IS NULL` — debe devolver 0 filas antes de crear FK compuesta. |
| **Rendimiento resolución capabilities** | Probar recursividad en `group_roles.parent_id` con profundidad >5; considerar materialized path o closure table si es cuello de botella. |
| **Transacción conversión espacio** | Verificar aislamiento (REPEATABLE READ) y tiempo de bloqueo en tablas `groups`/`spaces`/`group_members`. |
| **Idempotencia migraciones en CI/CD** | Ejecutar script de migración 2× seguidas en BD limpia y en BD con estado parcial; confirmar que no falla y estado final es idéntico. |
| **Compatibilidad OSAP V6** | Confirmar que `works`, `resources`, `files` no cambian esquema en V6 próximamente. |
| **Índices para consultas frecuentes** | `preparation_works(space_id, status)`, `preparation_work_items(preparation_work_id, sort_order)`, `spaces(owner_sub, space_type)`. |

---

## 14. Distinción expresa: Situación comprobada vs. Diseño propuesto vs. No verificado

| Área | Situación comprobada en repositorio actual | Diseño propuesto | No verificado / Pendiente |
|------|--------------------------------------------|------------------|---------------------------|
| `preparation_works` | Existe con `group_id NOT NULL FK→groups ON DELETE CASCADE` (mig 035) | `space_id NOT NULL FK→spaces ON DELETE RESTRICT` | Script de migración real |
| `spaces` | **No existe** | Nueva tabla unificadora | — |
| `projects` / `project_members` / `project_roles` | **No existen** | Tablas nuevas análogas a groups | Definición exacta de columnas |
| `library_items` | Existe con `owner_sub` (biblioteca personal) | Se mantiene; añadir `group_library_items`, `project_library_items` | Esquema exacto de compartidas |
| `preparation_work_items` | Existe con `work_id`, `resource_id` FK simples | FK compuesta `(work_id, resource_id)→resources(work_id,id)` | Índice único en `resources(work_id,id)` |
| `group_roles.capabilities` | **No existe** | Columna `JSON NOT NULL DEFAULT '[]'` | Lista canónica de capabilities |
| Migraciones idempotentes | Solo `CREATE TABLE IF NOT EXISTS` | Checks `INFORMATION_SCHEMA` + pasos condicionales | Scripts completos |
| Conversión personal→grupo | **No implementada** | Transacción atómica (6 pasos) | Pruebas de rollback |
| Permisos jerárquicos | `parent_id` existe pero **no se recorre** | Resolución recursiva + capabilities | Algoritmo exacto en código |

---

**Fin del documento**