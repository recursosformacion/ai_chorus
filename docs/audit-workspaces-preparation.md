# Auditoría técnica y funcional de Chorus — Espacios de trabajo y trabajos de preparación

**Versión:** 1.0 (Informe de auditoría)  
**Fecha:** 2026-11-21  
**Referencia:** «Espacios de trabajo y trabajos de preparación — Especificación técnica y funcional, versión 1.0, 21-11-2026»  
**Estado:** Informe histórico, superado por la implementación de migraciones 037–042 y la documentación vigente de `docs/workspaces-and-preparation.md`.  
**Tipo de auditoría:** Técnica y funcional, basada en código real

---

> **Aviso:** este documento describe el estado anterior a la implementación de los espacios. No debe utilizarse como diagnóstico actual ni como guía de despliegue. La referencia vigente es `docs/workspaces-and-preparation.md` y las migraciones 037–042.

## A. Resumen ejecutivo

### Estado general

Chorus se encuentra en un **estado parcial de implementación** respecto a la especificación de espacios de trabajo y trabajos de preparación. Existen **fundaciones básicas** (tablas de grupos, miembros, roles, biblioteca personal, preparation_works), pero **no existe el concepto de "espacio" unificador** (Personal/Grupo/Proyecto), lo cual es el pilar central de la especificación.

### Principales hallazgos

| Área | Estado | Gravedad |
|------|--------|----------|
| **Espacios de trabajo** | **No implementado** — solo existe `groups`, no hay `spaces` ni `projects` | **Crítico** |
| **Trabajos de preparación** | Parcialmente implementado — funciona pero requiere grupo, no tiene aislamiento por espacio | **Alto** |
| **Integridad Work/Resource** | Deficiente — FK simples, no compuesta; `files.resource_id` no siempre obligatorio | **Alto** |
| **Biblioteca** | Solo personal (`owner_sub`); no hay biblioteca compartida | **Alto** |
| **Permisos jerárquicos** | `group_roles.parent_id` existe pero **no se recorre** para herencia | **Medio** |
| **Migración 035** | `preparation_works.group_id NOT NULL FK→groups` — impide espacio personal | **Crítico** |
| **Conversión personal→grupo** | No existe endpoint ni lógica | **Alto** |
| **Capabilities/permisos extensibles** | No implementado — solo roles hardcodeados (manager/member/director) | **Medio** |
| **Integración OSAP V6** | Parcial — se referencian Work/Resource/File pero sin validación de coherencia | **Medio** |
| **Notificaciones** | Preferencias en `group_members` pero sin uso funcional | **Bajo** |

### Recomendación general

**No implementar** todavía el modelo completo. Es necesario:
1. Decidir si se introduce `spaces` o se reutiliza `groups` con `type_code`.
2. Diseñar migración segura para `preparation_works.group_id → space_id`.
3. Implementar biblioteca compartida.
4. Corregir integridad referencial Work/Resource.
5. Diseñar sistema de capabilities o mejorar permisos jerárquicos.

---

## B. Inventario real

### B.1 Tablas existentes (verificadas en migraciones y código)

| Tabla | Migración origen | Columnas clave | FKs relevantes | Estado |
|-------|------------------|----------------|-----------------|--------|
| `chorus_schema_migrations` | 001_schema.sql | name (PK), applied_at | — | ✅ Existe |
| `works` | 001_schema.sql | id (PK), title, required_resource_id | — | ✅ Existe |
| `resources` | 001_schema.sql | id (PK), work_id FK→works | work_id | ✅ Existe |
| `files` | 001_schema.sql | id (PK), resource_id FK→resources | resource_id | ✅ Existe |
| `groups` | 001_schema.sql | id (PK), name, entity_id, join_code | — | ✅ Existe |
| `group_members` | 001_schema.sql + 033/034 | id (PK), group_id FK→groups, user_sub, role, admin_role_id FK→group_roles, musical_role_id FK→group_roles | group_id, admin_role_id, musical_role_id | ✅ Existe |
| `events` | 001_schema.sql | id (PK), group_id FK→groups (NULLABLE) | group_id | ✅ Existe (permite personal) |
| `library_items` | 001_schema.sql | id (PK), owner_sub, work_id FK→works (NULLABLE) | work_id | ✅ Existe |
| `group_roles` | 029_create_group_roles.sql | id (PK), group_id FK→groups, scope, parent_id FK→group_roles (self) | group_id, parent_id | ✅ Existe (jerarquía definida pero no usada) |
| `group_sections` | 006_group_articles_tables.sql | id (PK), group_id FK→groups | group_id | ✅ Existe |
| `preparation_works` | 035_preparation_works.sql | id (PK), **group_id FK→groups NOT NULL** | **group_id** | ⚠️ Existe pero problemático |
| `preparation_work_items` | **No existe** | — | — | ❌ **Faltante** |
| `preparation_work_files` | **No existe** | — | — | ❌ **Faltante** |
| `spaces` | **No existe** | — | — | ❌ **Faltante** |
| `projects` / `project_members` / `project_roles` | **No existe** | — | — | ❌ **Faltante** |
| `group_library_items` | **No existe** | — | — | ❌ **Faltante** |

### B.2 Endpoints existentes (verificados en main.py)

| Endpoint | Método | Función | Estado |
|----------|--------|---------|--------|
| `/api/v1/auth/me` | GET | `me()` | ✅ Proxy a osap-auth |
| `/api/v1/auth/me` | PATCH | `update_my_profile()` | ✅ Proxy a osap-auth |
| `/api/v1/library` | GET | `list_library()` | ✅ Solo personal (owner_sub) |
| `/api/v1/library/references` | POST | `add_reference()` | ✅ |
| `/api/v1/library/works/{work_id}` | POST | `add_local_work()` | ✅ |
| `/api/v1/groups` | POST | `create_group()` | ✅ |
| `/api/v1/groups/join` | POST | `join_group()` | ✅ |
| `/api/v1/groups/{group_id}/members` | GET | `group_members()` | ✅ |
| `/api/v1/groups/{group_id}/members` | POST | `add_group_member()` | ✅ |
| `/api/v1/groups/{group_id}/members/{user_sub}` | PATCH | `update_group_member()` | ✅ |
| `/api/v1/groups/{group_id}/members/@me` | PATCH | `update_own_membership()` | ✅ |
| `/api/v1/groups/{group_id}/preparation-works` | GET | `list_preparation_works()` | ✅ |
| `/api/v1/groups/{group_id}/preparation-works` | POST | `create_preparation_work()` | ✅ |
| `/api/v1/groups/{group_id}/preparation-works/{work_id}` | GET/PATCH/DELETE | CRUD individual | ✅ |
| `/api/v1/groups/{group_id}/preparation-works/{work_id}/files` | POST | `upload_preparation_files()` | ✅ (almacenamiento privado) |
| `/api/v1/groups/{group_id}/preparation-works/{work_id}/files` | GET | `list_preparation_files()` | ✅ |
| `/api/v1/groups/{group_id}/roles` | GET/POST/PATCH/DELETE | CRUD roles | ✅ |
| `/api/v1/groups/{group_id}/sections` | GET/POST/PATCH/DELETE | CRUD secciones | ✅ |

### B.3 Endpoints ausentes

| Funcionalidad | Estado |
|---------------|--------|
| CRUD de espacios personales | ❌ No existe |
| Conversión personal→grupo/proyecto | ❌ No existe |
| Biblioteca compartida (grupo/proyecto) | ❌ No existe |
| `preparation_work_items` (items del trabajo) | ❌ No existe (solo `preparation_works` metadata) |
| FK compuesta Work+Resource en preparation_work_items | ❌ No existe tabla |
| Validación de coherencia Work→Resource al añadir item | ❌ No existe |
| Borrado protegido de Works/Resources con RESTRICT | ❌ Usa CASCADE |
| Capabilities por rol | ❌ No existe |
| Herencia recursiva de roles padre-hijo | ❌ `parent_id` existe pero no se recorre |
| Búsqueda global entre espacios | ❌ No existe |

---

## C. Matriz de cumplimiento

| # | Requisito especificación | Estado | Evidencia |
|---|--------------------------|--------|-----------|
| **1** | **Espacios de trabajo (Personal/Grupo/Proyecto)** | ❌ **No cumple** | No existe tabla `spaces`, `projects`. Solo `groups`. No hay `space_id`. |
| 1.1 | Tabla `spaces` unificadora | ❌ No cumple | No existe |
| 1.2 | `preparation_works.space_id` NOT NULL FK→spaces | ❌ No cumple | `preparation_works.group_id NOT NULL FK→groups` |
| 1.3 | Selector de espacio en UX | ❌ No cumple | No hay concepto de espacio |
| 1.4 | Espacio personal por defecto al registro | ❌ No cumple | No existe; usuario debe crear grupo para preparar |
| **2** | **Trabajos de preparación por espacio** | ⚠️ **Parcial** | Existe `preparation_works` pero ligada a `group_id` |
| 2.1 | Un trabajo pertenece a un único espacio | ❌ No cumple | Pertenece a `group_id` |
| 2.2 | Dos trabajos independientes en mismo espacio | ✅ Cumple | Funciona (mismo group_id, distinto work_id) |
| 2.3 | Modificar trabajo no modifica biblioteca | ✅ Cumple | No hay relación auto |
| 2.4 | Eliminar trabajo no elimina Works/Resources/Files | ⚠️ Parcial | `preparation_works` borrado elimina solo fila; Files en storage privado no referenciados en BD |
| 2.5 | Work y Resource corresponden | ❌ No cumple | No hay `preparation_work_items` con FK compuesta |
| **3** | **Integridad OSAP V6** | ⚠️ **Parcial** | Tablas V6 existen pero sin validación en preparation_works |
| 3.1 | FK compuesta `(work_id, resource_id)` en preparation_work_items | ❌ No cumple | Tabla no existe |
| 3.2 | `resources(work_id, id)` índice único | ✅ Cumple | `uq_resources_work (work_id, id)` en 001_schema.sql |
| 3.3 | `files.resource_id` NOT NULL | ✅ Cumple | `resource_id VARCHAR(191) NOT NULL` en 001_schema.sql |
| 3.4 | No duplicar archivos físicos | ⚠️ Parcial | Preparation files van a storage privado separado (`preparation/{group_id}/{work_id}`) |
| 3.5 | `files.resource_id = NULL` prohibido | ✅ Cumple | No se permite NULL en esquema |
| **4** | **Biblioteca** | ⚠️ **Parcial** | Solo personal (`library_items` con `owner_sub`) |
| 4.1 | Biblioteca personal (owner_sub) | ✅ Cumple | `library_items.owner_sub` |
| 4.2 | Biblioteca compartida grupo/proyecto | ❌ No cumple | No existe `group_library_items` |
| 4.3 | Incorporar a trabajo no añade a biblioteca | ✅ Cumple | No hay relación automática |
| 4.4 | Conversión personal→grupo no copia biblioteca | ❌ No cumple | No existe conversión |
| **5** | **Permisos y jerarquía** | ⚠️ **Parcial** | Roles existen, jerarquía definida pero no usada |
| 5.1 | `group_roles.parent_id` para jerarquía | ✅ Existe columna | Migración 029 |
| 5.2 | Recorrido recursivo para herencia | ❌ No cumple | Solo se usa `parent_id` para validar borrado, no para permisos |
| 5.3 | Permisos por capabilities | ❌ No cumple | Roles hardcodeados: manager, member, director |
| 5.4 | Restricción por sección (`section_id`) | ⚠️ Parcial | `section_id` existe en group_members pero no se usa en preparation_works |
| 5.5 | Director musical puede gestionar preparation_works | ✅ Cumple | `_can_manage_preparation_work` verifica `musical_role_id` con code='director' |
| **6** | **Conversión personal→grupo/proyecto** | ❌ **No cumple** | No existe endpoint ni lógica |
| 6.1 | Transacción atómica | ❌ No cumple | No existe |
| 6.2 | Crear membership propietario | ❌ No cumple | No existe |
| 6.3 | Separar bibliotecas | ❌ No cumple | No existe |
| **7** | **Migraciones** | ⚠️ **Parcial** | Migraciones existen pero no idempotentes para todos los casos |
| 7.1 | `CREATE TABLE IF NOT EXISTS` | ✅ Cumple | Usado en 001, 006, 029, 035 |
| 7.2 | Checks `INFORMATION_SCHEMA` para FKs/indices | ⚠️ Parcial | Solo en 034; no en todas |
| 7.3 | Migración 035 idempotente | ❌ No cumple | Usa `CREATE TABLE IF NOT EXISTS` pero no checks para FK |
| **8** | **Navegación y UX** | ❌ **No cumple** | No hay concepto de espacio |
| 8.1 | Selector de espacio si >1 | ❌ No cumple | No existe |
| 8.2 | Espacio personal sin crear grupo | ❌ No cumple | Obliga a crear grupo |
| 8.3 | Actuaciones personales sin grupo | ✅ Cumple | `events.group_id NULLABLE`, `scope='personal'` |
| 8.4 | Vincular actuación a trabajo preparación | ❌ No cumple | No existe relación |

---

## D. Defectos y riesgos

### Críticos

| ID | Defecto | Impacto | Reproducción |
|----|---------|---------|--------------|
| **D-01** | `preparation_works.group_id NOT NULL FK→groups ON DELETE CASCADE` impide espacio personal | Usuario no puede preparar trabajo sin crear grupo | `SELECT * FROM preparation_works` — requiere group_id |
| **D-02** | `ON DELETE CASCADE` en preparation_works borra trabajos al eliminar grupo | Pérdida de datos de preparación | Eliminar grupo con preparation_works → trabajos borrados |
| **D-03** | No existe tabla `preparation_work_items` | No se pueden asociar Works/Resources a trabajos | `SELECT * FROM preparation_work_items` → error tabla no existe |
| **D-04** | No hay FK compuesta Work+Resource en preparation | Puede asociarse Resource de Work diferente | No existe tabla; diseño propuesto requiere `resources(work_id, id)` único |
| **D-05** | No existe conversión personal→grupo | Usuario atrapado en espacio personal | No hay endpoint |

### Altos

| ID | Defecto | Impacto | Reproducción |
|----|---------|---------|--------------|
| **D-06** | No existe biblioteca compartida | Miembros de grupo no comparten biblioteca | `SELECT * FROM group_library_items` → error |
| **D-07** | Permisos no recorren jerarquía `parent_id` | Jefe de sección no hereda permisos de director | Asignar rol hijo → verificar capabilities no heredadas |
| **D-08** | `files.resource_id` permite NULL en esquema propuesto para adjuntos | Violación V6 | (Diseño propuesto en especificación, no en código) |
| **D-09** | Preparation files usan storage privado separado, no `files` table | Duplicación de almacenamiento, sin integridad referencial | `SELECT * FROM files` vs preparation folder |

### Medios

| ID | Defecto | Impacto | Reproducción |
|----|---------|---------|--------------|
| **D-10** | Roles hardcodeados (manager/member/director) | No extensible a nuevas responsabilidades | Crear nuevo rol sin capabilities |
| **D-11** | Migración 035 no idempotente para FK | Fallo si FK ya existe | Ejecutar 035 dos veces → error |
| **D-12** | `events.group_id` NULLABLE permite eventos sin grupo | Correcto para personales, pero sin relación a espacio | Evento personal sin espacio |
| **D-13** | No hay validación Work→Resource al añadir a preparation | Puede asociar Resource incorrecta | No existe validación |

### Bajos

| ID | Defecto | Impacto | Reproducción |
|----|---------|---------|--------------|
| **D-14** | Preferencias notificación en group_members no usadas | Funcionalidad sin efecto | Campos `notify_*` existen pero sin lógica |
| **D-15** | `group_roles.parent_id` existe pero no usado para permisos | Jerarquía visual sin efecto funcional | Ver §5.2 |

---

## E. Diferencias entre diseño y repositorio

### Qué conservar

| Elemento | Razón |
|----------|-------|
| `groups` + `group_members` + `group_roles` | Funcionan, migración a `spaces` puede reutilizarlos |
| `library_items` (owner_sub) | Biblioteca personal funciona correctamente |
| `works` → `resources` → `files` (V6) | Integridad básica existe; FK compuesta viables con `uq_resources_work` |
| `events` con `group_id NULLABLE` | Ya soporta eventos personales |
| `_can_manage_preparation_work` / `_can_view_preparation_work` | Lógica de permisos para preparation_works funciona |
| `group_sections` | Secciones para grupos funcionan |

### Qué modificar

| Elemento | Cambio requerido |
|----------|------------------|
| `preparation_works` | `group_id` → `space_id` FK→spaces ON DELETE RESTRICT |
| Migración 035 | Recrear con `space_id` en lugar de `group_id`; añadir checks idempotentes |
| `preparation_work_items` | Crear tabla con FK compuesta `(work_id, resource_id)→resources(work_id, id)` |
| `preparation_work_files` | Crear tabla para referenciar Files en trabajos |
| Permisos en preparation_works | Añadir capabilities o mejorar jerarquía recursiva |
| Biblioteca | Crear `group_library_items` / `project_library_items` |

### Qué ampliar

| Elemento | Extensión |
|----------|-----------|
| `groups` | Añadir `type_code` (grupo/proyecto) o crear `projects` tabla separada |
| `group_roles` | Añadir columna `capabilities JSON` |
| Permisos | Implementar resolución recursiva de capabilities por jerarquía |
| Conversión | Endpoint transaccional `POST /api/v1/spaces/{space_id}/convert` |

### Qué sustituir

| Elemento | Sustitución |
|----------|-------------|
| Preparación sin items | Añadir `preparation_work_items` con items completos (Work, Resource, voice, etc.) |
| Preparation files en storage privado | Referenciar `files` table vía `preparation_work_files` |
| Roles sin capabilities | Capabilities por rol con herencia |

---

## F. Modelo de datos recomendado

### F.1 Tabla `spaces` (nueva)

```sql
CREATE TABLE IF NOT EXISTS spaces (
    id            VARCHAR(191) NOT NULL PRIMARY KEY,
    space_type    ENUM('personal','group','project') NOT NULL,
    owner_sub     VARCHAR(191) NOT NULL COMMENT 'user_id del propietario (osap-auth)',
    group_id      VARCHAR(191) NULL COMMENT 'FK a groups(id) SOLO para space_type=group',
    project_id    VARCHAR(191) NULL COMMENT 'FK a projects(id) SOLO para space_type=project',
    name          VARCHAR(160) NOT NULL,
    description   TEXT NULL,
    created_at    VARCHAR(64) NOT NULL,
    updated_at    VARCHAR(64) NOT NULL,
    CONSTRAINT chk_space_group CHECK (
        (space_type = 'group' AND group_id IS NOT NULL AND project_id IS NULL) OR
        (space_type = 'project' AND project_id IS NOT NULL AND group_id IS NULL) OR
        (space_type = 'personal' AND group_id IS NULL AND project_id IS NULL)
    ),
    CONSTRAINT fk_space_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT,
    CONSTRAINT fk_space_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### F.2 Tabla `projects` (nueva, alternativa a reutilizar groups)

```sql
CREATE TABLE IF NOT EXISTS projects (
    id            VARCHAR(191) NOT NULL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    description   TEXT NULL,
    owner_sub     VARCHAR(191) NOT NULL,
    created_at    VARCHAR(64) NOT NULL,
    updated_at    VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### F.3 Modificación `preparation_works`

```sql
-- Migración: añadir space_id, migrar datos, dropear group_id
ALTER TABLE preparation_works
    ADD COLUMN space_id VARCHAR(191) NULL AFTER id,
    ADD CONSTRAINT fk_prepworks_space FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE RESTRICT;

-- Migración de datos (asumiendo 1 space por group existente)
INSERT INTO spaces (id, space_type, owner_sub, group_id, name, created_at, updated_at)
SELECT g.id, 'group', g.created_by, g.id, g.name, g.created_at, g.updated_at
FROM groups g
LEFT JOIN spaces s ON s.group_id = g.id AND s.space_type = 'group'
WHERE s.id IS NULL;

UPDATE preparation_works pw
JOIN spaces s ON s.group_id = pw.group_id AND s.space_type = 'group'
SET pw.space_id = s.id;

-- Verificar que no quedan NULLs, luego modificar columna
ALTER TABLE preparation_works MODIFY COLUMN space_id VARCHAR(191) NOT NULL;
ALTER TABLE preparation_works DROP FOREIGN KEY fk_preparation_works_group;
ALTER TABLE preparation_works DROP COLUMN group_id;
```

### F.4 Tabla `preparation_work_items` (nueva)

```sql
CREATE TABLE IF NOT EXISTS preparation_work_items (
    id                  VARCHAR(191) NOT NULL PRIMARY KEY,
    preparation_work_id VARCHAR(191) NOT NULL,
    work_id             VARCHAR(191) NOT NULL COMMENT 'FK → works(id) (obra canónica)',
    resource_id         VARCHAR(191) NOT NULL COMMENT 'FK → resources(id) (versión/arreglo)',
    voice_label         VARCHAR(64) NULL COMMENT 'Soprano, Tenor, Violín I, etc.',
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

**Nota:** Requiere índice único en `resources(work_id, id)` — ya existe: `uq_resources_work`.

### F.5 Tabla `preparation_work_files` (nueva)

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

### F.6 Biblioteca compartida (nueva)

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

### F.7 Capacidades en `group_roles` (modificación)

```sql
ALTER TABLE group_roles
    ADD COLUMN capabilities JSON NULL COMMENT 'Array de capability strings',
    ADD KEY idx_group_roles_capabilities (capabilities(255));
```

---

## G. Modelo de permisos

### G.1 Permisos actuales (verificados en código)

| Función | Rol requerido | Verificación |
|---------|---------------|--------------|
| `create_preparation_work` | Manager O admin O musical_role_id con code='director' | `_can_manage_preparation_work` |
| `update_preparation_work` | Manager O admin O director | `_can_manage_preparation_work` |
| `delete_preparation_work` | Manager O admin O director | `_can_manage_preparation_work` |
| `upload_preparation_files` | Manager O admin O director | `_can_manage_preparation_work` |
| `list_preparation_works` | Cualquier miembro activo O admin | `_can_view_preparation_work` |
| `update_group_member` | Manager O admin | Verificación inline |
| `add_group_member` | Manager O admin | Verificación inline |
| `group_roles` CRUD | Manager O admin | Verificación inline |

### G.2 Permisos propuestos (capabilities)

| Capability | Personal | Grupo | Proyecto |
|------------|----------|-------|----------|
| `preparation_work:create` | ✅ Owner | ✅ Manager + Director | ✅ Manager + Project Lead |
| `preparation_work:read` | ✅ Owner | ✅ Member | ✅ Member |
| `preparation_work:update` | ✅ Owner | ✅ Manager + Director | ✅ Manager |
| `preparation_work:delete` | ✅ Owner | ✅ Manager | ✅ Manager |
| `preparation_work:manage_files` | ✅ Owner | ✅ Manager + Director | ✅ Manager |
| `library_personal:read/write` | ✅ Owner | ✅ Owner | ✅ Owner |
| `library_shared:read` | — | ✅ Member | ✅ Member |
| `library_shared:write` | — | ✅ Manager + Library Manager | ✅ Manager |
| `member:invite` | — | ✅ Manager | ✅ Manager |
| `member:remove` | — | ✅ Manager | ✅ Manager |
| `member:manage_roles` | — | ✅ Manager | ✅ Manager |
| `space:convert_personal_to_group` | ✅ Owner | — | — |
| `space:convert_personal_to_project` | ✅ Owner | — | — |

### G.3 Jerarquía de roles (propuesta)

```
space_owner (capabilities: *)
  └── manager (capabilities: preparation_work:*, member:*, library_shared:manage)
        └── admin_role (capabilities: según scope)
              └── musical_role (capabilities: preparation_work:create/update)
                    └── section_role (capabilities: preparation_work:create en sección)
```

**Algoritmo de resolución:**
1. Obtener roles del usuario en el espacio.
2. Para cada rol, recorrer `parent_id` recursivamente hasta raíz.
3. Acumular capabilities (UNION).
4. Verificar capability requerida en set acumulado.

---

## H. Plan de migración

### H.1 Fases de migración

| Fase | Descripción | Riesgo | Rollback |
|------|-------------|--------|----------|
| **Fase 0: Preparación** | Backup BD, verificar datos existentes | Bajo | Restaurar backup |
| **Fase 1: Crear spaces** | Crear tabla `spaces`, migrar grupos existentes | Medio | Dropear spaces, restaurar grupos |
| **Fase 2: Alterar preparation_works** | Añadir `space_id`, migrar datos, dropear `group_id` | Alto | Restaurar backup |
| **Fase 3: Crear preparation_work_items** | Nueva tabla con FKs | Bajo | Dropear tabla |
| **Fase 4: Crear preparation_work_files** | Nueva tabla | Bajo | Dropear tabla |
| **Fase 5: Biblioteca compartida** | Crear `group_library_items` | Bajo | Dropear tabla |
| **Fase 6: Capabilities** | Añadir columna `capabilities JSON` a `group_roles` | Bajo | Dropear columna |

### H.2 Verificaciones previas

```sql
-- 1. Verificar índice único para FK compuesta
SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'resources'
  AND INDEX_NAME = 'uq_resources_work';

-- 2. Verificar datos preparation_works existentes
SELECT COUNT(*) FROM preparation_works;

-- 3. Verificar que todos los group_id tienen groups correspondiente
SELECT pw.group_id FROM preparation_works pw
LEFT JOIN groups g ON g.id = pw.group_id
WHERE g.id IS NULL;
```

### H.3 Procedimiento de rollback

1. **Antes de migrar:** `mysqldump` completo.
2. **Si falla en cualquier fase:** restaurar dump.
3. **Si falla después de Fase 2:** ejecutar rollback script que:
   - Re-añadir `group_id` a `preparation_works`.
   - Poblar desde `spaces`.
   - Dropear `space_id`.

---

## I. Plan de implementación

### Fase 1: Modelo de datos (2-3 semanas)

| Tarea | Dependencias | Criterio aceptación |
|-------|--------------|---------------------|
| Crear tabla `spaces` | — | Tests CRUD spaces |
| Crear tabla `projects` | — | Tests CRUD projects |
| Migrar `preparation_works.group_id → space_id` | spaces | Todos los trabajos migrados, FK correcta |
| Crear `preparation_work_items` con FK compuesta | resources V6 | FK compuesta funcionando |
| Crear `preparation_work_files` | files V6 | Referencias a Files funcionando |
| Crear `group_library_items` | library_items | Biblioteca compartida funcionando |
| Añadir `capabilities` a `group_roles` | — | Columna JSON añadida |

### Fase 2: Endpoints y lógica (3-4 semanas)

| Tarea | Dependencias | Criterio aceptación |
|-------|--------------|---------------------|
| CRUD `spaces` | Fase 1 | Endpoint personal/group/project |
| Conversión personal→grupo/proyecto | spaces, groups, group_members | Transacción atómica |
| CRUD `preparation_work_items` | preparation_works | Añadir/quitar items con validación Work/Resource |
| Validación coherencia Work→Resource | preparation_work_items | FK compuesta + validación en servicio |
| CRUD biblioteca compartida | group_library_items | Compartir obra con grupo |
| Resolución capabilities recursiva | group_roles | Herencia funciona |

### Fase 3: Permisos y UX (2-3 semanas)

| Tarea | Dependencias | Criterio aceptación |
|-------|--------------|---------------------|
| Capabilities por rol | Fase 1-2 | Nuevos roles sin cambiar código |
| Selector de espacio en UI | spaces | Cambiar entre espacios |
| Espacio personal por defecto | spaces | Usuario nuevo tiene espacio personal |
| Navegación por espacio | spaces | Trabajos/biblioteca/actuaciones aislados |

### Fase 4: Tests y validación (1-2 semanas)

| Tarea | Dependencias | Criterio aceptación |
|-------|--------------|---------------------|
| Tests aislamiento trabajos | Fase 1-2 | Dos trabajos no interfieren |
| Tests conversión espacio | Fase 2 | Conversión transaccional |
| Tests integridad FK compuesta | Fase 1 | Resource no pertenece a Work → error |
| Tests permisos jerárquicos | Fase 3 | Jefe sección hereda permisos |
| Tests migración idempotente | Fase 1 | Ejecutar 2× sin error |

---

## J. Decisiones que requieren aprobación

| # | Decisión | Alternativas | Recomendación |
|---|----------|--------------|---------------|
| **J-01** | Tabla `projects` independiente vs reutilizar `groups` con `type_code` | (a) `projects` separada; (b) `groups` con `type_code='project'` | **(b) Reutilizar groups** — menos tablas, menos migración. Añadir `type_code` y `project_*` tablas solo si necesario. |
| **J-02** | Capabilities predeterminadas por rol | (a) Hardcode en migración; (b) Configurable por grupo | **(a) Hardcode inicial, (b) después** — Simplifica inicio. |
| **J-03** | Notificaciones por cambios en trabajos | (a) Email; (b) WhatsApp/SMS; (c) In-app | **(c) In-app + (a) opcional** — Menor complejidad. |
| **J-04** | Formatos exportación programa | (a) PDF; (b) MusicXML; (c) CSV; (d) JSON | **(a) PDF + (d) JSON** — Cobertura básica. |
| **J-05** | Duplicar trabajo: copiar items o referencias? | (a) Copiar todo; (b) Solo referencias | **(b) Referencias** — Evita duplicación. |
| **J-06** | Cuotas almacenamiento por espacio | (a) Sin límite; (b) Por espacio; (c) Por usuario | **(c) Por usuario** — Más simple. |
| **J-07** | Búsqueda global entre espacios | (a) Solo espacio actual; (b) Todos los espacios | **(a) Inicial, (b) después** — Complejidad. |
| **J-08** | Historial cambios en items | (a) Sin historial; (b) Tabla history; (c) Audit log | **(c) Audit log** — Reutilizar `activity_log`. |
| **J-09** | Relación opcional actuación↔trabajo | (a) FK en events; (b) Tabla relación N:M | **(a) FK opcional** — Simple. |
| **J-10** | Biblioteca compartida: ¿copiar Work/Resource/File o solo referenciar? | (a) Copiar; (b) Solo referencias | **(b) Solo referencias** — No duplicar. |

---

## K. Contratos con osap-api

### Operaciones administrativas requeridas

| Operación | Método | Propósito | Autorización |
|-----------|--------|-----------|--------------|
| Listar usuarios OSAP | `GET /admin/users` | Gestionar membresías | Admin OSAP |
| Obtener perfil usuario | `GET /auth/me` | Validar identidad | Token usuario |
| Verificar admin OSAP | `GET /auth/me` con `roles` | Control acceso admin | Admin OSAP |
| Auditoría de acciones | `POST /audit` (opcional) | Registrar acciones admin | Chorus → OSAP |

### Garantías que Chorus debe ofrecer

1. **No acceso directo BD osap-api desde Chorus** — Solo vía API autenticada.
2. **Validación de admin OSAP** — Chorus debe verificar `roles` del token osap-auth.
3. **Operaciones admin sin membresía** — Admin OSAP puede gestionar grupos sin ser miembro (vía `_is_admin` en Chorus).
4. **No escalada de privilegios** — Gestor de grupo no obtiene permisos globales.

---

## L. Pruebas necesarias

### L.1 Pruebas unitarias

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

### L.2 Pruebas de integración

| # | Prueba | Objetivo |
|---|--------|----------|
| I-01 | CRUD completo preparation_works + items | Flujo completo |
| I-02 | Conversión personal→grupo transaccional | Verificar rollback |
| I-03 | Permisos preparation_works por rol | Manager/Director/Member |
| I-04 | Aislamiento entre trabajos mismo espacio | No interferencia |
| I-05 | Aislamiento entre espacios diferentes | No visibilidad cruzada |
| I-06 | Migración preparation_works.group_id → space_id | Datos migrados correctamente |

### L.3 Pruebas de permisos

| # | Prueba | Escenario |
|---|--------|-----------|
| P-01 | Outsider no ve preparation_works | 403 |
| P-02 | Member no crea preparation_work | 403 |
| P-03 | Director musical crea preparation_work | 201 |
| P-04 | Jefe sección (hijo de director) crea preparation_work | 201 (si herencia implementada) |
| P-05 | Admin OSAP gestiona grupo sin ser miembro | 200 |
| P-06 | Gestor grupo no gestiona otros grupos | 403 |

### L.4 Pruebas de migración

| # | Prueba | Objetivo |
|---|--------|----------|
| M-01 | Ejecutar migración 2× | Idempotencia |
| M-02 | Ejecutar con FK ya existente | No falla |
| M-03 | Rollback después de Fase 2 | Restaura datos |
| M-04 | Verificar datos migrados | preparation_works con space_id |

### L.5 Pruebas de concurrencia

| # | Prueba | Objetivo |
|---|--------|----------|
| C-01 | Dos usuarios editan mismo preparation_work simultáneamente | Sin corrupción |
| C-02 | Conversión espacio mientras otro usuario añade item | Transacción consistente |

---

## M. Conclusiones y recomendaciones finales

### Estado actual: **No listo para implementación completa**

El repositorio tiene **bases funcionales** (grupos, miembros, roles, library_items, preparation_works básica) pero **carece del concepto unificador de "espacio"** que es central para la especificación.

### Riesgos principales

1. **Migración de preparation_works.group_id → space_id** requiere cuidado por datos existentes y FK CASCADE.
2. **Introducir spaces** puede romper endpoints existentes que asumen `group_id`.
3. **FK compuesta Work+Resource** requiere índice único que ya existe, pero debe validarse que todos los datos actuales son coherentes.

### Ruta crítica recomendada

1. **Decidir J-01** (projects vs groups con type_code) — Aprobación funcional requerida.
2. **Crear tabla `spaces`** con migración idempotente.
3. **Migrar preparation_works** con script de backup y rollback.
4. **Crear preparation_work_items** con FK compuesta.
5. **Implementar endpoints CRUD** para spaces, items, files.
6. **Añadir biblioteca compartida**.
7. **Implementar capabilities** o mejorar jerarquía.
8. **Tests completos** antes de producción.

### Próximos pasos

1. **Revisar este informe** con equipo funcional.
2. **Decidir J-01 a J-10** (decisiones pendientes).
3. **Crear rama de desarrollo** para migración spaces.
4. **Ejecutar migración en entorno de test** (osap_chorus_test).
5. **Validar con tests de integración** completos.

---

**Fin del informe de auditoría**