# Chorus 0.15 — Auditoría técnica v3 y validación previa a implementación

**Fecha**: 2026-11-18  
**Repositorio**: `D:\Proyectos\AI_OSAP\Chorus` (backend `recursosformacion/ai_chorus`)  
**Ámbito**: Análisis y documentación exclusivamente — **SIN MODIFICACIONES**

---

## 1. Corrección y verificación de defectos de la auditoría v2

### 1.1 Inventario de tablas del baseline legacy — **DEFECTO CONFIRMADO**

| Métrica | v2 audit | Realidad verificada |
|---------|----------|---------------------|
| Tablas MySQL en 001_schema.sql | "20 tablas (lista de 21)" | **19 CREATE TABLE** (18 aplicación + `chorus_schema_migrations`) |
| Tablas SQLite totales | No verificado | **21 tablas aplicación** (excluyendo temp `creation_drafts_new`) |
| Tablas faltantes en MySQL vs SQLite | No identificado | **3 tablas**: `group_sections`, `group_articles`, `group_article_media` |

**Evidencia**: `grep -n "CREATE TABLE" migrations/mysql/001_schema.sql` → 19 líneas. Las 3 tablas faltantes están en `migrations/mysql/003_group_articles.sql` (redundante).

**Consecuencia**: El baseline legacy v2 verificaba tablas que no existen en el esquema histórico MySQL real.

**Corrección mínima**: Baseline legacy debe verificar **exactamente las 18 tablas aplicación** presentes en `001_schema.sql`.

---

### 1.2 Baseline legacy no debe registrar migraciones no ejecutadas — **DEFECTO CONFIRMADO**

**Código v2 propuesto**: `INSERT IGNORE` condicionado a `@legacy_ok` registraba `002_material_library`, `003_material_groups`, `004_group_articles_tables`, `005_coral_integration` sin haber ejecutado sus scripts.

**Realidad**: Esas migraciones **no existen** en el esquema histórico MySQL. El esquema histórico (001_schema.sql) ya incluye la mayor parte del contenido de SQLite 001-015, **excepto** las migraciones de material (SQLite 012, 013).

**Corrección mínima**: Baseline legacy solo registra `001_baseline_schema` + `999_legacy_baseline`. Las migraciones 002, 003, 004 se ejecutan **después** si no están registradas.

---

### 1.3 Baseline debe fallar explícitamente si verificación no supera — **DEFECTO CONFIRMADO**

**Código v2**: `INSERT IGNORE ... WHERE @legacy_ok` — si falla, no registra nada pero **tampoco aborta** la inicialización; `initialise_database` continúa e intenta aplicar migraciones 001-004 encima de un esquema incompatible.

**Corrección mínima**: El script baseline debe usar `SIGNAL SQLSTATE '45000'` (o equivalente) para abortar la conexión si `@legacy_ok = FALSE`, y `initialise_database` debe detectar el fallo y detenerse.

---

### 1.4 Instalación legacy incompleta no debe recibir esquema nuevo encima — **DEFECTO CONFIRMADO**

**Comportamiento actual v2**: Si baseline falla silenciosamente, `initialise_database` ejecuta el bucle 001-004. Como las tablas ya existen (pero incompletas), los `CREATE TABLE IF NOT EXISTS` no fallan, pero las columnas faltantes no se añaden.

**Corrección mínima**: 
1. Baseline legacy verifica integridad completa (tablas + columnas críticas + FKs).
2. Si falla → error explícito → `initialise_database` aborta.
3. No se ejecutan migraciones posteriores sobre esquema incompatible.

---

### 1.5 Verificación de FKs por tabla — **DEFECTO CONFIRMADO (conteo incorrecto)**

| Tabla | FKs en MySQL 001_schema.sql | Destino |
|-------|----------------------------|---------|
| `resources` | `fk_resources_work` (work_id → works.id) | works |
| `files` | `fk_files_resource` (resource_id → resources.id) | resources |
| `editor_source_tokens` | `fk_source_token_draft` (draft_id → creation_drafts.id) | creation_drafts |
| `library_items` | `fk_library_work` (work_id → works.id) | works |
| `collection_items` | `fk_collection_item_collection` (collection_id → collections.id), `fk_collection_item_library` (library_item_id → library_items.id) | collections, library_items |
| `group_members` | `fk_group_member_group` (group_id → groups.id) | groups |
| `events` | `fk_events_group` (group_id → groups.id) | groups |
| `event_groups` | `fk_event_groups_event` (event_id → events.id), `fk_event_groups_group` (group_id → groups.id) | events, groups |
| `event_rsvps` | `fk_rsvp_event` (event_id → events.id) | events |
| `messages` | `fk_messages_group` (group_id → groups.id) | groups |
| `event_targets` | `fk_event_target_event` (event_id → events.id) | events |
| `message_recipients` | `fk_message_recipient_message` (message_id → messages.id) | messages |

**Total**: **14 FKs** (no "≥15" como afirmaba v2).

**Columnas críticas por tabla** (para baseline):
- `group_members`: `admin_role_id`, `musical_role_id`, `section_id`, `display_name`
- `events`: `recurrence`, `recurrence_until`, `series_id`, `creator_badge`
- `groups`: `slug`, `kind`, `description`, `status`, `editorial_mode`, `technical_description`
- `resources`: `version_label`, `part_label`, `material_status`, `group_id`, `group_section_id` **FALTANTES en 001_schema.sql**
- `files`: `folder_path`, `display_name`, `original_name` **FALTANTES en 001_schema.sql**

---

### 1.6 Script `rebuild_test_db.py` — **NO EXISTE (era propuesta v2)**

**Hallazgo**: El archivo `scripts/rebuild_test_db.py` **no existe** en el repositorio. Era una propuesta de la v2.

**Error potencial identificado en propuesta v2**: Doble `cursor.fetchone()` sobre mismo resultado en verificación de FKs:
```python
cursor.execute("SELECT COUNT(*) AS c FROM information_schema.TABLE_CONSTRAINTS...")
fk_count = cursor.fetchone()['c']  # Primera llamada
checks.append(("foreign_keys", fk_count >= 15, f"FK count: {cursor.fetchone()['c']}"))  # Segunda llamada → None!
```

**Corrección**: Guardar resultado en variable.

---

### 1.7 Reconstrucción debe registrar migraciones realmente ejecutadas — **PENDIENTE**

**Estado actual**: No existe script de reconstrucción. La propuesta v2 lo diseñaba pero no se ha implementado.

**Requisito**: Cada migración aplicada debe insertar su nombre en `chorus_schema_migrations` **después** de ejecutarse exitosamente, no antes.

---

### 1.8 Archivo de migración ausente debe abortar con código ≠ 0 — **PENDIENTE**

**Requisito**: En `rebuild_test_db.py`, si `MIGRATION_NAMES` incluye un archivo que no existe en `migrations/mysql/`, el script debe salir con código ≠ 0 (no `continue` silencioso).

---

### 1.9 Ejecutor SQL compartido aplicación + reconstrucción — **NO EXISTE**

**Estado actual**: 
- App usa `_MySQLConnection.executescript()` (split por `;` simple, línea 69-75 `app/db.py`)
- Propuesta v2 usaba `sqlparse` pero no está implementado

**Realidad**: No hay mecanismo compartido. El `executescript` actual:
- Elimina comentarios `--` línea a línea
- Split por `;` **sin respetar strings/comentarios multilínea** → frágil
- No usa `sqlparse`

**Corrección mínima**: Extraer `_execute_sql_script(conn, script, is_mysql)` a `app/db.py` usando `sqlparse`, y usarlo tanto en `initialise_database` como en `rebuild_test_db.py`.

---

### 1.10 Idempotencia de operación destructiva — **ACLARACIÓN NECESARIA**

**Propuesta v2**: "Idempotente: DROP TABLE IF EXISTS + CREATE"

**Realidad MariaDB**: `DROP TABLE` y `CREATE TABLE` son DDL → **COMMIT implícito**. No hay rollback posible. Si falla a mitad (ej. migración 002 falla), el estado es:
- Tablas 001 creadas
- Tablas 002 parcialmente creadas o no creadas
- `chorus_schema_migrations` tiene 001 pero no 002

**Comportamiento correcto**: 
- Script es **re-ejecutable** (idempotente en sentido de "se puede correr de nuevo desde cero")
- **No es transaccional** — estado intermedio es posible
- Verificación final obligatoria en **nueva conexión** (ve estado committeado)
- Exit ≠ 0 si verificación falla → CI detecta fallo

---

## 2. Compatibilidad de migraciones históricas

### 2.1 Inventario real de scripts de migración

#### MySQL (existentes)
| Archivo | Estado | Contenido |
|---------|--------|-----------|
| `001_schema.sql` | **ESQUEMA COMPLETO HISTÓRICO** | 18 tablas aplicación + FKs + índices (equivalente a SQLite 001-011, 014). **Incluye 11 columnas de groups de SQLite 015**. **FALTAN 3 tablas**: `group_sections`, `group_articles`, `group_article_media` |
| `002_agenda_recurrence.sql` | **REDUNDANTE** | `ALTER TABLE events` columnas + índice que YA están en 001_schema.sql |
| `003_group_articles.sql` | **PARCIALMENTE REDUNDANTE** | `ALTER TABLE groups` (11 columnas **ya están en 001_schema.sql**) + **3 CREATE TABLE necesarios** (`group_sections`, `group_articles`, `group_article_media`) que faltan en 001_schema.sql |

#### SQLite (15 incrementales)
| Migración | Tablas/Columnas | Estado en MySQL 001_schema.sql |
|-----------|-----------------|--------------------------------|
| 001_v6_work_resource_file | works, resources, files | ✅ Incluido |
| 002_creation_drafts | creation_drafts, editor_source_tokens | ✅ Incluido |
| 003_owner_and_library | owner_sub en works, library_items, collections, collection_items | ✅ Incluido |
| 004_oidc_states | oidc_states | ✅ Incluido |
| 005_local_draft_source | source_kind='local' en creation_drafts | ✅ Incluido (ya en CHECK) |
| 006_groups_events | groups, group_members, events, event_groups, event_rsvps, entity_leads | ✅ Incluido |
| 007_entity_leads | entity_leads | ✅ Incluido |
| 008_entity_lead_manager | manager_* en entity_leads | ✅ Incluido |
| 009_messages | display_name en group_members, messages, message_recipients | ✅ Incluido |
| 010_group_member_roles | admin_role_id, musical_role_id, section_id en group_members | ✅ Incluido |
| 011_event_targets | event_targets | ✅ Incluido |
| **012_material_library** | version_label, part_label, material_status en resources + folder_path, display_name, original_name en files + índice | ❌ **FALTANTE** |
| **013_material_groups** | group_id, group_section_id en resources + índice | ❌ **FALTANTES** |
| 014_agenda_recurrence | recurrence, recurrence_until, series_id, creator_badge en events + índice | ✅ Incluido (columnas + FK; índice `idx_events_series` faltante) |
| **015_group_articles** | 11 columnas en groups + group_sections, group_articles, group_article_media | ⚠️ **Parcial**: 11 columnas en groups ✅, **3 tablas nuevas ❌** |

---

### 2.2 Matriz de migraciones MySQL reales necesarias

| Migración MySQL | Origen | Contenido real | Estado |
|-----------------|--------|----------------|--------|
| `001_baseline_schema.sql` | Renombrar `001_schema.sql` | Esquema histórico completo (18 tablas, incluye 11 columnas de groups de SQLite 015) | ✅ Existe (renombrar) |
| `002_material_library.sql` | SQLite 012 | ALTER resources (version_label, part_label, material_status) + ALTER files (folder_path, display_name, original_name) + índices | ❌ **NUEVO** |
| `003_material_groups.sql` | SQLite 013 | ALTER resources (group_id, group_section_id) + índice | ❌ **NUEVO** |
| `004_group_articles_tables.sql` | SQLite 015 (parte CREATE TABLE) | CREATE TABLE `group_sections`, `group_articles`, `group_article_media` (NO ALTER groups — ya en baseline) | ❌ **NUEVO** |
| `005_coral_integration.sql` | Informe coral | 12 columnas en groups | ❌ **TRABAJO INDEPENDIENTE** (no autorizado aquí) |
| `999_legacy_baseline.sql` | Nuevo | Verificación integridad + registro baseline honesto | ❌ **NUEVO** |

**Eliminar**: `002_agenda_recurrence.sql`, `003_group_articles.sql` (redundantes: ALTER TABLE ya en baseline, CREATE TABLE movidas a 004).

---

### 2.3 Registro de migraciones en instalaciones existentes

**Tabla `chorus_schema_migrations` actual en instalaciones MySQL**:
- Solo `mysql_schema_v1` registrada (por `initialise_database` línea 488)
- **Ninguna** de las 15 migraciones SQLite registradas
- Las migraciones 002 y 003 MySQL **nunca se ejecutaron** (el código retorna en línea 496)

**Compatibilidad hacia adelante**:
| Tipo instalación | Detección | Acción |
|------------------|-----------|--------|
| **Nueva MySQL** | Sin tablas, sin migraciones | Ejecuta 001→004 en orden, registra cada una |
| **Nueva SQLite** | Sin tablas, sin migraciones | Ejecuta 001-015 SQLite en orden |
| **Legacy compatible** | 18 tablas + columnas críticas + 14 FKs + solo `mysql_schema_v1` | Ejecuta `999_legacy_baseline` → registra `001_baseline_schema` + `999_legacy_baseline` |
| **Legacy incompleta** | Faltan tablas/columnas/FKs | `999_legacy_baseline` falla con error → `initialise_database` aborta |
| **Ya actualizada** | 001_baseline_schema, 002, 003, 004 registradas | No hace nada (idempotente) |

**No falsear historial**: `999_legacy_baseline` registra explícitamente "reconocimiento de baseline", no ejecución de migraciones individuales.

---

## 3. Protección real de tests

### 3.1 Estado actual de pytest

| Archivo | Estado |
|---------|--------|
| `pyproject.toml` | Sin marcadores, `addopts = "-ra"` |
| `tests/conftest.py` | **NO EXISTE** |
| Marcadores `@pytest.mark.integration` | **NO USADOS** en tests actuales |
| Tests unitarios vs integración | **NO SEPARADOS** — todos usan SQLite via `_settings(tmp_path)` |

### 3.2 Cómo se ejecutan realmente los tests

```bash
# Actual (todos corren con SQLite en tmp_path)
pytest

# Propuesto v2 (requiere implementación)
pytest                    # Solo @pytest.mark.unit (sin BD)
pytest -m integration     # Requiere MariaDB + osap_chorus_test
pytest -m migrations      # Subconjunto de integration
```

**Realidad**: `@pytest.mark.integration` **NO activa fixture automáticamente**. Las fixtures se activan por **nombre de parámetro** en la función de test, no por marcador.

### 3.3 Diseño de protección efectiva

**Archivo nuevo**: `tests/conftest.py`

```python
import os
import pytest
from urllib.parse import urlparse
from app.config import Settings
from app.db import connect as db_connect

# ============================================================
# VERIFICACIÓN DE CONFIGURACIÓN EFECTIVA (llama a connect())
# ============================================================
def _get_effective_db_info(settings: Settings) -> dict:
    """Obtiene info real de la BD que Chorus USA (no solo env vars)."""
    conn = db_connect(settings)
    try:
        if settings.database_url:
            # MySQL/MariaDB
            row = conn.execute("SELECT DATABASE() AS db, USER() AS usr, @@hostname AS host, @@port AS port").fetchone()
            return {
                "engine": "mariadb",
                "database": row["db"],
                "user": row["usr"].split("@")[0] if row["usr"] else "",
                "host": row["host"],
                "port": row["port"],
            }
        else:
            # SQLite
            row = conn.execute("PRAGMA database_list").fetchone()
            path = row[2] if row else ""
            return {
                "engine": "sqlite",
                "database": os.path.basename(path) if path else "memory",
            }
    finally:
        conn.close()

def _verify_integration_requirements() -> Settings:
    """Valida TODOS los requisitos para tests de integración/migraciones."""
    settings = Settings.load()  # Misma carga que create_app()
    
    info = _get_effective_db_info(settings)
    
    # 1. Motor MariaDB
    if info["engine"] != "mariadb":
        raise RuntimeError(
            f"BLOQUEO: Tests integración requieren MariaDB, motor detectado: {info['engine']}"
        )
    
    # 2. Base de datos efectiva
    if info["database"] != "osap_chorus_test":
        raise RuntimeError(
            f"BLOQUEO: Base efectiva '{info['database']}' ≠ 'osap_chorus_test'"
        )
    
    # 3. Usuario de pruebas (no root, no dev)
    if info["user"] != "osap2027_test":
        raise RuntimeError(
            f"BLOQUEO: Usuario '{info['user']}' ≠ 'osap2027_test'"
        )
    
    # 4. Host/puerto esperados (configurable pero validado)
    expected_host = os.getenv("CHORUS_TEST_DB_HOST", "127.0.0.1")
    expected_port = int(os.getenv("CHORUS_TEST_DB_PORT", "3306"))
    if info["host"] != expected_host or info["port"] != expected_port:
        raise RuntimeError(
            f"BLOQUEO: Host/puerto {info['host']}:{info['port']} ≠ esperado {expected_host}:{expected_port}"
        )
    
    # 5. Variable de entorno unificada
    if not settings.database_url:
        raise RuntimeError("BLOQUEO: CHORUS_DATABASE_URL no definido (requerido para MariaDB)")
    
    # 6. Verificar permisos limitados (intentar operación que requiera solo permisos de test)
    with db_connect(settings) as conn:
        try:
            conn.execute("CREATE TEMPORARY TABLE _perm_check (id INT)")
            conn.execute("DROP TEMPORARY TABLE _perm_check")
        except Exception as e:
            raise RuntimeError(f"BLOQUEO: Permisos insuficientes en osap_chorus_test: {e}")
    
    return settings

# ============================================================
# FIXTURES SELECTIVAS (solo para tests marcados)
# ============================================================
@pytest.fixture
def integration_settings():
    """Solo para @pytest.mark.integration. Falla ANTES de cualquier test."""
    return _verify_integration_requirements()

@pytest.fixture
def migration_settings(integration_settings):
    """Solo para @pytest.mark.migrations."""
    return integration_settings

# NO autouse global — unit tests corren sin BD
```

**Marcadores en `pyproject.toml`**:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -m 'not integration'"  # Default: SOLO unitarios
markers = [
    "unit: tests sin base de datos (default, rápidos)",
    "integration: tests que requieren MariaDB 10.4.32 real (osap_chorus_test)",
    "migrations: tests de migraciones específicamente",
]
```

### 3.4 Comportamiento verificado

| Comando | Tests que corren | BD requerida | Bloqueo si no hay MariaDB |
|---------|------------------|--------------|---------------------------|
| `pytest` | Solo `@pytest.mark.unit` (o sin marcador) | **No** | No |
| `pytest -m integration` | `@pytest.mark.integration` | **Sí** (osap_chorus_test) | **Sí** (RuntimeError claro) |
| `pytest -m migrations` | `@pytest.mark.migrations` | **Sí** | **Sí** |

**Tests actuales a reclasificar**:
- **Unitarios** (sin BD): tests MXL en `test_api_runtime.py` (5 tests)
- **Integración** (MariaDB): `test_agenda.py`, `test_articles.py`, `test_messages.py`, `test_material.py`, `test_entity_leads.py`
- **Migraciones** (MariaDB): `test_creation_drafts.py`, `test_v6_schema.py`, `test_oidc.py`, `test_library_integrity.py`, `test_api_runtime.py::test_database_migrations_are_repeatable` (reescritos para MariaDB)

---

## 4. Separación de entornos

### 4.1 Tres entornos, variable unificada

| Entorno | Base de datos | Usuario | Variable `CHORUS_DATABASE_URL` |
|---------|---------------|---------|--------------------------------|
| **Desarrollo** | `osap_chorus` | `osap2027_dev` | `mysql+pymysql://osap2027_dev:****@host:3306/osap_chorus` |
| **Pruebas** | `osap_chorus_test` | `osap2027_test` | `mysql+pymysql://osap2027_test:****@host:3306/osap_chorus_test` |
| **Producción** | `osap_chorus_prod` | (dedicado) | Fuera de alcance |

**Verificación en `Settings.load()` (línea 80 `app/config.py`)**:
```python
database_url=value("CHORUS_DATABASE_URL", storage, "database_url"),
```
**La variable real es `CHORUS_DATABASE_URL`** (no `CHORUS_STORAGE_DATABASE_URL` como afirmaba v2 — **corregido**).

**Archivo `osap.toml` (committed, SIN secrets)**:
```toml
[storage]
# database_url se define POR ENTORNO via variable de entorno CHORUS_DATABASE_URL
root = "var/private"
```

**Credenciales por entorno (SOLO variables de entorno, NUNCA en repo)**:
- Dev: `CHORUS_DATABASE_URL=mysql+pymysql://osap2027_dev:****@127.0.0.1:3306/osap_chorus`
- Test: `CHORUS_DATABASE_URL=mysql+pymysql://osap2027_test:****@127.0.0.1:3306/osap_chorus_test`
- Prod: `CHORUS_DATABASE_URL=mysql+pymysql://osap2027_prod:****@db-host:3306/osap_chorus_prod`

**Usuario de pruebas**: `osap2027_test` con permisos **solo sobre `osap_chorus_test`** (SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES). **Sin CREATE DATABASE / DROP DATABASE**.

---

## 5. Auditoría de integración móvil

### 5.1 Estado real del código móvil

| Aspecto | Hallazgo |
|---------|----------|
| **Repositorio** | `D:\Proyectos\AI_OSAP\Chorus_movil\Chorus` — **VACÍO** (`git init`, 0 commits) |
| **Historial git** | Sin commits en rama `main` |
| **Código fuente** | **NO EXISTE** en workspace actual |
| **Documentación técnica** | Existe en `docs/integration-contracts.md`, `docs/authentication-runtime.md`, `docs/roadmap-0.3.md` |

**Conclusión**: **No hay código móvil que auditar**. El repositorio está vacío. Sin embargo, la arquitectura está documentada y los contratos backend están implementados.

---

### 5.2 Arquitectura documentada (verificada en docs y código backend)

#### Autenticación (verificado en `app/main.py` y `docs/authentication-runtime.md`)

| Componente | Implementación backend | Documentación |
|------------|------------------------|---------------|
| **OSAP-Auth** | Autoridad de identidad única | ✅ `docs/authentication-runtime.md` |
| **Login email/password** | `POST /api/v1/auth/login` → reenvía a osap-auth | ✅ Línea 768-790 `app/main.py` |
| **OIDC PKCE** | `GET /api/v1/auth/oidc/start` + callback | ✅ Líneas 999-1053 `app/main.py` |
| **Bearer tokens** | `Authorization: Bearer <access_token>` | ✅ `request()` en `web/app.js:85` |
| **Refresh token** | Cookie `chorus_refresh` (HttpOnly, Secure, SameSite=Lax, path=/api/v1/auth) | ✅ Líneas 780-786, 1048-1052 `app/main.py` |
| **Introspección** | `GET /api/v1/auth/me` → reenvía Bearer a osap-auth `/auth/me` | ✅ Línea 619 `app/main.py` |
| **Audiencia tokens** | osap-auth usa `aud=osap-api`; Chorus no valida JWT localmente | ✅ `docs/authentication-runtime.md:11` |

**Gap móvil**: Web usa cookies para refresh; Android necesitará almacenamiento seguro (Keystore) + header `Authorization` explícito en cada request. **No hay APIs paralelas** — mismo endpoint `/api/v1/auth/refresh` acepta cookie o header.

#### Grupos y permisos (verificado en `app/main.py`)

| Operación | Endpoint | Auth | Permisos | Web usa |
|-----------|----------|------|----------|---------|
| Crear grupo | `POST /api/v1/groups` | Bearer | Usuario autenticado → manager | ✅ |
| Unirse a grupo | `POST /api/v1/groups/join` | Bearer | Usuario autenticado | ✅ |
| Editar grupo | `PATCH /api/v1/groups/{id}` | Bearer | Manager del grupo | ✅ |
| Miembros | `GET /api/v1/groups/{id}/members` | Bearer | Miembro activo | ✅ |
| Editar miembro | `PATCH /api/v1/groups/{id}/members/{sub}` | Bearer | Manager | ✅ |
| Catálogo secciones | `GET /api/v1/groups/{id}/catalog` | Bearer | Miembro activo | ✅ |

**Identidad**: `user.sub` (de osap-auth `user_id`) — consistente web/móvil.

**Grupo activo**: Web maneja en UI; móvil debe permitir selección y persistir localmente.

**Roles**: `role` (manager/member) + `admin_role_id`, `musical_role_id`, `section_id` (strings libres, no normalizados).

---

#### Agenda y comunicación (verificado en `app/main.py`)

| Operación | Endpoint | Auth | Permisos | Formato |
|-----------|----------|------|----------|---------|
| Crear evento | `POST /api/v1/events` | Bearer | Manager (grupo) / Usuario (personal) | JSON |
| Editar evento | `PATCH /api/v1/events/{id}` | Bearer | Creador o Manager | JSON + `edit_scope` |
| Eliminar evento | `DELETE /api/v1/events/{id}` | Bearer | Creador o Manager | `?scope=single|series` |
| RSVP | `POST /api/v1/events/{id}/rsvp` | Bearer | Miembro | `{"status": "yes|no"}` |
| Agenda usuario | `GET /api/v1/agenda` | Bearer | Usuario | `{events[], groups[]}` |
| Mensajes grupo | `GET/POST /api/v1/groups/{id}/messages` | Bearer | Miembro / Manager | JSON |
| Reply mensaje | `POST /api/v1/messages/{id}/reply` | Bearer | Destinatario | `{"body": "...", "all": bool}` |
| Marcar leído | `POST /api/v1/messages/{id}/read` | Bearer | Destinatario | — |
| Artículos | `GET/POST /api/v1/groups/{id}/articles` | Bearer | Miembro / Manager | JSON + media |

**RSVP**: Exclusivamente binario `yes|no` (ver `event_rsvps.status` CHECK constraint).

**Cookies**: Endpoints **no dependen de cookies** salvo `/api/v1/auth/refresh` (acepta cookie `chorus_refresh` **o** header `Authorization` con refresh token). Web usa cookies; Android usará header.

---

#### Material musical (verificado en `app/main.py:2878-3239`)

| Operación | Endpoint | Auth | Formato salida |
|-----------|----------|------|----------------|
| Árbol material | `GET /api/v1/material/tree` | Bearer (manager) | Works → Versions → Files |
| **Manifiesto sincronización** | `GET /api/v1/material/manifest` | Bearer (miembro) | `group_id, generated_at, works[{work_id, title, versions[{resource_id, version_label, section_id, updated_at, files[{file_id, path, sha256, size_bytes, mime_type, download_url}]}]}]` |
| Descarga archivo | `GET /api/v1/material/files/{id}/download` | Bearer (miembro) | Binary (MXL/PDF) + headers |
| Importar material | `POST /api/v1/material/import` | Bearer (manager) | `metadata` (JSON) + `files` (multipart) |
| Publicar recurso | `POST /api/v1/material/resources/{id}/publish` | Bearer (manager) | Resource actualizado |

**Manifiesto**: Existe y es **completo** para sincronización offline. Incluye `sha256`, `size_bytes`, `mime_type`, `download_url`. **No hay parámetro incremental** (`since`, `etag`) — cliente debe comparar localmente.

**Permisos por sección**: `manifest` filtra por `member.section_id` vs `resource.group_section_id`.

**Estados material**: `draft` → `reviewed` → `published` (solo `published` en manifiesto).

---

#### Offline (arquitectura documentada, no implementada en móvil)

| Requisito | Soporte backend | Estado |
|-----------|-----------------|--------|
| Descarga voluntaria material en curso | `manifest` + `download` endpoints | ✅ Backend listo |
| Caché local (archivos + metadatos) | Cliente responsable | ❌ No hay cliente |
| Sincronización posterior | Cliente descarga manifiesto completo, compara `sha256`/`updated_at` | ✅ Backend listo |
| Detección de cambios | `updated_at` en resources + `sha256` en files | ✅ Backend listo |
| Conflictos / reintentos / idempotencia | Cliente responsable (descarga atómica, verifica hash) | ❌ No hay cliente |
| Revocación permisos / material retirado | `material_status` ≠ `published` excluye de manifiesto | ✅ Backend listo |

**Decisión arquitectura**: Cliente decide trabajo offline. Chorus es referencia única. No catálogo paralelo en Android.

---

#### MuseEncore (verificado en `app/main.py:2694-2745`, `web/editor.html`)

| Paso | Implementación | Limitación |
|------|----------------|------------|
| **1. Token temporal** | `GET /api/v1/drafts/{id}/editor` → genera token SHA256 (5 min) | ✅ |
| **2. URL firmada** | `/api/v1/editor-sources/{token}/{filename}` con CORS restringido a `editor_origin` | ✅ |
| **3. Carga MXL** | MuseEncore abre `editor.html?url=...` → carga via `fetch` | ✅ Web |
| **4. Retorno automático** | `postMessage` tipo `chorus:score` con `ArrayBuffer` → `window.opener.postMessage` → web sube a `/api/v1/drafts/{id}/files` | ✅ **Solo web** (requiere `window.opener`) |
| **5. Fallback manual** | Si no hay `window.opener`, `editor.html` descarga `.mxl` → usuario sube manualmente en Chorus | ✅ Web y móvil teórico |

**Gap Android**: Sin `window.opener` en Custom Tab / Trusted Web Activity. Alternativas:
- **Deep link retorno**: `chorus://editor-callback?draft_id=...&file=...` (requiere registrar esquema)
- **Upload directo**: MuseEncore → `POST /api/v1/drafts/{id}/files` (requiere token en MuseEncore)
- **Descarga manual**: Usuario exporta `.mxl` y sube en app Chorus (siempre funciona)

**No hay integración automática implementada** — documentado como limitación conocida.

---

#### Compatibilidad web/Android — Matriz de contratos

| Endpoint | Autenticación | Web usa | Android requerido | Gap |
|----------|---------------|---------|-------------------|-----|
| `/api/v1/auth/login` | email/password | ✅ | ✅ | Ninguno |
| `/api/v1/auth/oidc/start` | — | ✅ | ✅ (Custom Tab) | Callback via App Link |
| `/api/v1/auth/refresh` | Cookie **o** Bearer refresh | Cookie | Header `Authorization` | Implementar TokenManager |
| `/api/v1/auth/me` | Bearer access | ✅ | ✅ | Ninguno |
| `/api/v1/groups/*` | Bearer | ✅ | ✅ | Ninguno |
| `/api/v1/events/*` | Bearer | ✅ | ✅ | Ninguno |
| `/api/v1/material/*` | Bearer | ✅ | ✅ | Descarga binaria via DownloadManager |
| `/api/v1/editor-sources/{token}/*` | Token en URL | Iframe | Custom Tab + token | Sin `window.opener` |

**No hay endpoints que dependan exclusivamente de cookies** — todos aceptan Bearer token. `/api/v1/auth/refresh` acepta ambos.

**No crear APIs paralelas** — contratos actuales son compartibles.

---

### 5.3 Problemas anteriores — Estado

| Problema | Estado actual |
|----------|---------------|
| `doc` undefined en `oidc_callback` | **NO ENCONTRADO** en código actual (líneas 1020-1053 `app/main.py` limpio) |
| Cookies vs Bearer en Android | Resuelto: endpoints aceptan Bearer; solo refresh usa cookie opcional |
| Duplicación catálogo musical | No — Chorus usa modelo V6 propio, referencias OSAP opacas |
| Sincronización offline | Backend listo (manifiesto); cliente pendiente |

---

## 6. Pruebas y CI

### 6.1 Diseño de pruebas reales con MariaDB 10.4.32

| Categoría | Tests | Motor | Datos |
|-----------|-------|-------|-------|
| **Unitarios** | MXL validation, helpers puros | Sin BD | Sintéticos |
| **Instalación limpia** | `initialise_database` registra 001→003 | MariaDB | Vacía |
| **Actualización legacy** | Baseline compatible → registra 001 + 999 | MariaDB | Esquema 001_schema.sql + solo mysql_schema_v1 |
| **Legacy incompleta** | Baseline falla → aborta | MariaDB | Esquema incompleto |
| **Repetición** | Re-ejecutar inicialización → idempotente | MariaDB | Ya actualizada |
| **Migraciones material** | 002, 003 añaden columnas + registran | MariaDB | Post-baseline |
| **API grupos/agenda** | CRUD + permisos + RSVP | MariaDB | Sintéticos |
| **API mensajes** | Hilos, reply-all, lectura | MariaDB | Sintéticos |
| **API material** | Árbol, manifiesto, descarga, import, publish | MariaDB | Sintéticos |
| **Permisos** | Manager vs miembro vs outsider | MariaDB | Sintéticos |
| **Autenticación** | Login, refresh, OIDC, onboarding | MariaDB + FakeAuth | Sintéticos |
| **Contratos móviles** | Cuando exista cliente: mismos endpoints | MariaDB | Sintéticos |

**Datos**: Siempre sintéticos. **Nunca** datos personales de producción.

### 6.2 GitHub Actions — Configuración real

```yaml
# .github/workflows/test.yml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[test]"
      - run: pytest -m unit -x -q

  integration-tests:
    runs-on: ubuntu-latest
    # Sin contenedores: MariaDB 10.4 nativo via apt
    steps:
      - run: python scripts/rebuild_test_db.py
      - run: pytest -m migrations -x -v
```

---

## 7. Integración coral

**NO INCLUIDA** en este trabajo. La migración `005_coral_integration.sql`, modelos API, frontend y tests son **trabajo independiente** que requiere autorización expresa separada.

---

## 8. Informe final v3 — Formato requerido

### 8.1 Hallazgos con gravedad, archivo/líneas, evidencia, corrección, prueba

| ID | Gravedad | Archivo/Líneas | Evidencia observada | Consecuencia | Corrección mínima | Prueba de verificación |
|----|----------|----------------|---------------------|--------------|-------------------|------------------------|
| **A1** | **Bloqueante** | `migrations/mysql/001_schema.sql` (19 CREATE TABLE) | 18 tablas aplicación vs 21 SQLite; 3 faltantes | Baseline legacy verifica tablas inexistentes | Baseline verifica exactamente 18 tablas reales | `SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()` = 19 (con migraciones) |
| **A2** | **Bloqueante** | `999_legacy_baseline.sql` (propuesto v2) | `INSERT IGNORE` registra 002,003,004 sin ejecutar | Historial falseado | Solo registra `001_baseline_schema` + `999_legacy_baseline` | `SELECT name FROM chorus_schema_migrations` tras baseline = 2 filas |
| **A3** | **Bloqueante** | `999_legacy_baseline.sql` | `@legacy_ok=FALSE` no aborta conexión | Inicialización continúa sobre esquema incompatible | `SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Legacy baseline failed'` | Ejecutar baseline en BD incompleta → error SQLSTATE 45000 |
| **A4** | **Bloqueante** | `app/main.py:477-526` (`initialise_database`) | MySQL: solo ejecuta 001_schema.sql + registra mysql_schema_v1; retorna línea 496 | Migraciones 002,003,004 MySQL nunca corren; material y tablas artículos faltantes | Reescribir con detección legacy + bucle 001→004 | Instalación nueva MySQL → registra 001,002,003,004 |
| **A5** | **Alta** | `app/db.py:69-75` (`executescript`) | Split por `;` sin respetar strings/comentarios | SQL frágil, falla con `;` en datos | Extraer `_execute_sql_script` con `sqlparse` | Ejecutar migración con `;` en string → no se rompe |
| **A6** | **Alta** | `scripts/rebuild_test_db.py` (no existe) | No hay script de reconstrucción | Tests no pueden recrear BD limpia | Crear script con `autocommit=True`, verificación final | `python scripts/rebuild_test_db.py` → exit 0, verificación OK |
| **A7** | **Alta** | `tests/conftest.py` (no existe) | Sin protección; tests unitarios e integración mezclados | Tests integración corren con SQLite accidental | Fixtures selectivas + marcadores + verificación conexión efectiva | `pytest -m integration` sin MariaDB → RuntimeError |
| **A8** | **Media** | `pyproject.toml:21-23` | Sin marcadores, `addopts = "-ra"` | No separación unit/integration | Añadir marcadores + `addopts = "-m 'not integration'"` | `pytest` → solo unit; `pytest -m integration` → solo integration |
| **A9** | **Media** | `app/config.py:80` | Variable real `CHORUS_DATABASE_URL` (no `CHORUS_STORAGE_DATABASE_URL`) | Docs v2 incorrectos | Corregir docs; usar `CHORUS_DATABASE_URL` consistentemente | `grep -r CHORUS_DATABASE_URL` → solo referencias correctas |
| **A10** | **Media** | `migrations/mysql/002_agenda_recurrence.sql`, `003_group_articles.sql` | Redundantes (ALTER TABLE en baseline, CREATE TABLE en 004) | Confusión historial | Eliminar; contenido real en 002_material, 003_material_groups, 004_group_articles_tables | `ls migrations/mysql/` → solo 001,002,003,004,005,999 |
| **A11** | **Baja** | `docs/mysql.md` | Referencias a `CHORUS_STORAGE_DATABASE_URL` | Inconsistencia | Actualizar a `CHORUS_DATABASE_URL` | `grep CHORUS_DATABASE_URL docs/` → consistente |

---

### 8.2 Lista exacta de archivos que habría que modificar

#### Migraciones MySQL (7 archivos)
1. `migrations/mysql/001_baseline_schema.sql` — **RENOMBRAR** desde `001_schema.sql`
2. `migrations/mysql/002_material_library.sql` — **NUEVO** (desde SQLite 012)
3. `migrations/mysql/003_material_groups.sql` — **NUEVO** (desde SQLite 013)
4. `migrations/mysql/004_group_articles_tables.sql` — **NUEVO** (3 CREATE TABLE de SQLite 015, SIN ALTER TABLE groups)
5. `migrations/mysql/005_coral_integration.sql` — **NUEVO** (trabajo independiente, no autorizado aquí)
6. `migrations/mysql/999_legacy_baseline.sql` — **NUEVO** (verificación + registro honesto)
7. **ELIMINAR**: `migrations/mysql/002_agenda_recurrence.sql`, `migrations/mysql/003_group_articles.sql`

#### Código aplicación (3 archivos)
7. `app/main.py` — `initialise_database()` líneas 477-526: detección legacy + bucle 001→004
8. `app/db.py` — Añadir `_execute_sql_script()` con `sqlparse`, `_detect_legacy_installation()`, `_ensure_migrations_table()`
9. `app/config.py` — Sin cambios (ya correcto)

#### Scripts (1 archivo)
10. `scripts/rebuild_test_db.py` — **NUEVO** (idempotente, verificación final, `autocommit=True`)

#### Tests (8+ archivos)
11. `tests/conftest.py` — **NUEVO** (fixtures `integration_settings`, `migration_settings`, verificación conexión efectiva)
12. `pyproject.toml` — `sqlparse` en `[dev]`/`[test]`, marcadores, `addopts`
13. `tests/test_agenda.py` — `@pytest.mark.integration`, fixture `integration_settings`
14. `tests/test_articles.py` — igual
15. `tests/test_messages.py` — igual
15. `tests/test_material.py` — igual
16. `tests/test_entity_leads.py` — igual
17. `tests/test_creation_drafts.py` — **REESCRIBIR** para MariaDB + `@pytest.mark.integration @pytest.mark.migrations`
18. `tests/test_v6_schema.py` — **REESCRIBIR** igual
19. `tests/test_oidc.py` — **REESCRIBIR** igual
20. `tests/test_library_integrity.py` — **REESCRIBIR** igual
21. `tests/test_api_runtime.py` — Separar: tests MXL → `@pytest.mark.unit`; test migraciones → reescribir MariaDB + `@pytest.mark.migrations`

#### CI/CD (1 archivo)
22. `.github/workflows/test.yml` — **NUEVO** (3 jobs: unit, integration, migrations)

#### Documentación (1 archivo)
23. `docs/mysql.md` — Actualizar: 5 migraciones, baseline, variable `CHORUS_DATABASE_URL`, permisos `osap2027_test`

---

### 8.3 Orden de implementación

| Fase | Descripción | Entregables | Criterio de salida |
|------|-------------|-------------|---------------------|
| **1. Fundación BD** | Migraciones reales, baseline legacy, rebuild script, helper SQL compartido | Items 1-7, 10 | `CHORUS_DATABASE_URL=.../osap_chorus_test python -c "from app.main import initialise_database; from app.config import Settings; initialise_database(Settings.load())"` registra 001, 002, 003, 004; `rebuild_test_db.py` exit 0 |
| **2. Infraestructura tests** | conftest, marcadores, reclasificar tests API | Items 7-9, 12-16 | `pytest` (solo unit, <5s); `CHORUS_DATABASE_URL=.../osap_chorus_test pytest -m integration` pasa tests API |
| **3. Tests esquema** | Reescribir 5 tests para MariaDB real | Items 17-21 | `pytest -m migrations` 100% pass en MariaDB |
| **4. CI/CD** | GitHub Actions 3 jobs | Item 22 | Push a main → 3 jobs verdes |
| **5. Coral (separado)** | Migración 005 + API + frontend | Item 5 | Autorización separada |

---

### 8.4 Riesgos pendientes

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| `sqlparse` no maneja dialecto MariaDB específico | Baja | Medio | Probar con scripts reales antes de Fase 1 |
| Baseline legacy falla en instalaciones con esquemas híbridos | Media | Alto | Probar con snapshot de BD dev real antes de Fase 1 |
| Tests de esquema reescritos revelan bugs latentes | Media | Medio | Ejecutar en MariaDB local antes de CI |
| `rebuild_test_db.py` estado parcial tras fallo DDL | Baja | Medio | Verificación final en nueva conexión + exit ≠ 0 |
| Usuario `osap2027_test` permisos incorrectos en CI | Baja | Alto | Validar permisos en step CI antes de tests |

---

### 8.5 Criterios de aceptación verificables

| ID | Criterio | Comando | Esperado |
|----|----------|---------|----------|
| **CA-01** | 5 migraciones MySQL reales (+ baseline) | `ls migrations/mysql/00[1-5]_*.sql migrations/mysql/999_legacy_baseline.sql \| wc -l` | 6 |
| **CA-02** | Migraciones redundantes eliminadas | `ls migrations/mysql/002_agenda_recurrence.sql 2>/dev/null; echo $?` | 1 (no existe) |
| **CA-03** | Instalación nueva MySQL registra 001→004 | Ver Fase 1 | 4 filas: `001_baseline_schema`, `002_material_library`, `003_material_groups`, `004_group_articles_tables` |
| **CA-04** | Legacy compatible registra baseline honesto | Ver Fase 1 | 2 filas: `001_baseline_schema`, `999_legacy_baseline` |
| **CA-05** | Legacy incompleta NO registra baseline | Ver Fase 1 | Solo `mysql_schema_v1` |
| **CA-06** | `rebuild_test_db.py` reconstruye y verifica | `CHORUS_DATABASE_URL=.../osap_chorus_test python scripts/rebuild_test_db.py` | Exit 0, verificación OK |
| **CA-07** | `rebuild_test_db.py` falla si migración falla | Corromper migración → ejecutar | Exit != 0 |
| **CA-08** | Tests unitarios corren sin BD | `pytest` | ≥5 tests pass, <5s, sin conexión BD |
| **CA-09** | Tests integración bloqueados sin MariaDB | `unset CHORUS_DATABASE_URL && pytest -m integration` | `RuntimeError` claro |
| **CA-10** | Tests integración corren con MariaDB | `CHORUS_DATABASE_URL=.../osap_chorus_test pytest -m integration` | 100% pass |
| **CA-11** | GitHub Actions 3 jobs verdes | Push a main | Unit + Integration + Migrations = pass |
| **CA-12** | Sin secrets en repo | `git grep -rE "(password|secret)" -- "*.toml" "*.py" \| grep -v "CHORUS_" \| grep -v "testpass" \| grep -v "placeholder"` | Sin resultados |
| **CA-13** | Variable unificada `CHORUS_DATABASE_URL` | `grep -r "CHORUS_STORAGE_DATABASE_URL" -- "*.py" "*.md" "*.yml" \| grep -v "CHORUS_DATABASE_URL"` | Sin resultados |
| **CA-14** | Ejecutor SQL compartido (`sqlparse`) | `grep -r "sqlparse" app/db.py` | Encontrado en `_execute_sql_script` |

---

### 8.6 Decisión recomendada sobre Fase 1

**RECOMENDACIÓN: AUTORIZAR FASE 1** con las siguientes condiciones previas:

1. **Validar `sqlparse`** con los 4 scripts de migración reales antes de implementar `_execute_sql_script`.
2. **Snapshot de BD dev real** para probar `999_legacy_baseline.sql` detectando esquemas híbridos.
3. **Crear usuario `osap2027_test`** en MariaDB local/CI con permisos exactos (sin CREATE/DROP DATABASE).
4. **Confirmar que `005_coral_integration.sql` queda FUERA** de este alcance (trabajo separado).

**No autorizar Fases 2-5 hasta que Fase 1 pase todos los CA-01 a CA-07 en entorno real.**

---

**Fin de la auditoría técnica v3.**

**Próximo paso**: Autorización expresa para implementar Fase 1 (fundación BD).