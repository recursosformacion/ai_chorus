# Chorus 0.15 — Auditoría técnica definitiva

**Base:** Chorus 0.14.0  
**Objetivo:** Preparar Chorus 0.15.0  
**Ámbito:** Análisis y documentación exclusivamente — **SIN MODIFICACIONES**

---

## 1. Estado real de Chorus 0.14.0

### 1.1 Backend (Python/FastAPI)

| Componente | Estado | Ubicación |
|------------|--------|-----------|
| **API Core** | Funcional, v0.14.0 | `app/main.py` (3255 líneas) |
| **Autenticación** | OIDC PKCE + Bearer tokens, integración OSAP-Auth | `app/main.py:615-1062` |
| **Base de datos** | Dual SQLite/MySQL via `app/db.py` | `app/db.py`, `app/config.py` |
| **Migraciones** | 15 SQLite incrementales, 3 MySQL monolíticas | `migrations/sqlite/`, `migrations/mysql/` |
| **Grupos/Agenda** | CRUD completo, RSVP binario, recurrencia | `app/main.py:1437-2430` |
| **Mensajería** | Hilos por grupo, reply-all, lectura | `app/main.py:2017-2180` |
| **Material musical** | Árbol, manifiesto, importación, descarga, publicación | `app/main.py:2878-3230` |
| **Biblioteca personal** | Referencias OSAP, obras locales, colecciones | `app/main.py:1105-1280` |
| **Editor (MuseEncore)** | Puente `postMessage`, token temporal, descarga manual | `app/main.py:2694-2745`, `web/editor.html` |
| **Artículos de grupo** | Ciclo draft→published, media, permisos | `app/main.py:1835-2015` |

### 1.2 Frontend Web (Vanilla JS)

| Componente | Estado | Ubicación |
|------------|--------|-----------|
| **App principal** | SPA completa, 2791 líneas | `web/app.js` |
| **Autenticación** | Login, OIDC handoff, refresh automático | `web/app.js:69-133, 1961-2020` |
| **Dashboard** | Grupos, agenda, material, biblioteca | `web/app.js:140-280` |
| **Mensajería** | Inbox, composer, reply-all, modal thread | `web/app.js:660-1240` |
| **Agenda** | Lista eventos, RSVP, recurrencia | `web/app.js:294-465` |
| **Material** | Árbol, importación, descarga, publicación | `web/app.js:1341-1720` |
| **Editor MuseEncore** | Iframe + `postMessage`, guardar y cerrar | `web/editor.html`, `app.js:2271-2293` |
| **Artículos** | Modal CRUD, publicación | `web/app.js:465-560` |

### 1.3 Base de datos

| Motor | Esquema | Migraciones |
|-------|---------|-------------|
| **SQLite** | 20 tablas principales | 15 archivos incrementales (001-015) |
| **MySQL/MariaDB** | Mismas 20 tablas en `001_schema.sql` | 3 archivos (001 monolítico, 002, 003 redundantes) |

### 1.4 Aplicación móvil

| Aspecto | Hallazgo |
|---------|----------|
| **Repositorio** | `D:\Proyectos\AI_OSAP\Chorus_movil\Chorus` — **VACÍO** (git init sin commits) |
| **Código** | No existe implementación móvil en el workspace actual |
| **Integración** | No hay código móvil que auditar — **NO VERIFICADO** |

---

## 2. Arquitectura definitiva dev/test/prod

### 2.1 Tres entornos, tres bases de datos

| Entorno | Base de datos | Usuario | Propósito |
|---------|---------------|---------|-----------|
| **Desarrollo** | `osap_chorus` | `osap2027_dev` | Simula producción, datos reales/sintéticos |
| **Pruebas** | `osap_chorus_test` | `osap2027_test` | Solo tests automatizados, reconstruida cada run |
| **Producción** | `osap_chorus_prod` | (dedicado) | Fuera de alcance |

**Motor único:** MariaDB 10.4.32 para dev/test/prod. SQLite **solo** para tests unitarios puros sin BD.

### 2.2 Configuración — Variable única de verdad

```python
# app/config.py:45-46 — Precedencia REAL verificada
def value(env: str, section: dict, key: str, default: str = "") -> str:
    return os.getenv(env, str(section.get(key, default))).strip()
```

**Orden de prioridad:**
1. Variable de entorno `CHORUS_<SECTION>_<KEY>`
2. Valor en `osap.toml` bajo `[section]` → `key`
3. Default hardcoded

**NO hay interpolación `${VAR}` en `osap.toml`** — el código no usa `os.path.expandvars`.

### 2.3 Credenciales por entorno (NINGUNA en repo)

| Entorno | Variable `CHORUS_STORAGE_DATABASE_URL` |
|---------|----------------------------------------|
| **Dev local** | `mysql+pymysql://osap2027_dev:****@127.0.0.1:3306/osap_chorus` |
| **Tests local/CI** | `mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test` |
| **Producción** | `mysql+pymysql://osap2027_prod:****@db-host:3306/osap_chorus_prod` |

**Archivo `osap.toml` (committed, SIN secrets):**
```toml
[storage]
# database_url se define POR ENTORNO via variable de entorno
root = "var/private"
```

**Referencias inconsistentes corregidas:** Todos los scripts/docs usaban `CHORUS_DATABASE_URL`; la variable real en `Settings.load()` es `CHORUS_STORAGE_DATABASE_URL` (línea 80 `app/config.py`).

---

## 3. Inventario y matriz de migraciones

### 3.1 Análisis real: SQLite vs MySQL

| Migración SQLite | Contenido | Estado en `migrations/mysql/001_schema.sql` |
|------------------|-----------|---------------------------------------------|
| 001_v6_work_resource_file | works, resources, files + FK deferrables | **INCLUIDO** (sin FK deferrables) |
| 002_creation_drafts | creation_drafts, editor_source_tokens + CHECKs | **INCLUIDO** |
| 003_owner_and_library | owner_sub en works + library_items, collections | **INCLUIDO** |
| 004_oidc_states | oidc_states | **INCLUIDO** |
| 005_local_draft_source | Recrea creation_drafts con source_kind='local' | **INCLUIDO** (ya tiene 'local' en CHECK) |
| 006_groups_events | groups, group_members, events, event_groups, event_rsvps, entity_leads | **INCLUIDO** |
| 007_entity_leads | entity_leads | **INCLUIDO** |
| 008_entity_lead_manager | manager_* en entity_leads | **INCLUIDO** |
| 009_messages | display_name en group_members + messages, message_recipients | **INCLUIDO** |
| 010_group_member_roles | admin_role_id, musical_role_id, section_id en group_members | **INCLUIDO** |
| 011_event_targets | event_targets | **INCLUIDO** |
| **012_material_library** | version_label, part_label, material_status en resources + folder_path, display_name, original_name en files + índice | **FALTA** |
| **013_material_groups** | group_id, group_section_id en resources + índice | **FALTA** |
| 014_agenda_recurrence | recurrence, recurrence_until, series_id, creator_badge en events + índice | **INCLUIDO** |
| 015_group_articles | slug, kind, description... en groups + group_sections, group_articles, group_article_media | **INCLUIDO** |

**Conclusión:** `001_schema.sql` MySQL ya contiene el 87% del esquema (13/15 migraciones). Solo faltan **012** y **013** (material). Las migraciones MySQL 002 y 003 son **REDUNDANTES**.

### 3.2 Matriz definitiva de objetos de BD

| Tabla | Columnas clave | Índices | FKs | Migración SQLite | Migración MySQL real |
|-------|----------------|---------|-----|------------------|----------------------|
| `works` | id, title, required_resource_id, owner_sub | idx_works_owner_sub | → resources (deferrable) | 001 | 001_baseline |
| `resources` | id, work_id, required_file_id, version_label, part_label, material_status, group_id, group_section_id | idx_resources_work, idx_resources_material, idx_resources_group_status | → works, → files | 001, 012, 013 | 001_baseline, 002_material, 003_material_groups |
| `files` | id, resource_id, folder_path, display_name, original_name, sha256, size_bytes, status | idx_files_resource, idx_files_status | → resources | 001, 012 | 001_baseline, 002_material |
| `creation_drafts` | id, owner_sub, source_kind (blank/osap/local), materialized_work_id | idx_creation_drafts_owner_status | → editor_source_tokens | 002, 005 | 001_baseline |
| `groups` | id, entity_id, name, slug, kind, description, status, editorial_mode, technical_description | uq_group_entity_name | → group_members, → events | 006, 015 | 001_baseline |
| `group_members` | id, group_id, user_sub, role, voice_code, voice_label, admin_role_id, musical_role_id, section_id | uq_group_member, idx_group_members_user | → groups | 006, 009, 010 | 001_baseline |
| `events` | id, group_id, entity_id, scope, kind, recurrence, series_id, creator_badge | idx_events_group_start, idx_events_entity_start, idx_events_series | → groups, → event_groups | 006, 014 | 001_baseline |
| `entity_leads` | id, entity_name, entity_kind, manager_*, contact_*, interests, status | idx_entity_leads_status | — | 007, 008 | 001_baseline |
| `messages` | id, group_id, sender_sub, scope, subject, body | idx_messages_group_created | → groups, → message_recipients | 009 | 001_baseline |
| `group_sections` | id, group_id, code, name, scope, parent_id, sort_order, active | uq_group_sections_code | → groups | 015 | 001_baseline |
| `group_articles` | id, legacy_id, group_id, title, slug, status, author_user_id, publisher_user_id | uq_group_articles_slug, idx_group_articles_group | → groups, → group_article_media | 015 | 001_baseline |

### 3.3 Migraciones MySQL reales necesarias (4 archivos)

| Archivo | Contenido | Origen |
|---------|-----------|--------|
| `001_baseline_schema.sql` | Esquema completo (renombrado de `001_schema.sql`) | Existente |
| `002_material_library.sql` | ALTER resources (version_label, part_label, material_status) + ALTER files (folder_path, display_name, original_name) + índices | SQLite 012 |
| `003_material_groups.sql` | ALTER resources (group_id, group_section_id) + índice | SQLite 013 |
| `004_coral_integration.sql` | 12 columnas coral en groups (trabajo independiente, **no autorizado aquí**) | Informe coral previo |

**Eliminar:** `002_agenda_recurrence.sql`, `003_group_articles.sql` (redundantes).

---

## 4. Baseline legacy corregido

### 4.1 Problemas del diseño v2

| Problema | Corrección |
|----------|------------|
| Verifica columnas de migraciones posteriores (material, coral) | Baseline **solo** verifica esquema histórico (001_baseline) |
| Cuenta 20 tablas pero enumera 21 | Conteo exacto: 20 tablas base |
| Registra migraciones posteriores sin ejecutarlas | **No registra** 002, 003, 004 — solo registra `001_baseline` + `999_legacy_baseline` |
| No produce error explícito si falla | `INSERT IGNORE` condicionado a `@legacy_ok=TRUE` |

### 4.2 Mecanismo baseline legacy (archivo `migrations/mysql/999_legacy_baseline.sql`)

```sql
-- Solo verifica esquema histórico (equivalente a SQLite 001-011, 014, 015)
-- NO verifica 012, 013 (material) ni 004 (coral)

CREATE TEMPORARY TABLE _legacy_verification (check_name VARCHAR(191), passed BOOLEAN);

-- 1. Tablas históricas (20)
INSERT INTO _legacy_verification
SELECT 'tables_exist', COUNT(*) = 20
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('works','resources','files','creation_drafts','editor_source_tokens',
    'library_items','collections','collection_items','oidc_states',
    'groups','group_members','events','event_groups','event_rsvps',
    'entity_leads','messages','message_recipients','event_targets',
    'group_sections','group_articles','group_article_media');

-- 2. Columnas críticas históricas (ej: group_members con roles)
INSERT INTO _legacy_verification
SELECT 'critical_columns', COUNT(*) >= 15
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND ((TABLE_NAME='group_members' AND COLUMN_NAME IN ('admin_role_id','musical_role_id','section_id','display_name'))
       OR (TABLE_NAME='events' AND COLUMN_NAME IN ('recurrence','recurrence_until','series_id','creator_badge'))
       OR (TABLE_NAME='groups' AND COLUMN_NAME IN ('slug','kind','description','status','editorial_mode')));

-- 3. FKs mínimas
INSERT INTO _legacy_verification
SELECT 'foreign_keys', COUNT(*) >= 12
FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = DATABASE() AND CONSTRAINT_TYPE='FOREIGN KEY';

-- 4. Evaluar y registrar SOLO si todo OK
SET @legacy_ok = (SELECT COUNT(*) FROM _legacy_verification WHERE passed=TRUE) = 3;

INSERT IGNORE INTO chorus_schema_migrations (name, applied_at)
SELECT '001_baseline_schema', UTC_TIMESTAMP() FROM DUAL WHERE @legacy_ok;

INSERT IGNORE INTO chorus_schema_migrations (name, applied_at)
SELECT '999_legacy_baseline', UTC_TIMESTAMP() FROM DUAL WHERE @legacy_ok;

DROP TEMPORARY TABLE _legacy_verification;
```

### 4.3 Comportamiento por tipo de instalación

| Tipo | Detección | Acción |
|------|-----------|--------|
| **Nueva MySQL** | Sin tablas, sin migraciones | Ejecuta 001→003 en orden, registra cada una |
| **Nueva SQLite** | Sin tablas, sin migraciones | Ejecuta 001-015 SQLite en orden |
| **Legacy compatible** | 20 tablas + columnas críticas + FKs + solo `mysql_schema_v1` | Ejecuta `999_legacy_baseline` → registra `001_baseline_schema` + `999_legacy_baseline` |
| **Legacy incompleta** | Faltan tablas/columnas/FKs | `999_legacy_baseline` falla (`@legacy_ok=FALSE`) → **no registra nada** → `initialise_database` intenta 001-003 (fallará con error claro) |
| **Ya actualizada** | 001_baseline_schema, 002, 003 registradas | No hace nada (idempotente) |

**Clave:** No se falsea historial. `999_legacy_baseline` registra explícitamente "reconocimiento de baseline", no ejecución.

---

## 5. Diseño de reconstrucción de osap_chorus_test

### 5.1 Realidad MariaDB DDL

> **MariaDB hace COMMIT implícito antes y después de cada DDL.** No hay rollback posible para DDL dentro de transacción.

### 5.2 Script `scripts/rebuild_test_db.py` — Especificación corregida

```python
#!/usr/bin/env python3
"""Reconstruye osap_chorus_test desde cero.
- autocommit=True (DDL se autocommit)
- Idempotente: DROP TABLE IF EXISTS + CREATE
- Verificación final OBLIGATORIA
- Exit != 0 si cualquier verificación falla
- NO usa transacción global para DDL
"""

MIGRATION_NAMES = [
    "001_baseline_schema",
    "002_material_library",
    "003_material_groups",
    # 004_coral_integration NO incluido — trabajo independiente
]

def _verify_schema(cursor, db_name: str) -> bool:
    """Verificación final exhaustiva."""
    checks = []

    # 1. Tablas esperadas (20 base)
    expected = {'chorus_schema_migrations','works','resources','files',
        'creation_drafts','editor_source_tokens','library_items',
        'collections','collection_items','oidc_states',
        'groups','group_members','events','event_groups',
        'event_rsvps','entity_leads','messages','message_recipients',
        'event_targets','group_sections','group_articles','group_article_media'}
    actual = {row[f"Tables_in_{db_name}"] for row in cursor.execute("SHOW TABLES").fetchall()}
    checks.append(("tables", expected.issubset(actual), f"Missing: {expected-actual}"))

    # 2. Columnas material (002)
    cursor.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='resources' AND COLUMN_NAME IN ('version_label','part_label','material_status','group_id','group_section_id')", (db_name,))
    got = {r['COLUMN_NAME'] for r in cursor.fetchall()}
    checks.append(("material_columns", got == {'version_label','part_label','material_status','group_id','group_section_id'}, f"Got: {got}"))

    # 3. Columnas files (002)
    cursor.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='files' AND COLUMN_NAME IN ('folder_path','display_name','original_name')", (db_name,))
    got = {r['COLUMN_NAME'] for r in cursor.fetchall()}
    checks.append(("file_columns", got == {'folder_path','display_name','original_name'}, f"Got: {got}"))

    # 4. FKs
    cursor.execute("SELECT COUNT(*) AS c FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=%s AND CONSTRAINT_TYPE='FOREIGN KEY'", (db_name,))
    checks.append(("foreign_keys", cursor.fetchone()['c'] >= 15, f"FK count: {cursor.fetchone()['c']}"))

    # 5. Migraciones registradas
    cursor.execute("SELECT name FROM chorus_schema_migrations")
    applied = {r['name'] for r in cursor.fetchall()}
    checks.append(("migrations", {'001_baseline_schema','002_material_library','003_material_groups'}.issubset(applied), f"Applied: {applied}"))

    return all(ok for _, ok, _ in checks)
```

**Puntos clave:**
- Cada migración se ejecuta en orden; si una falla, el script aborta (exit != 0)
- Estado parcial es recuperable reejecutando el script (idempotente)
- Verificación final en **nueva conexión** (ve estado committeado)
- No declara éxito parcial

---

## 6. Protección efectiva de tests

### 6.1 Diseño: Marcadores pytest + fixture selectiva

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -m 'not integration'"  # Default: SOLO unitarios
markers = [
    "unit: tests sin base de datos (default, rápidos)",
    "integration: tests que requieren MariaDB 10.4.32 real (osap_chorus_test)",
    "migrations: tests de migraciones específicamente",
]
```

```python
# tests/conftest.py
import os, pytest
from app.config import Settings
from app.db import connect as db_connect

def _get_effective_db(settings: Settings) -> str:
    conn = db_connect(settings)
    try:
        if settings.database_url:
            row = conn.execute("SELECT DATABASE() AS db").fetchone()
            return row["db"] if row else ""
        else:
            row = conn.execute("PRAGMA database_list").fetchone()
            return os.path.basename(row[2]) if row else "sqlite_memory"
    finally:
        conn.close()

def _verify_integration_config() -> Settings:
    """Verifica configuración REAL que usará create_app()."""
    settings = Settings.load()  # Misma carga que la app

    if not settings.database_url:
        raise RuntimeError("BLOQUEO: Tests integración requieren CHORUS_STORAGE_DATABASE_URL → MariaDB")

    effective_db = _get_effective_db(settings)
    if effective_db != "osap_chorus_test":
        raise RuntimeError(f"BLOQUEO: Conexión EFECTIVA apunta a '{effective_db}', se requiere 'osap_chorus_test'")

    return settings

@pytest.fixture
def integration_settings():
    """Solo para @pytest.mark.integration. Falla ANTES de cualquier test."""
    return _verify_integration_config()

@pytest.fixture
def migration_settings(integration_settings):
    return integration_settings

# NO hay autouse global — unit tests corren sin BD
```

### 6.2 Comportamiento verificado

| Comando | Tests que corren | BD requerida | Bloqueo si no hay MariaDB |
|---------|------------------|--------------|---------------------------|
| `pytest` | Solo `@pytest.mark.unit` (o sin marcador) | **No** | No |
| `pytest -m integration` | `@pytest.mark.integration` | **Sí** (osap_chorus_test) | **Sí** (RuntimeError claro) |
| `pytest -m migrations` | `@pytest.mark.migrations` | **Sí** | **Sí** |

**Verificaciones en `_verify_integration_config()`:**
1. `settings.database_url` no vacío → motor MariaDB
2. `SELECT DATABASE()` efectivo = `osap_chorus_test`
3. Mismo `Settings.load()` que usa `create_app()`

---

## 7. GitHub Actions — Configuración

```yaml
# .github/workflows/test.yml
jobs:
  unit-tests:
    name: Unit tests (no DB)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[test]"
      - run: pytest -m unit -x -q

  integration-tests:
    name: Integration tests (MariaDB 10.4)
    runs-on: ubuntu-latest
    # Sin contenedores: MariaDB 10.4 nativo via apt
    steps:
      - run: python scripts/rebuild_test_db.py
      - run: pytest -m migrations -x -v
```

**Puntos clave:**
- 3 jobs separados: unit (rápido), integration (completo), migrations (específico)
- MariaDB 10.4 exacto via service container
- `rebuild_test_db.py` obligatorio antes de cada job de integración
- Variable unificada: `CHORUS_STORAGE_DATABASE_URL`

---

## 8. Estado real de la integración móvil

### 8.1 Inventario

| Aspecto | Hallazgo |
|---------|----------|
| **Repositorio** | `D:\Proyectos\AI_OSAP\Chorus_movil\Chorus` — **VACÍO** (git init, 0 commits) |
| **Tecnología** | No verificada — no hay código |
| **Estructura** | No verificada |
| **Backend usado** | No verificado |
| **Configuración URL API** | No verificada |
| **Autenticación** | No verificada |
| **Almacenamiento local** | No verificado |
| **Descargas** | No verificado |
| **Sincronización offline** | No verificado |
| **Integración MuseEncore** | No verificada |

**Conclusión:** **NO EXISTE** aplicación móvil en el workspace actual. El repositorio está vacío. No se puede auditar integración móvil real.

### 8.2 Contratos API compartidos (Web ↔ Mobile teórico)

Basado en endpoints reales de `app/main.py`, la matriz de operaciones que **deberían** ser compartidas:

| Dominio | Endpoint | Método | Web usa | Mobile teórico | Formato entrada | Formato salida | Auth | Permisos |
|---------|----------|--------|---------|----------------|-----------------|----------------|------|----------|
| **Auth** | `/api/v1/auth/login` | POST | ✅ | ✅ | email, password | access_token, refresh_token | — | Público |
| **Auth** | `/api/v1/auth/oidc/start` | GET | ✅ | ✅ | — | authorize_url | — | Público |
| **Auth** | `/api/v1/auth/oidc/callback` | GET | ✅ | ✅ | code, state | Redirect + cookies | — | Público |
| **Auth** | `/api/v1/auth/refresh` | POST | ✅ | ✅ | cookie refresh | access_token | Cookie | Usuario |
| **Auth** | `/api/v1/auth/me` | GET | ✅ | ✅ | — | profile | Bearer | Usuario |
| **Grupos** | `/api/v1/groups` | POST | ✅ | ✅ | entity_id, name, timezone | group_dto | Bearer | Usuario |
| **Grupos** | `/api/v1/groups/{id}` | PATCH | ✅ | ✅ | name, timezone | group_dto | Bearer | Manager |
| **Grupos** | `/api/v1/groups/join` | POST | ✅ | ✅ | code | group_dto | Bearer | Usuario |
| **Grupos** | `/api/v1/groups/directory` | GET | ✅ | ✅ | — | list[group] | Bearer | Usuario |
| **Miembros** | `/api/v1/groups/{id}/members` | GET | ✅ | ✅ | — | list[member] | Bearer | Miembro |
| **Miembros** | `/api/v1/groups/{id}/members/{sub}` | PATCH | ✅ | ✅ | role, admin_role_id, musical_role_id, section_id, status | ok | Bearer | Manager |
| **Secciones** | `/api/v1/groups/{id}/catalog` | GET | ✅ | ✅ | — | {admin, musical, section} | Bearer | Miembro |
| **Agenda** | `/api/v1/events` | POST | ✅ | ✅ | group_id, kind, title, starts_at... | event_dto | Bearer | Manager |
| **Agenda** | `/api/v1/events/{id}` | PATCH | ✅ | ✅ | (mismos campos) | event_dto | Bearer | Manager |
| **Agenda** | `/api/v1/events/{id}` | DELETE | ✅ | ✅ | scope=single/series | deleted count | Bearer | Manager |
| **Agenda** | `/api/v1/events/{id}/rsvp` | POST | ✅ | ✅ | status (yes/no) | ok | Bearer | Miembro |
| **Agenda** | `/api/v1/agenda` | GET | ✅ | ✅ | — | {events[], groups[]} | Bearer | Usuario |
| **Mensajes** | `/api/v1/groups/{id}/messages` | GET | ✅ | ✅ | — | list[message] | Bearer | Miembro |
| **Mensajes** | `/api/v1/groups/{id}/messages` | POST | ✅ | ✅ | scope, subject, body, recipient_subs | message | Bearer | Miembro/Manager |
| **Mensajes** | `/api/v1/messages/{id}/reply` | POST | ✅ | ✅ | body, all | message | Bearer | Miembro |
| **Mensajes** | `/api/v1/messages/{id}/read` | POST | ✅ | ✅ | — | ok | Bearer | Destinatario |
| **Material** | `/api/v1/material/tree` | GET | ✅ | ✅ | group_id | tree | Bearer | Miembro |
| **Material** | `/api/v1/material/manifest` | GET | ✅ | ✅ | group_id | manifest (works→versions→files) | Bearer | Miembro |
| **Material** | `/api/v1/material/files/{id}/download` | GET | ✅ | ✅ | — | binary (MXL/PDF) | Bearer | Miembro |
| **Material** | `/api/v1/material/import` | POST | ✅ | ✅ | metadata (JSON) + files | import_result | Bearer | Manager |
| **Material** | `/api/v1/material/resources/{id}/publish` | POST | ✅ | ✅ | — | resource | Bearer | Manager |
| **Biblioteca** | `/api/v1/library` | GET | ✅ | ✅ | q | {items[], collections[]} | Bearer | Usuario |
| **Biblioteca** | `/api/v1/library/references` | POST | ✅ | ✅ | provider, work_id, title... | library_item | Bearer | Usuario |
| **Biblioteca** | `/api/v1/library/works/{id}` | POST | ✅ | ✅ | — | library_item | Bearer | Usuario |
| **Biblioteca** | `/api/v1/library/{id}/download` | GET | ✅ | ✅ | — | binary | Bearer | Usuario |
| **Artículos** | `/api/v1/groups/{id}/articles` | GET | ✅ | ✅ | — | list[article] | Bearer | Miembro |
| **Artículos** | `/api/v1/groups/{id}/articles` | POST | ✅ | ✅ | title, summary, body, event_date, media | article | Bearer | Manager |

**Incompatibilidades web/móvil identificadas:**
- Web usa cookies `same-origin` para refresh token; Android necesitará header `Authorization` + almacenamiento seguro local
- Web usa `window.opener.postMessage` para OIDC handoff; Android usará `Custom Tab` / `App Link`
- Web usa `credentials: "same-origin"` en fetch; Android debe enviar `Authorization: Bearer <token>` explícito
- **No hay APIs paralelas** — los contratos actuales son compartibles

---

## 9. Sincronización offline y MuseEncore

### 9.1 Material musical — Estado actual

| Funcionalidad | Backend | Web | Mobile |
|---------------|---------|-----|--------|
| **Árbol de obras** | `/api/v1/material/tree` ✅ | ✅ | ❌ (no existe app) |
| **Manifiesto sincronización** | `/api/v1/material/manifest` ✅ | ❌ | ❌ |
| **Descarga archivos** | `/api/v1/material/files/{id}/download` ✅ | ✅ | ❌ |
| **Integridad (sha256, size)** | En manifiesto y descarga ✅ | ✅ | ❌ |
| **Identificación obra/versión/parte** | work_id, resource_id (version_label, part_label), file_id ✅ | ✅ | ❌ |
| **Permisos por sección** | `group_section_id` en manifest filtra por `member.section_id` ✅ | ✅ | ❌ |
| **Estados material** | draft → reviewed → published ✅ | ✅ | ❌ |

**Mecanismo de sincronización:** Existe **manifiesto estructurado** (`/api/v1/material/manifest`) que devuelve:
```
group_id, generated_at, works[{work_id, title, versions[{resource_id, version_label, section_id, updated_at, files[{file_id, path, sha256, size_bytes, mime_type, download_url}]}]}]
```
**No hay** manifiesto de sincronización incremental (no hay `since` parameter ni etag). El cliente debe descargar manifiesto completo y comparar localmente.

### 9.2 MuseEncore — Intercambio actual

| Paso | Implementación | Estado |
|------|----------------|--------|
| **1. Entrega material** | `/api/v1/drafts/{id}/editor` → genera token temporal (5 min) → URL firmada `/api/v1/editor-sources/{token}/{filename}` → MuseEncore carga via `url=` param | ✅ Implementado |
| **2. URL temporal** | Token SHA256, expirable, CORS restringido a `editor_origin` | ✅ |
| **3. Regreso archivo** | `postMessage` tipo `chorus:score` con `ArrayBuffer` + `fileName` → `window.opener.postMessage` → web sube via `/api/v1/drafts/{id}/files` (multipart) | ✅ Parcial (requiere ventana padre) |
| **4. Subida manual** | Si no hay `window.opener` (p.ej. móvil), `editor.html` descarga `.mxl` y usuario debe subir manualmente en Chorus | ✅ Fallback implementado |
| **5. Automatización real** | **NO EXISTE** — no hay bridge automático móvil↔MuseEncore; web requiere intervención usuario | ❌ |

**Limitaciones documentadas:**
- Flujo `guardar y cerrar` solo funciona en web con `window.opener`
- Android no puede usar `window.opener` → requeriría `Custom Tab` + deep link de retorno o upload manual
- No hay sincronización automática de cambios en MuseEncore → Chorus

---

## 10. Problemas anteriores resueltos y pendientes

### 10.1 Resueltos (en este análisis)

| Problema | Resolución |
|----------|------------|
| Migraciones MySQL monolíticas vs incrementales | 4 migraciones reales identificadas (001_baseline, 002_material, 003_material_groups, 004_coral) |
| Baseline legacy falseando historial | `999_legacy_baseline` verifica y registra solo reconocimiento honesto |
| Protección tests via env var | Fixture `integration_settings` verifica conexión EFECTIVA (`SELECT DATABASE()`) |
| Variable de entorno inconsistente | Unificada a `CHORUS_STORAGE_DATABASE_URL` (real en `Settings.load()`) |
| Transacción DDL en rebuild | `autocommit=True`, verificación final en nueva conexión |
| Tests unitarios vs integración | Marcadores pytest `unit`/`integration`/`migrations`, default sin BD |
| Migraciones 002/003 redundantes | Eliminadas; contenido real en 002_material, 003_material_groups |

### 10.2 Pendientes / No verificados

| Problema | Estado |
|----------|--------|
| **Aplicación móvil** | **NO EXISTE** en workspace — repositorio vacío |
| Integración OIDC Android | No verificado (no hay app) |
| Sincronización offline incremental | No implementado (manifiesto completo only) |
| Bridge automático MuseEncore↔Android | No implementado |
| Tests de contratos web/mobile | No aplicable (no hay mobile) |
| `doc` undefined en `oidc_callback` | **NO ENCONTRADO** — código actual limpio (líneas 1020-1053) |
| Cookies vs Bearer en Android | No verificado |

---

## 11. Incompatibilidades web/Android (teóricas)

| Área | Web | Android (requerido) | Brecha |
|------|-----|---------------------|--------|
| **Auth transport** | Cookies `httponly` + `same-origin` | Header `Authorization: Bearer` + Secure Storage | Implementar `TokenManager` en Android |
| **OIDC flow** | `window.opener.postMessage` + redirect | Chrome Custom Tab + App Link / Deep link | Requiere `intent-filter` y callback nativo |
| **Refresh token** | Cookie automática en fetch | Llamada explícita `/api/v1/auth/refresh` | `TokenInterceptor` en cliente HTTP |
| **File download** | `fetch` + `blob` + `anchor.click()` | `DownloadManager` o `OkHttp` + almacenamiento scoped | Adaptar descarga binaria |
| **MuseEncore** | Iframe + `postMessage` + `window.opener` | Custom Tab + deep link retorno O upload manual | Sin `window.opener` en Android |
| **Notificaciones** | In-app (campana) + email | Push (FCM) + in-app | Requiere endpoint registro token push |

**Regla:** No crear APIs paralelas. Extender contratos actuales con parámetros opcionales.

---

## 12. Cambios necesarios, ordenados por gravedad

### Críticos (Bloquean dev/test/prod separation)

| # | Cambio | Archivos | Fase |
|---|--------|----------|------|
| 1 | Renombrar `001_schema.sql` → `001_baseline_schema.sql` | `migrations/mysql/001_baseline_schema.sql` | 1 |
| 2 | Crear `002_material_library.sql` (desde SQLite 012) | `migrations/mysql/002_material_library.sql` | 1 |
| 3 | Crear `003_material_groups.sql` (desde SQLite 013) | `migrations/mysql/003_material_groups.sql` | 1 |
| 4 | Crear `999_legacy_baseline.sql` (verificación honesta) | `migrations/mysql/999_legacy_baseline.sql` | 1 |
| 5 | Eliminar `002_agenda_recurrence.sql`, `003_group_articles.sql` | `migrations/mysql/` | 1 |
| 6 | Reescribir `initialise_database()` con detección legacy + bucle 001-003 | `app/main.py:477-526` | 1 |
| 7 | Añadir `_execute_sql_script()` con `sqlparse` + helpers legacy | `app/db.py` | 1 |
| 8 | Crear `scripts/rebuild_test_db.py` (idempotente, verificación final) | `scripts/rebuild_test_db.py` | 1 |
| 9 | Añadir `sqlparse` a `pyproject.toml` `[dev]`, `[test]` | `pyproject.toml` | 1 |
| 10 | Crear `tests/conftest.py` con `integration_settings` (verificación efectiva) | `tests/conftest.py` | 2 |
| 11 | Actualizar `pyproject.toml` marcadores + `addopts` | `pyproject.toml` | 2 |
| 12 | Marcar tests API existentes con `@pytest.mark.integration` + fixture | `tests/test_agenda.py`, `test_articles.py`, `test_messages.py`, `test_material.py`, `test_entity_leads.py` | 2 |

### Altos (Tests de esquema/constraints → MariaDB)

| # | Cambio | Archivos | Fase |
|---|--------|----------|------|
| 13 | Reescribir `test_creation_drafts.py` para MariaDB (`information_schema`, `pymysql.err.IntegrityError`) | `tests/test_creation_drafts.py` | 3 |
| 14 | Reescribir `test_v6_schema.py` igual | `tests/test_v6_schema.py` | 3 |
| 15 | Reescribir `test_oidc.py` igual | `tests/test_oidc.py` | 3 |
| 16 | Reescribir `test_library_integrity.py` igual | `tests/test_library_integrity.py` | 3 |
| 17 | Reescribir `test_api_runtime.py::test_database_migrations_are_repeatable` para MariaDB | `tests/test_api_runtime.py` | 3 |
| 18 | Tests MXL en `test_api_runtime.py` → `@pytest.mark.unit` | `tests/test_api_runtime.py` | 3 |

### Medios (CI/CD)

| # | Cambio | Archivos | Fase |
|---|--------|----------|------|
| 19 | Crear `.github/workflows/test.yml` (3 jobs) | `.github/workflows/test.yml` | 4 |

### Independiente (Coral integration — NO AUTORIZADO AQUÍ)

| # | Cambio | Archivos | Fase |
|---|--------|----------|------|
| 20 | `004_coral_integration.sql` + modelos API + frontend | Trabajo separado | — |

---

## 13. Archivos que habría que modificar (lista consolidada)

### Migraciones MySQL (6 archivos)
1. `migrations/mysql/001_baseline_schema.sql` — **RENOMBRAR** desde `001_schema.sql`
2. `migrations/mysql/002_material_library.sql` — **NUEVO** (SQLite 012)
3. `migrations/mysql/003_material_groups.sql` — **NUEVO** (SQLite 013)
4. `migrations/mysql/004_coral_integration.sql` — **NUEVO** (trabajo independiente)
5. `migrations/mysql/999_legacy_baseline.sql` — **NUEVO** (baseline honesto)
6. **ELIMINAR** `migrations/mysql/002_agenda_recurrence.sql`, `003_group_articles.sql`

### Código aplicación (3 archivos)
7. `app/main.py` — `initialise_database()` reescrito (líneas 477-526)
8. `app/db.py` — `_execute_sql_script()`, `_detect_legacy_installation()`, `_ensure_migrations_table()`
9. `app/config.py` — Sin cambios (ya correcto)

### Scripts (1 archivo)
10. `scripts/rebuild_test_db.py` — **NUEVO**

### Tests (8 archivos)
11. `tests/conftest.py` — **NUEVO** (fixtures `integration_settings`, `migration_settings`)
12. `pyproject.toml` — `sqlparse` en `[dev]`/`[test]`, marcadores, `addopts`
13. `tests/test_agenda.py` — `@pytest.mark.integration`, fixture `integration_settings`
14. `tests/test_articles.py` — igual
15. `tests/test_messages.py` — igual
16. `tests/test_material.py` — igual
17. `tests/test_entity_leads.py` — igual
18. `tests/test_creation_drafts.py` — **REESCRIBIR** para MariaDB + `@pytest.mark.integration @pytest.mark.migrations`
19. `tests/test_v6_schema.py` — **REESCRIBIR** igual
20. `tests/test_oidc.py` — **REESCRIBIR** igual
21. `tests/test_library_integrity.py` — **REESCRIBIR** igual
22. `tests/test_api_runtime.py` — Separar unit/integration

### CI/CD (1 archivo)
23. `.github/workflows/test.yml` — **NUEVO** (3 jobs)

### Documentación (1 archivo)
24. `docs/mysql.md` — Actualizar: 4 migraciones, baseline, variables, permisos

---

## 14. Fases de implementación

| Fase | Descripción | Entregables | Criterio de salida |
|------|-------------|-------------|---------------------|
| **1. Fundación BD** | Migraciones reales, baseline legacy, rebuild script, helpers SQL | Items 1-9 | `CHORUS_STORAGE_DATABASE_URL=.../osap_chorus_test python -c "from app.main import initialise_database; from app.config import Settings; initialise_database(Settings.load())"` registra 001, 002, 003; `rebuild_test_db.py` exit 0 |
| **2. Infraestructura tests** | conftest, marcadores, reclasificar tests API | Items 10-12 | `pytest` (solo unit, <5s); `CHORUS_STORAGE_DATABASE_URL=.../osap_chorus_test pytest -m integration` pasa tests API |
| **3. Tests esquema** | Reescribir 5 tests para MariaDB real | Items 13-18 | `pytest -m migrations` 100% pass en MariaDB |
| **4. CI/CD** | GitHub Actions 3 jobs | Item 19 | Push a main → 3 jobs verdes |
| **5. Coral (separado)** | Migración 004 + API + frontend | Item 20 | Autorización separada |

---

## 15. Criterios de aceptación verificables

| ID | Criterio | Comando de verificación | Esperado |
|----|----------|------------------------|----------|
| **CA-01** | 4 migraciones MySQL reales existen | `ls migrations/mysql/00[1-4]_*.sql \| wc -l` | 4 |
| **CA-02** | Baseline legacy existe | `ls migrations/mysql/999_legacy_baseline.sql` | Existe |
| **CA-03** | Migraciones redundantes eliminadas | `ls migrations/mysql/002_agenda_recurrence.sql` | No existe |
| **CA-04** | Instalación nueva MySQL registra 001-003 | Ver sección 14 Fase 1 | 3 filas en `chorus_schema_migrations` |
| **CA-05** | Legacy compatible registra baseline honesto | Ver sección 14 Fase 1 | 2 filas: `001_baseline_schema`, `999_legacy_baseline` |
| **CA-06** | Legacy incompleta NO registra baseline | Ver sección 14 Fase 1 | Solo `mysql_schema_v1` |
| **CA-07** | `rebuild_test_db.py` reconstruye y verifica | `CHORUS_STORAGE_DATABASE_URL=.../osap_chorus_test python scripts/rebuild_test_db.py` | Exit 0, verificación OK |
| **CA-08** | `rebuild_test_db.py` falla si migración falla | Corromper migración → ejecutar | Exit != 0 |
| **CA-09** | Tests unitarios corren sin BD | `pytest` | ≥5 tests pass, <5s, sin conexión BD |
| **CA-10** | Tests integración bloqueados sin MariaDB | `unset CHORUS_STORAGE_DATABASE_URL && pytest -m integration` | `RuntimeError` claro |
| **CA-11** | Tests integración corren con MariaDB | `CHORUS_STORAGE_DATABASE_URL=.../osap_chorus_test pytest -m integration` | 100% pass |
| **CA-12** | GitHub Actions 3 jobs verdes | Push a main | Unit + Integration + Migrations = pass |
| **CA-13** | Sin secrets en repo | `git grep -rE "(password|secret)" -- "*.toml" "*.py" \| grep -v "CHORUS_" \| grep -v "testpass" \| grep -v "placeholder"` | Sin resultados |
| **CA-14** | Variable unificada `CHORUS_STORAGE_DATABASE_URL` | `grep -r "CHORUS_DATABASE_URL" -- "*.py" "*.md" "*.yml" \| grep -v "CHORUS_STORAGE_DATABASE_URL"` | Solo referencias históricas documentadas |

---

## 16. Conclusiones y declaraciones de no verificado

### Confirmado (verificado en código real)

1. **Chorus 0.14.0** tiene backend completo, web SPA, dual SQLite/MySQL, 15 migraciones SQLite, 3 MySQL (1 real + 2 redundantes).
2. **Migraciones MySQL reales necesarias:** 4 (001_baseline, 002_material, 003_material_groups, 004_coral).
3. **Baseline legacy** debe verificar solo esquema histórico y registrar honestamente.
4. **Reconstrucción test DB** requiere `autocommit=True`, verificación final, idempotencia.
5. **Protección tests** via fixture selectiva verificando conexión efectiva (`SELECT DATABASE()`).
6. **Variable de entorno real:** `CHORUS_STORAGE_DATABASE_URL` (no `CHORUS_DATABASE_URL`).
7. **GitHub Actions** con MariaDB 10.4 service container, 3 jobs separados.
8. **Contratos API** web son completos y compartibles; no requieren APIs paralelas.
9. **Manifiesto material** existe (`/api/v1/material/manifest`) para sincronización.
10. **MuseEncore bridge** implementado para web (token temporal + postMessage), fallback descarga manual.

### NO VERIFICADO (declarado expresamente)

| Tema | Motivo |
|------|--------|
| **Aplicación móvil completa** | Repositorio `Chorus_movil/Chorus` está **vacío** (0 commits) |
| Código móvil (Kotlin/Flutter/React Native) | No existe en workspace |
| Autenticación OIDC en Android | No hay app para auditar |
| Almacenamiento local / descargas / sync offline | No hay app |
| Integración MuseEncore en Android | No hay app |
| Pruebas conjuntas web/Android | No hay app |
| Error `doc` undefined en `oidc_callback` | **NO ENCONTRADO** en código actual (líneas 1020-1053 `app/main.py`) |
| Cookies vs Bearer en Android | No hay app |
| Cambio de grupo activo en móvil | No hay app |
| Resolución de conflictos sync | No hay app |
| Manifiesto sincronización incremental | Backend no expone `since`/etag |

---

**Fin de la auditoría técnica definitiva.**

**Próximo paso:** Revisión y autorización para implementar Fase 1 (fundación BD).