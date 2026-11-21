# Chorus — Arquitectura definitiva de espacios de trabajo y preparación

**Versión:** 1.0 (Documento consolidado)  
**Fecha:** 2026-11-21  
**Basado en:** Especificación funcional v1.0 + Auditoría técnica v1.0 + Revisión crítica del código  
**Estado:** Arquitectura definitiva — lista para implementación

---

## 1. Resumen ejecutivo

### 1.1 Objetivo

Definir la arquitectura técnica definitiva para los **espacios de trabajo** y **trabajos de preparación** en Chorus, que permita a un músico independiente y a una agrupación musical organizar sus repertorios de forma simultánea y aislada, manteniendo coherencia con el modelo V6 de OSAP.

### 1.2 Principios rectores

1. **Un usuario independiente puede trabajar sin crear grupo ficticio** — espacio personal por defecto.
2. **Cada usuario tiene al menos un espacio personal** — creado automáticamente al registro.
3. **Un grupo puede tener múltiples trabajos de preparación independientes** — cada uno con su propia selección de obras.
4. **Los proyectos son espacios temporales con identidad propia** — no confundir con grupos estables.
5. **Un trabajo pertenece a un único espacio** — relación 1:N espacio→trabajos.
6. **Selección de Resource debe pertenecer al Work indicado** — integridad referencial estricta.
7. **Incorporar obra a trabajo NO la añade a biblioteca** — son conceptos separados.
8. **Bibliotecas personales y compartidas son independientes** — no se mezclan automáticamente.
9. **Conversión personal→grupo/proyecto es transaccional** — sin pérdidas ni copias innecesarias.
10. **Permisos distinguen responsabilidades administrativas y musicales** — jerarquía clara.
11. **Admins OSAP gestionan sin ser miembros** — vía contratos API.
12. **Gestor de grupo no obtiene privilegios globales** — aislamiento estricto.

### 1.3 Decisión arquitectónica principal

**Se adopta la Alternativa B: `spaces` como entidad unificadora, reutilizando `groups` como entidad de pertenencia colectiva.**

- `spaces` es la entidad contenedora común para Personal/Grupo/Proyecto.
- `groups` se mantiene para grupos estables (membresías, roles, secciones).
- `projects` se implementa como extensión de `groups` con `type_code='project'` (no tabla separada inicialmente).
- Esto minimiza cambios, reutiliza infraestructura existente y permite evolución futura.

---

## 2. Inventario real actualizado

### 2.1 Tablas existentes (verificadas)

| Tabla | Columnas clave | FKs | Estado |
|-------|----------------|-----|--------|
| `groups` | id, name, entity_id, created_by, join_code, kind, **type_code** (NUEVO) | — | ✅ Existe |
| `group_members` | id, group_id FK→groups, user_sub, role, **admin_role_id** FK→group_roles, **musical_role_id** FK→group_roles, **section_id**, **granted_by** | group_id, admin_role_id, musical_role_id | ✅ Existe |
| `group_roles` | id, group_id FK→groups, scope, code, name, **parent_id** FK→group_roles (self), active | group_id, parent_id | ✅ Existe |
| `library_items` | id, **owner_sub**, kind, work_id FK→works, title, metadata_json | work_id | ✅ Existe |
| `events` | id, **group_id NULLABLE**, entity_id, scope, kind, title, starts_at | group_id | ✅ Existe (soporta personales) |
| `works` | id, title, **required_resource_id**, owner_sub | — | ✅ Existe |
| `resources` | id, **work_id FK→works**, resource_type, required_file_id, **UNIQUE(work_id, id)** | work_id | ✅ Existe |
| `files` | id, **resource_id FK→resources**, name, storage_pointer, sha256 | resource_id | ✅ Existe |
| `preparation_works` | id, **group_id FK→groups NOT NULL**, title, folder_path, status | **group_id** | ⚠️ Existe pero problemático |
| `preparation_work_items` | — | — | ❌ **NO EXISTE** |
| `preparation_work_files` | — | — | ❌ **NO EXISTE** |
| `spaces` | — | — | ❌ **NO EXISTE** |

### 2.2 Endpoints existentes (verificados en main.py)

| Endpoint | Método | Función | Estado |
|----------|--------|---------|--------|
| `/api/v1/auth/me` | GET/PATCH | Perfil usuario | ✅ Proxy osap-auth |
| `/api/v1/library` | GET | Lista biblioteca personal | ✅ owner_sub |
| `/api/v1/library/works/{work_id}` | POST | Añadir work local | ✅ |
| `/api/v1/groups` | POST | Crear grupo | ✅ |
| `/api/v1/groups/join` | POST | Unirse por código | ✅ |
| `/api/v1/groups/{id}/members` | GET/POST | Miembros | ✅ |
| `/api/v1/groups/{id}/members/{user_sub}` | PATCH/DELETE | Gestionar miembro | ✅ |
| `/api/v1/groups/{id}/preparation-works` | GET/POST | Trabajos preparación | ✅ (requiere group_id) |
| `/api/v1/groups/{id}/preparation-works/{id}` | GET/PATCH/DELETE | CRUD individual | ✅ |
| `/api/v1/groups/{id}/preparation-works/{id}/files` | POST/GET | Archivos | ✅ (storage privado) |

### 2.3 Endpoints ausentes

| Funcionalidad | Estado |
|---------------|--------|
| CRUD `spaces` | ❌ No existe |
| Conversión personal→grupo/proyecto | ❌ No existe |
| `preparation_work_items` (items con Work/Resource) | ❌ No existe tabla ni endpoints |
| FK compuesta Work+Resource en preparation | ❌ No existe |
| Biblioteca compartida (`group_library_items`) | ❌ No existe |
| Capabilities por rol | ❌ No existe |
| Herencia recursiva de roles | ❌ `parent_id` existe pero no se usa |

---

## 3. Matriz de cumplimiento de la especificación

| # | Requisito especificación | Estado | Evidencia |
|---|--------------------------|--------|-----------|
| **1** | Espacios de trabajo (Personal/Grupo/Proyecto) | ❌ **No cumple** | No existe `spaces`. Solo `groups`. |
| 1.1 | Tabla `spaces` unificadora | ❌ No cumple | No existe |
| 1.2 | `preparation_works.space_id` FK→spaces | ❌ No cumple | `preparation_works.group_id FK→groups NOT NULL` |
| 1.3 | Selector de espacio UX | ❌ No cumple | No hay concepto de espacio |
| 1.4 | Espacio personal por defecto | ❌ No cumple | Obliga a crear grupo |
| **2** | Trabajos de preparación por espacio | ⚠️ **Parcial** | Existe pero ligado a group_id |
| 2.1 | Un trabajo = un espacio | ❌ No cumple | Pertenece a group_id |
| 2.2 | Dos trabajos independientes mismo espacio | ✅ Cumple | Funciona (mismo group_id, distinto work_id) |
| 2.3 | Modificar trabajo no modifica biblioteca | ✅ Cumple | No hay relación auto |
| 2.4 | Eliminar trabajo no elimina Works/Resources | ⚠️ Parcial | CASCADE en preparation_works; Files en storage privado no referenciados |
| 2.5 | Work y Resource corresponden | ❌ No cumple | No hay `preparation_work_items` con FK compuesta |
| **3** | Integridad OSAP V6 (Work→Resource→File) | ⚠️ **Parcial** | Tablas V6 existen; sin validación en preparation |
| 3.1 | FK compuesta `(work_id, resource_id)` en preparation_work_items | ❌ No cumple | Tabla no existe |
| 3.2 | `resources(work_id, id)` índice único | ✅ Cumple | `uq_resources_work` en 001_schema.sql |
| 3.3 | `files.resource_id` NOT NULL | ✅ Cumple | `resource_id VARCHAR(191) NOT NULL` |
| 3.4 | No duplicar archivos físicos | ⚠️ Parcial | Preparation files van a storage privado separado |
| 3.5 | `files.resource_id = NULL` prohibido | ✅ Cumple | No se permite NULL |
| **4** | Biblioteca personal vs compartida | ⚠️ **Parcial** | Solo personal (`library_items` con `owner_sub`) |
| 4.1 | Biblioteca personal (owner_sub) | ✅ Cumple | `library_items.owner_sub` |
| 4.2 | Biblioteca compartida grupo/proyecto | ❌ No cumple | No existe `group_library_items` |
| 4.3 | Incorporar a trabajo no añade a biblioteca | ✅ Cumple | No hay relación automática |
| 4.4 | Conversión personal→grupo no copia biblioteca | ❌ No cumple | No existe conversión |
| **5** | Permisos y jerarquía | ⚠️ **Parcial** | Roles existen, jerarquía definida pero no usada |
| 5.1 | `group_roles.parent_id` para jerarquía | ✅ Existe | Migración 029 |
| 5.2 | Recorrido recursivo para herencia | ❌ No cumple | Solo se usa para validar borrado |
| 5.3 | Permisos por capabilities | ❌ No cumple | Roles hardcodeados |
| 5.4 | Restricción por sección (`section_id`) | ⚠️ Parcial | `section_id` existe pero no se usa en preparation |
| 5.5 | Director musical gestiona preparation | ✅ Cumple | `_can_manage_preparation_work` verifica code='director' |
| **6** | Conversión personal→grupo/proyecto | ❌ **No cumple** | No existe endpoint ni lógica |
| **7** | Migraciones idempotentes | ⚠️ **Parcial** | Solo `CREATE TABLE IF NOT EXISTS` |
| **8** | Navegación y UX por espacio | ❌ **No cumple** | No hay concepto de espacio |

---

## 4. Hallazgos de auditoría: confirmados, corregidos o descartados

### 4.1 Confirmados

| Hallazgo | Estado | Confirmación |
|----------|--------|--------------|
| D-01: `preparation_works.group_id NOT NULL` impide espacio personal | ✅ Confirmado | Migración 035 línea 4: `group_id VARCHAR(191) NOT NULL` |
| D-02: `ON DELETE CASCADE` borra trabajos al eliminar grupo | ✅ Confirmado | Migración 035 línea 16: `ON DELETE CASCADE` |
| D-03: No existe `preparation_work_items` | ✅ Confirmado | No aparece en migraciones ni código |
| D-05: No existe conversión personal→grupo | ✅ Confirmado | No hay endpoint ni función |
| D-06: No existe biblioteca compartida | ✅ Confirmado | Solo `library_items` con `owner_sub` |
| D-07: Permisos no recorren jerarquía | ✅ Confirmado | `parent_id` solo se usa en DELETE role (línea 2543 main.py) |

### 4.2 Corregidos

| Hallazgo auditoría | Corrección | Razón |
|--------------------|------------|-------|
| D-04: FK compuesta Work+Resource | **Corregido**: Sí es viable y necesaria | `resources` tiene `UNIQUE KEY uq_resources_work (work_id, id)` — permite FK compuesta |
| D-08: `files.resource_id` permite NULL | **Corregido**: No permite NULL | Esquema V6: `resource_id VARCHAR(191) NOT NULL` — cumple |
| D-09: Preparation files usan storage privado | **Corregido**: Decisión de diseño, no defecto | Storage privado es aceptable si se referencia en BD; no es duplicación |
| D-10: Roles hardcodeados | **Corregido**: No es defecto crítico | Hardcode inicial es aceptable; capabilities pueden añadirse después |
| D-11: Migración 035 no idempotente | **Corregido**: Parcialmente idempotente | Usa `CREATE TABLE IF NOT EXISTS` — aceptable para tabla nueva |
| D-12: `events.group_id` NULLABLE | **Corregido**: Es diseño correcto | Permite eventos personales sin grupo — cumple especificación |

### 4.3 Descartados

| Hallazgo auditoría | Razón de descarte |
|--------------------|-------------------|
| D-13: No hay validación Work→Resource | No aplica — no existe `preparation_work_items` aún; será requisito de diseño |
| D-14: Preferencias notificación no usadas | No es defecto bloqueante; puede implementarse después |
| D-15: `group_roles.parent_id` no usado | Confirmado pero no crítico para MVP |

### 4.4 Inconsistencias de la auditoría anterior corregidas

| Inconsistencia | Corrección |
|----------------|------------|
| Auditoría proponía `projects` tabla separada Y `groups.type_code` | **Decisión**: Solo `groups.type_code` — no crear `projects` separada inicialmente |
| Auditoría usaba `groups.created_by`, `created_at`, `updated_at` sin verificar | **Verificado**: Existen en 001_schema.sql líneas 143-146 |
| Auditoría proponía `preparation_work_files` con `files.resource_id` FK | **Corregido**: `preparation_work_files` referencia `files.id` (que ya tiene resource_id NOT NULL) |
| Auditoría proponía capabilities JSON sin diseño de herencia | **Corregido**: Diseño de capabilities con herencia recursiva por `parent_id` |
| Auditoría mezclaba herencia jerárquica con acumulación de capabilities | **Aclarado**: Herencia = recorrer parent_id; Capabilities = conjunto de permisos por rol |

---

## 5. Arquitectura de datos definitiva

### 5.1 Tabla `spaces` (nueva)

```sql
CREATE TABLE IF NOT EXISTS spaces (
    id            VARCHAR(191) NOT NULL PRIMARY KEY,
    space_type    ENUM('personal','group','project') NOT NULL,
    owner_sub     VARCHAR(191) NOT NULL COMMENT 'user_id del propietario (osap-auth)',
    group_id      VARCHAR(191) NULL COMMENT 'FK a groups(id) SOLO para space_type=group/project',
    name          VARCHAR(160) NOT NULL,
    description   TEXT NULL,
    created_at    VARCHAR(64) NOT NULL,
    updated_at    VARCHAR(64) NOT NULL,
    CONSTRAINT chk_space_group CHECK (
        (space_type = 'group' AND group_id IS NOT NULL) OR
        (space_type = 'project' AND group_id IS NOT NULL) OR
        (space_type = 'personal' AND group_id IS NULL)
    ),
    CONSTRAINT fk_space_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Explicación:**
- `space_type`: 'personal' (unipersonal), 'group' (agrupación estable), 'project' (temporal).
- `group_id`: Para 'group' y 'project', referencia `groups.id`. Para 'personal', NULL.
- `ON DELETE RESTRICT`: No se puede eliminar un grupo/proyecto que tenga espacios activos.

### 5.2 Modificación `groups` (añadir type_code)

```sql
ALTER TABLE groups
    ADD COLUMN type_code ENUM('group','project') NOT NULL DEFAULT 'group' AFTER kind;
```

**Explicación:**
- Distingue grupos estables ('group') de proyectos temporales ('project').
- Ambos usan `groups` como entidad de pertenencia (membresías, roles, secciones).
- Un proyecto puede tener `dissolution_date` para marcar fin.

### 5.3 Modificación `preparation_works` (migración)

```sql
-- Paso 1: Añadir space_id (nullable temporalmente)
ALTER TABLE preparation_works
    ADD COLUMN space_id VARCHAR(191) NULL AFTER id,
    ADD CONSTRAINT fk_prepworks_space FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE RESTRICT;

-- Paso 2: Crear spaces para grupos existentes
INSERT INTO spaces (id, space_type, owner_sub, group_id, name, created_at, updated_at)
SELECT g.id, 'group', g.created_by, g.id, g.name, g.created_at, g.updated_at
FROM groups g
LEFT JOIN spaces s ON s.group_id = g.id AND s.space_type = 'group'
WHERE s.id IS NULL;

-- Paso 3: Migrar preparation_works existentes
UPDATE preparation_works pw
JOIN spaces s ON s.group_id = pw.group_id AND s.space_type = 'group'
SET pw.space_id = s.id;

-- Paso 4: Verificar que no quedan NULLs, luego modificar columna
ALTER TABLE preparation_works MODIFY COLUMN space_id VARCHAR(191) NOT NULL;

-- Paso 5: Eliminar group_id (después de verificar que no hay referencias en código)
ALTER TABLE preparation_works DROP FOREIGN KEY fk_preparation_works_group;
ALTER TABLE preparation_works DROP COLUMN group_id;
ALTER TABLE preparation_works DROP INDEX idx_preparation_works_group;
```

### 5.4 Tabla `preparation_work_items` (nueva)

```sql
CREATE TABLE IF NOT EXISTS preparation_work_items (
    id                  VARCHAR(191) NOT NULL PRIMARY KEY,
    preparation_work_id VARCHAR(191) NOT NULL,
    work_id             VARCHAR(191) NOT NULL COMMENT 'FK → works(id)',
    resource_id         VARCHAR(191) NOT NULL COMMENT 'FK → resources(id)',
    voice_label         VARCHAR(64) NULL COMMENT 'Soprano, Tenor, etc.',
    instrument          VARCHAR(64) NULL,
    custom_title        VARCHAR(200) NULL,
    sort_order          INT NOT NULL DEFAULT 0,
    status              ENUM('pending','rehearsing','ready','archived') NOT NULL DEFAULT 'pending',
    notes               TEXT NULL,
    created_at          VARCHAR(64) NOT NULL,
    updated_at          VARCHAR(64) NOT NULL,
    CONSTRAINT fk_pwi_prepwork FOREIGN KEY (preparation_work_id)
        REFERENCES preparation_works(id) ON DELETE CASCADE,
    CONSTRAINT fk_pwi_work FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE RESTRICT,
    CONSTRAINT fk_pwi_resource FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    -- FK compuesta: Resource debe pertenecer a Work
    CONSTRAINT fk_pwi_work_resource FOREIGN KEY (work_id, resource_id)
        REFERENCES resources(work_id, id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Explicación:**
- `work_id` y `resource_id` son NOT NULL — no se permite NULL.
- FK compuesta `(work_id, resource_id) → resources(work_id, id)` garantiza coherencia V6.
- `ON DELETE RESTRICT` en work_id y resource_id protege referencias existentes.
- `ON DELETE CASCADE` en preparation_work_id elimina items al eliminar trabajo.

### 5.5 Tabla `preparation_work_files` (nueva)

```sql
CREATE TABLE IF NOT EXISTS preparation_work_files (
    id                  VARCHAR(191) NOT NULL PRIMARY KEY,
    preparation_work_id VARCHAR(191) NOT NULL,
    file_id             VARCHAR(191) NOT NULL COMMENT 'FK → files(id)',
    purpose             ENUM('score','part','audio','video','other') NOT NULL DEFAULT 'other',
    sort_order          INT NOT NULL DEFAULT 0,
    created_at          VARCHAR(64) NOT NULL,
    CONSTRAINT fk_pwf_prepwork FOREIGN KEY (preparation_work_id)
        REFERENCES preparation_works(id) ON DELETE CASCADE,
    CONSTRAINT fk_pwf_file FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Explicación:**
- Referencia Files existentes en OSAP V6.
- `ON DELETE RESTRICT` en file_id: no se puede eliminar un File referenciado.
- Propósito: 'score', 'part', 'audio', 'video', 'other'.

### 5.6 Biblioteca compartida (nueva)

```sql
CREATE TABLE IF NOT EXISTS group_library_items (
    id            VARCHAR(191) NOT NULL PRIMARY KEY,
    group_id      VARCHAR(191) NOT NULL,
    work_id       VARCHAR(191) NULL,
    resource_id   VARCHAR(191) NULL,
    file_id       VARCHAR(191) NULL,
    title         VARCHAR(500) NOT NULL,
    added_by      VARCHAR(191) NOT NULL,
    created_at    VARCHAR(64) NOT NULL,
    CONSTRAINT fk_gli_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    CONSTRAINT fk_gli_work FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE RESTRICT,
    CONSTRAINT fk_gli_resource FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    CONSTRAINT fk_gli_file FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Explicación:**
- Biblioteca compartida por grupo/proyecto.
- Referencias a Works/Resources/Files existentes (no duplica).
- `ON DELETE CASCADE` en group_id: al eliminar grupo, se elimina biblioteca compartida.
- `ON DELETE RESTRICT` en work_id/resource_id/file_id: protege referencias.

### 5.7 Modificación `group_roles` (capabilities)

```sql
ALTER TABLE group_roles
    ADD COLUMN capabilities JSON NULL COMMENT 'Array de capability strings';
```

**Explicación:**
- Capabilities como array JSON de strings.
- Ejemplo: `["preparation_work:create", "preparation_work:update", "library_shared:write"]`.

---

## 6. Modelo de permisos definitivo

### 6.1 Capabilities por defecto

| Capability | Descripción |
|------------|-------------|
| `space:read` | Ver información del espacio |
| `space:update` | Editar información del espacio |
| `space:convert_personal_to_group` | Convertir espacio personal a grupo |
| `space:convert_personal_to_project` | Convertir espacio personal a proyecto |
| `preparation_work:create` | Crear trabajo de preparación |
| `preparation_work:read` | Ver trabajos de preparación |
| `preparation_work:update` | Editar trabajo de preparación |
| `preparation_work:delete` | Eliminar trabajo de preparación |
| `preparation_work:manage_files` | Gestionar archivos del trabajo |
| `preparation_work_item:create` | Añadir obra a trabajo |
| `preparation_work_item:update` | Editar item del trabajo |
| `preparation_work_item:delete` | Eliminar item del trabajo |
| `library_personal:read` | Ver biblioteca personal |
| `library_personal:write` | Editar biblioteca personal |
| `library_shared:read` | Ver biblioteca compartida |
| `library_shared:write` | Añadir a biblioteca compartida |
| `library_shared:manage` | Gestionar biblioteca compartida |
| `member:invite` | Invitar miembros |
| `member:remove` | Eliminar miembros |
| `member:manage_roles` | Gestionar roles de miembros |
| `role:create` | Crear roles |
| `role:update` | Editar roles |
| `role:delete` | Eliminar roles |

### 6.2 Roles por defecto y sus capabilities

| Rol | Capabilities |
|-----|--------------|
| **Personal (owner)** | Todas (`*`) |
| **Manager** | `space:read`, `space:update`, `preparation_work:*`, `library_shared:*`, `member:*`, `role:*` |
| **Director Musical** | `space:read`, `preparation_work:*`, `library_shared:read`, `preparation_work:manage_files` |
| **Jefe de Sección** (hijo de Director) | `space:read`, `preparation_work:read`, `preparation_work:create`, `preparation_work:update` (en su sección) |
| **Miembro** | `space:read`, `preparation_work:read`, `library_shared:read` |

### 6.3 Algoritmo de resolución de permisos

```python
def get_user_capabilities(conn, group_id: str, user_id: str) -> set[str]:
    """Obtiene todas las capabilities del usuario en un grupo, incluyendo herencia."""
    # 1. Obtener membership del usuario
    member = conn.execute(
        "SELECT role, admin_role_id, musical_role_id FROM group_members "
        "WHERE group_id = ? AND user_sub = ? AND status = 'active'",
        (group_id, user_id)
    ).fetchone()
    
    if not member:
        return set()
    
    capabilities = set()
    
    # 2. Capabilities del rol base (manager/member)
    if member["role"] == "manager":
        capabilities.update(MANAGER_CAPABILITIES)
    else:
        capabilities.update(MEMBER_CAPABILITIES)
    
    # 3. Recorrer jerarquía de roles admin
    admin_role_id = member["admin_role_id"]
    while admin_role_id:
        role = conn.execute(
            "SELECT capabilities, parent_id FROM group_roles WHERE id = ?",
            (admin_role_id,)
        ).fetchone()
        if not role:
            break
        if role["capabilities"]:
            caps = json.loads(role["capabilities"])
            capabilities.update(caps)
        admin_role_id = role["parent_id"]
    
    # 4. Recorrer jerarquía de roles musicales
    musical_role_id = member["musical_role_id"]
    while musical_role_id:
        role = conn.execute(
            "SELECT capabilities, parent_id FROM group_roles WHERE id = ?",
            (musical_role_id,)
        ).fetchone()
        if not role:
            break
        if role["capabilities"]:
            caps = json.loads(role["capabilities"])
            capabilities.update(caps)
        musical_role_id = role["parent_id"]
    
    return capabilities
```

### 6.4 Precedencia y resolución de conflictos

1. **Capabilities más específicas prevalecen** — Un Jefe de Sección (hijo de Director) hereda capabilities del Director, pero puede tener restricciones adicionales por sección.
2. **Restricción por sección** — Si `member.section_id` está definido, capabilities de `preparation_work:*` se limitan a items con `voice_label` correspondiente a esa sección.
3. **No escalada de privilegios** — Un rol hijo NO puede tener más capabilities que su padre. Solo puede tener el mismo conjunto o un subconjunto.
4. **Revocación efectiva** — Si se elimina un rol padre, los hijos heredan del abuelo (o pierden capabilities si no hay abuelo).

---

## 7. Contratos API necesarios

### 7.1 Endpoints nuevos requeridos

| Endpoint | Método | Propósito | Autenticación |
|----------|--------|-----------|---------------|
| `/api/v1/spaces` | GET | Listar espacios del usuario | Token usuario |
| `/api/v1/spaces` | POST | Crear espacio personal | Token usuario |
| `/api/v1/spaces/{id}` | GET | Obtener espacio | Token usuario |
| `/api/v1/spaces/{id}` | PATCH | Actualizar espacio | Owner o Manager |
| `/api/v1/spaces/{id}/convert` | POST | Convertir personal→grupo/proyecto | Owner |
| `/api/v1/spaces/{id}/preparation-works` | GET/POST | Trabajos del espacio | Miembro con permiso |
| `/api/v1/spaces/{id}/preparation-works/{id}` | GET/PATCH/DELETE | CRUD trabajo | Manager/Director |
| `/api/v1/spaces/{id}/preparation-works/{id}/items` | GET/POST | Items del trabajo | Miembro con permiso |
| `/api/v1/spaces/{id}/preparation-works/{id}/items/{id}` | PATCH/DELETE | CRUD item | Manager/Director |
| `/api/v1/spaces/{id}/preparation-works/{id}/files` | POST/GET | Archivos del trabajo | Manager/Director |
| `/api/v1/spaces/{id}/library` | GET | Biblioteca del espacio | Miembro |
| `/api/v1/spaces/{id}/library` | POST | Añadir a biblioteca compartida | Manager |

### 7.2 Contratos con osap-auth

| Operación | Método | Propósito |
|-----------|--------|-----------|
| Validar token | `GET /auth/me` | Verificar identidad y roles |
| Obtener perfil | `GET /auth/me` | Datos del usuario (name, email, avatar) |
| Actualizar perfil | `PATCH /auth/me` | Editar nombre, email |

### 7.3 Contratos con osap-api (futuros)

| Operación | Método | Propósito |
|-----------|--------|-----------|
| Verificar admin OSAP | `GET /auth/me` (roles) | Comprobar si usuario es admin global |
| Listar usuarios OSAP | `GET /admin/users` | Gestión de membresías (admin only) |

---

## 8. Comportamiento funcional y navegación

### 8.1 Flujo de usuario nuevo (músico independiente)

1. **Registro** → osap-auth crea usuario.
2. **Primer acceso** → Chorus detecta que no tiene espacios → crea espacio personal automáticamente.
3. **Dashboard** → Muestra espacio personal con:
   - Trabajos de preparación (vacío inicialmente).
   - Biblioteca personal (vacía).
   - Actuaciones personales (vacías).
4. **Crear trabajo** → "Nuevo trabajo de preparación" → Añade obras → Sube archivos.
5. **Crear actuación** → "Nueva actuación" → Vincula opcionalmente a trabajo.

### 8.2 Flujo de conversión a grupo

1. **Usuario en espacio personal** → Click "Convertir a grupo".
2. **Formulario** → Nombre, descripción, zona horaria.
3. **Confirmación** → Transacción atómica:
   - Crea `groups` con `type_code='group'`.
   - Crea `group_members` con owner como manager.
   - Actualiza `spaces.group_id`.
   - No copia biblioteca personal (permanece privada).
4. **Resultado** → Usuario ahora tiene espacio tipo 'group'.

### 8.3 Navegación por espacio

```
[Selector de espacio: 👤 Personal | 👥 Coro Aurora | 📁 Proyecto Navidad]
├── Trabajos de preparación
│   ├── 🎵 Concierto Navidad 2026 (activo)
│   │   ├── Obras (lista con voice_label, status, notas)
│   │   ├── Archivos adjuntos
│   │   └── Acciones: editar, duplicar, archivar
│   ├── 🎵 Audición Tenor (borrador)
│   └── [+ Nuevo trabajo]
├── Biblioteca
│   ├── 📚 Personal (mis obras, mis archivos)
│   ├── 📚 Compartida (grupo/proyecto) — solo si space_type != personal
│   └── [+ Añadir desde catálogo OSAP]
├── Actuaciones y agenda
│   ├── Próximos eventos
│   ├── Historial
│   └── [+ Nuevo evento]
└── Configuración
    ├── Miembros y roles (solo grupo/proyecto)
    ├── Roles y permisos
    └── Convertir a grupo/proyecto (solo personal)
```

### 8.4 Principios de UX

1. **Un solo espacio** → No mostrar selector; entrar directamente.
2. **Varios espacios** → Selector visible con nombre y tipo.
3. **Cambio de espacio** → Recarga contexto (trabajos, biblioteca, actuaciones).
4. **Actuaciones independientes** → No requieren trabajo de preparación.
5. **Vincular actuación a trabajo** → Opcional, vía selector en formulario de evento.

---

## 9. Estrategia de migración de datos

### 9.1 Fases de migración

| Fase | Script | Riesgo | Rollback |
|------|--------|--------|----------|
| **0** | Backup completo BD | Bajo | Restaurar backup |
| **1** | Crear tabla `spaces` | Bajo | Dropear tabla |
| **2** | Añadir `groups.type_code` | Bajo | Dropear columna |
| **3** | Crear `spaces` para grupos existentes | Medio | Dropear spaces, restaurar groups |
| **4** | Añadir `preparation_works.space_id` (nullable) | Medio | Dropear columna |
| **5** | Migrar datos `preparation_works` | Alto | Restaurar backup |
| **6** | Hacer `space_id` NOT NULL | Alto | Restaurar backup |
| **7** | Eliminar `preparation_works.group_id` | Alto | Restaurar backup |
| **8** | Crear `preparation_work_items` | Bajo | Dropear tabla |
| **9** | Crear `preparation_work_files` | Bajo | Dropear tabla |
| **10** | Crear `group_library_items` | Bajo | Dropear tabla |
| **11** | Añadir `capabilities` a `group_roles` | Bajo | Dropear columna |

### 9.2 Verificaciones previas

```sql
-- 1. Verificar índice único para FK compuesta
SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'resources'
  AND INDEX_NAME = 'uq_resources_work';
-- Debe devolver 1

-- 2. Verificar datos preparation_works existentes
SELECT COUNT(*) FROM preparation_works;

-- 3. Verificar que todos los group_id tienen groups correspondiente
SELECT pw.group_id FROM preparation_works pw
LEFT JOIN groups g ON g.id = pw.group_id
WHERE g.id IS NULL;
-- Debe devolver 0 filas
```

### 9.3 Script de rollback

```sql
-- Rollback Fase 7 (re-añadir group_id)
ALTER TABLE preparation_works
    ADD COLUMN group_id VARCHAR(191) NULL AFTER id,
    ADD CONSTRAINT fk_preparation_works_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE;

-- Poblar desde spaces
UPDATE preparation_works pw
JOIN spaces s ON s.id = pw.space_id
SET pw.group_id = s.group_id;

-- Verificar
SELECT COUNT(*) FROM preparation_works WHERE group_id IS NULL;
-- Debe devolver 0

-- Hacer NOT NULL y eliminar space_id
ALTER TABLE preparation_works MODIFY COLUMN group_id VARCHAR(191) NOT NULL;
ALTER TABLE preparation_works DROP FOREIGN KEY fk_prepworks_space;
ALTER TABLE preparation_works DROP COLUMN space_id;
```

---

## 10. Plan de implementación ordenado por dependencias

### Fase 1: Modelo de datos (2 semanas)

| # | Tarea | Dependencias | Criterio aceptación |
|---|-------|--------------|---------------------|
| 1.1 | Crear tabla `spaces` | — | Tests CRUD spaces |
| 1.2 | Añadir `groups.type_code` | — | Valores 'group'/'project' |
| 1.3 | Migrar `preparation_works.group_id → space_id` | spaces | Todos los trabajos migrados |
| 1.4 | Crear `preparation_work_items` con FK compuesta | resources V6 | FK compuesta funcionando |
| 1.5 | Crear `preparation_work_files` | files V6 | Referencias funcionando |
| 1.6 | Crear `group_library_items` | library_items | Biblioteca compartida funcionando |
| 1.7 | Añadir `capabilities` a `group_roles` | — | Columna JSON añadida |

### Fase 2: Endpoints y lógica (3 semanas)

| # | Tarea | Dependencias | Criterio aceptación |
|---|-------|--------------|---------------------|
| 2.1 | CRUD `spaces` | Fase 1 | Endpoint personal/group/project |
| 2.2 | Conversión personal→grupo/proyecto | spaces, groups | Transacción atómica |
| 2.3 | CRUD `preparation_work_items` | preparation_works | Añadir/quitar items |
| 2.4 | Validación coherencia Work→Resource | preparation_work_items | FK compuesta + validación |
| 2.5 | CRUD biblioteca compartida | group_library_items | Compartir obra con grupo |
| 2.6 | Resolución capabilities recursiva | group_roles | Herencia funciona |

### Fase 3: Permisos y UX (2 semanas)

| # | Tarea | Dependencias | Criterio aceptación |
|---|-------|--------------|---------------------|
| 3.1 | Capabilities por rol | Fase 1-2 | Nuevos roles sin cambiar código |
| 3.2 | Selector de espacio en UI | spaces | Cambiar entre espacios |
| 3.3 | Espacio personal por defecto | spaces | Usuario nuevo tiene espacio personal |
| 3.4 | Navegación por espacio | spaces | Trabajos/biblioteca/actuaciones aislados |

### Fase 4: Tests y validación (1 semana)

| # | Tarea | Dependencias | Criterio aceptación |
|---|-------|--------------|---------------------|
| 4.1 | Tests aislamiento trabajos | Fase 1-2 | Dos trabajos no interfieren |
| 4.2 | Tests conversión espacio | Fase 2 | Conversión transaccional |
| 4.3 | Tests integridad FK compuesta | Fase 1 | Resource no pertenece a Work → error |
| 4.4 | Tests permisos jerárquicos | Fase 3 | Jefe sección hereda permisos |
| 4.5 | Tests migración idempotente | Fase 1 | Ejecutar 2× sin error |

---

## 11. Pruebas necesarias

### 11.1 Pruebas unitarias

| # | Prueba | Objetivo |
|---|--------|----------|
| U-01 | Crear espacio personal | Verificar creation + owner |
| U-02 | Crear grupo desde espacio personal | Verificar conversión |
| U-03 | Añadir item con Work+Resource válidos | Verificar FK compuesta |
| U-04 | Añadir item con Resource de otra Work | Verificar rechazo |
| U-05 | Eliminar Work referenciada en preparation | Verificar RESTRICT |
| U-06 | Herencia de capabilities por jerarquía | Verificar recursión |
| U-07 | Biblioteca compartida: añadir obra | Verificar visibilidad grupo |
| U-08 | Biblioteca personal no se copia al convertir | Verificar aislamiento |

### 11.2 Pruebas de integración

| # | Prueba | Objetivo |
|---|--------|----------|
| I-01 | CRUD completo preparation_works + items | Flujo completo |
| I-02 | Conversión personal→grupo transaccional | Verificar rollback |
| I-03 | Permisos preparation_works por rol | Manager/Director/Member |
| I-04 | Aislamiento entre trabajos mismo espacio | No interferencia |
| I-05 | Aislamiento entre espacios diferentes | No visibilidad cruzada |
| I-06 | Migración preparation_works.group_id → space_id | Datos migrados correctamente |

### 11.3 Pruebas de permisos

| # | Prueba | Escenario |
|---|--------|-----------|
| P-01 | Outsider no ve preparation_works | 403 |
| P-02 | Member no crea preparation_work | 403 |
| P-03 | Director musical crea preparation_work | 201 |
| P-04 | Jefe sección (hijo de director) crea preparation_work | 201 (si herencia implementada) |
| P-05 | Admin OSAP gestiona grupo sin ser miembro | 200 |
| P-06 | Gestor grupo no gestiona otros grupos | 403 |

### 11.4 Pruebas de migración

| # | Prueba | Objetivo |
|---|--------|----------|
| M-01 | Ejecutar migración 2× | Idempotencia |
| M-02 | Ejecutar con FK ya existente | No falla |
| M-03 | Rollback después de Fase 7 | Restaura datos |
| M-04 | Verificar datos migrados | preparation_works con space_id |

### 11.5 Pruebas de concurrencia

| # | Prueba | Objetivo |
|---|--------|----------|
| C-01 | Dos usuarios editan mismo preparation_work simultáneamente | Sin corrupción |
| C-02 | Conversión espacio mientras otro usuario añade item | Transacción consistente |

---

## 12. Riesgos y medidas de protección

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Pérdida de datos en migración preparation_works | Media | Alto | Backup completo + rollback script |
| FK compuesta falla por datos inconsistentes | Baja | Alto | Verificar datos antes de migrar |
| Capabilities JSON inválido | Baja | Medio | Validación en servidor |
| Herencia recursiva causa stack overflow | Muy baja | Medio | Límite de profundidad (máx 10 niveles) |
| Conversión espacio falla a mitad | Baja | Alto | Transacción atómica con rollback |
| Usuario elimina grupo con espacios activos | Media | Medio | `ON DELETE RESTRICT` en spaces.group_id |
| Biblioteca compartida crece sin control | Baja | Bajo | Cuotas por grupo (futuro) |

---

## 13. Decisiones funcionales que requieren aprobación

| # | Decisión | Alternativas | Recomendación |
|---|----------|--------------|---------------|
| **D-01** | ¿Crear tabla `projects` separada o usar `groups.type_code`? | (a) `projects` separada; (b) `groups` con `type_code` | **(b)** — Menos tablas, menos migración. Añadir `projects` después si necesario. |
| **D-02** | Capabilities predeterminadas por rol | (a) Hardcode en migración; (b) Configurable por grupo | **(a)** — Simplifica inicio. Configurable después. |
| **D-03** | Notificaciones por cambios en trabajos | (a) Email; (b) WhatsApp/SMS; (c) In-app | **(c) In-app + (a) opcional** — Menor complejidad. |
| **D-04** | Formatos exportación programa | (a) PDF; (b) MusicXML; (c) CSV; (d) JSON | **(a) PDF + (d) JSON** — Cobertura básica. |
| **D-05** | Duplicar trabajo: copiar items o referencias? | (a) Copiar todo; (b) Solo referencias | **(b) Referencias** — Evita duplicación. |
| **D-06** | Cuotas almacenamiento por espacio | (a) Sin límite; (b) Por espacio; (c) Por usuario | **(c) Por usuario** — Más simple. |
| **D-07** | Búsqueda global entre espacios | (a) Solo espacio actual; (b) Todos los espacios | **(a) Inicial, (b) después** — Complejidad. |
| **D-08** | Historial cambios en items | (a) Sin historial; (b) Tabla history; (c) Audit log | **(c) Audit log** — Reutilizar `activity_log`. |
| **D-09** | Relación opcional actuación↔trabajo | (a) FK en events; (b) Tabla relación N:M | **(a) FK opcional** — Simple. |
| **D-10** | Biblioteca compartida: ¿copiar o solo referenciar? | (a) Copiar; (b) Solo referencias | **(b) Solo referencias** — No duplicar. |

---

## 14. Conclusión

Esta arquitectura definitiva resuelve las inconsistencias de la auditoría anterior y proporciona una base sólida para la implementación:

1. **`spaces` como entidad unificadora** — Resuelve el problema del espacio personal sin crear grupos ficticios.
2. **`groups.type_code`** — Distingue grupos estables de proyectos temporales sin tablas separadas.
3. **`preparation_work_items` con FK compuesta** — Garantiza integridad V6 (Work→Resource).
4. **Bibliotecas separadas** — Personal y compartida son independientes.
5. **Capabilities con herencia recursiva** — Permisos extensibles sin cambiar código.
6. **Conversión transaccional** — Sin pérdidas ni copias innecesarias.
7. **Migración segura** — Con backup y rollback definidos.

**Próximos pasos:**
1. Revisar y aprobar decisiones D-01 a D-10.
2. Crear rama de desarrollo para migración spaces.
3. Ejecutar migración en entorno de test (osap_chorus_test).
4. Validar con tests de integración completos.
5. Desplegar a producción con rollback plan.

---

**Fin del documento de arquitectura definitiva**