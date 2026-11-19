# Chorus 0.15 — Propuesta técnica corregida: Separación de entornos dev/test (v2)

**Fecha**: 2026-11-18  
**Versión**: Chorus 0.14.0 → 0.15.0  
**Ámbito**: Solo análisis y documentación — **sin modificaciones**

---

## 1. Análisis real de migraciones: Matriz definitiva

### 1.1 Estado actual comparado

| Aspecto | SQLite (15 migraciones incrementales) | MySQL (3 archivos actuales) |
|---------|--------------------------------------|----------------------------|
| **001** | `works`, `resources`, `files` + índices + FK deferrables | Incluido en `001_schema.sql` |
| **002** | `creation_drafts`, `editor_source_tokens` + CHECKs | Incluido en `001_schema.sql` |
| **003** | `owner_sub` en `works` + `library_items`, `collections`, `collection_items` | Incluido en `001_schema.sql` |
| **004** | `oidc_states` | Incluido en `001_schema.sql` |
| **005** | Recrea `creation_drafts` con `source_kind='local'` | **Ya incluido** en `001_schema.sql` (tiene `source_kind='local'` en CHECK) |
| **006** | `groups`, `group_members`, `events`, `event_groups`, `event_rsvps` | Incluido en `001_schema.sql` |
| **007** | `entity_leads` | Incluido en `001_schema.sql` |
| **008** | `manager_name`, `manager_email`, `manager_has_account` en `entity_leads` | **Ya incluido** en `001_schema.sql` |
| **009** | `display_name` en `group_members` + `messages`, `message_recipients` | **Ya incluido** en `001_schema.sql` |
| **010** | `admin_role_id`, `musical_role_id`, `section_id` en `group_members` | **Ya incluido** en `001_schema.sql` |
| **011** | `event_targets` | **Ya incluido** en `001_schema.sql` |
| **012** | `version_label`, `part_label`, `material_status` en `resources` + `folder_path`, `display_name`, `original_name` en `files` | **FALTA** en `001_schema.sql` |
| **013** | `group_id`, `group_section_id` en `resources` + índice | **FALTA** en `001_schema.sql` |
| **014** | `recurrence`, `recurrence_until`, `series_id`, `creator_badge` en `events` + índice | **Ya incluido** en `001_schema.sql` |
| **015** | `slug`, `kind`, `description`... en `groups` + `group_sections`, `group_articles`, `group_article_media` | **Ya incluido** en `001_schema.sql` |

### 1.2 Conclusión crítica

**El archivo `migrations/mysql/001_schema.sql` YA CONTIENE el esquema completo equivalente a SQLite 001-015**, excepto dos migraciones de material:
- **012_material_library** → columnas en `resources` y `files`
- **013_material_groups** → columnas `group_id`, `group_section_id` en `resources`

**Los archivos MySQL 002 y 003 son REDUNDANTES** — sus `ALTER TABLE` ya están aplicados en 001_schema.sql.

### 1.3 Matriz definitiva de migraciones MySQL necesarias

| Migración MySQL | Contenido real | Origen SQLite equivalente | Estado |
|-----------------|----------------|---------------------------|--------|
| **001_baseline_schema.sql** | Esquema completo (works→files, drafts, library, groups, events, entity_leads, messages, oidc_states, event_targets, group_members con roles, events con recurrence, groups con articles) | 001-015 **excepto** 012, 013 | **EXISTE** (renombrar 001_schema.sql) |
| **002_material_library.sql** | `ALTER TABLE resources ADD version_label, part_label, material_status` + `ALTER TABLE files ADD folder_path, display_name, original_name` + índice | 012_material_library.sql | **NUEVO** |
| **003_material_groups.sql** | `ALTER TABLE resources ADD group_id, group_section_id` + índice | 013_material_groups.sql | **NUEVO** |
| **004_coral_integration.sql** | 12 columnas coral en `groups` (informe previo) | — | **NUEVO (Chorus 0.15)** |

**Total: 4 migraciones MySQL reales** (no 15, no 3).

---

## 2. Estrategia de Baseline para instalaciones Legacy

### 2.1 Problema

Instalaciones MySQL existentes tienen:
- Esquema completo creado por `001_schema.sql` monolítico
- Solo `mysql_schema_v1` registrada en `chorus_schema_migrations`
- **No se puede** registrar 001-015 como "ejecutadas" porque sus scripts individuales nunca corrieron

### 2.2 Solución: Baseline honesto con verificación de integridad

**Archivo nuevo**: `migrations/mysql/001_baseline_schema.sql` (renombrado de `001_schema.sql`)

**Archivo nuevo**: `migrations/mysql/002_material_library.sql` (contenido de SQLite 012)

**Archivo nuevo**: `migrations/mysql/003_material_groups.sql` (contenido de SQLite 013)

**Archivo nuevo**: `migrations/mysql/004_coral_integration.sql` (12 columnas coral)

**Archivo nuevo**: `migrations/mysql/999_legacy_baseline.sql` — **SOLO registro de baseline, SIN DDL**

```sql
-- migrations/mysql/999_legacy_baseline.sql
-- Baseline para instalaciones legacy: registra que el esquema base (001) ya existe
-- NO ejecuta ningún DDL. Solo verifica e inserta registros de migración.
-- Se ejecuta UNA VEZ en instalaciones que ya tienen el esquema completo.

-- Verificación de integridad: comprobar que TODAS las tablas/columnas esperadas existen
-- Si falla, la migración aborta y NO registra nada.

-- Tabla de verificación (se crea temporalmente)
CREATE TEMPORARY TABLE IF NOT EXISTS _legacy_verification (
    check_name VARCHAR(191) PRIMARY KEY,
    passed BOOLEAN NOT NULL
);

-- 1. Verificar tablas críticas
INSERT INTO _legacy_verification (check_name, passed)
SELECT 'tables_exist', COUNT(*) = 20
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN (
    'works','resources','files','creation_drafts','editor_source_tokens',
    'library_items','collections','collection_items','oidc_states',
    'groups','group_members','events','event_groups','event_rsvps',
    'entity_leads','messages','message_recipients','event_targets',
    'group_sections','group_articles','group_article_media'
  );

-- 2. Verificar columnas críticas de material (012/013)
INSERT INTO _legacy_verification (check_name, passed)
SELECT 'material_columns', COUNT(*) = 7
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND ((TABLE_NAME = 'resources' AND COLUMN_NAME IN ('version_label','part_label','material_status','group_id','group_section_id'))
       OR (TABLE_NAME = 'files' AND COLUMN_NAME IN ('folder_path','display_name','original_name')));

-- 3. Verificar columnas coral (004)
INSERT INTO _legacy_verification (check_name, passed)
SELECT 'coral_columns', COUNT(*) = 12
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'groups'
  AND COLUMN_NAME IN ('foundation_date','dissolution_date','locality','region','country_code',
                      'venue','formation_type','member_count','public_email',
                      'language','repertoire','venues');

-- 4. Evaluar resultado
SET @legacy_ok = (SELECT COUNT(*) FROM _legacy_verification WHERE passed = TRUE) = 3;

-- 5. Si todo OK, registrar baseline
INSERT IGNORE INTO `chorus_schema_migrations` (`name`, `applied_at`)
SELECT '001_baseline_schema', UTC_TIMESTAMP() FROM DUAL WHERE @legacy_ok;

INSERT IGNORE INTO `chorus_schema_migrations` (`name`, `applied_at`)
SELECT '002_material_library', UTC_TIMESTAMP() FROM DUAL WHERE @legacy_ok;

INSERT IGNORE INTO `chorus_schema_migrations` (`name`, `applied_at`)
SELECT '003_material_groups', UTC_TIMESTAMP() FROM DUAL WHERE @legacy_ok;

INSERT IGNORE INTO `chorus_schema_migrations` (`name`, `applied_at`)
SELECT '004_coral_integration', UTC_TIMESTAMP() FROM DUAL WHERE @legacy_ok;

-- 6. Registrar que se aplicó el baseline legacy
INSERT IGNORE INTO `chorus_schema_migrations` (`name`, `applied_at`)
SELECT '999_legacy_baseline', UTC_TIMESTAMP() FROM DUAL WHERE @legacy_ok;

-- Limpieza
DROP TEMPORARY TABLE IF EXISTS _legacy_verification;
```

### 2.3 Lógica en `initialise_database()`

```python
def initialise_database(settings: Settings) -> None:
    root = Path(__file__).resolve().parent.parent
    with _connect(settings) as conn:
        # 1. Asegurar tabla de migraciones
        _ensure_migrations_table(conn, settings.database_url is not None)

        # 2. Detectar instalación legacy MySQL
        is_mysql = settings.database_url is not None
        if is_mysql:
            legacy = _detect_legacy_installation(conn)
            if legacy:
                # Ejecutar baseline legacy (solo registro, verifica integridad)
                _execute_sql_script(conn, (root / "migrations" / "mysql" / "999_legacy_baseline.sql").read_text("utf-8"), True)
                return  # Baseline aplicado, migraciones futuras correrán normal

        # 3. Instalación nueva: ejecutar migraciones en orden
        migration_names = [
            "001_baseline_schema",
            "002_material_library",
            "003_material_groups",
            "004_coral_integration",
        ]

        mig_dir = "mysql" if is_mysql else "sqlite"

        for name in migration_names:
            applied = conn.execute(
                "SELECT 1 FROM chorus_schema_migrations WHERE name = ?", (name,)
            ).fetchone()
            if applied is None:
                sql_path = root / "migrations" / mig_dir / f"{name}.sql"
                if not sql_path.exists():
                    # En SQLite, algunas migraciones pueden no existir (p.ej. coral)
                    continue
                script = sql_path.read_text("utf-8")
                _execute_sql_script(conn, script, is_mysql)
                conn.execute(
                    "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
                    (name, utcnow()),
                )

def _detect_legacy_installation(conn) -> bool:
    """Detecta instalación MySQL con esquema completo pero solo mysql_schema_v1 registrada."""
    # Tiene tablas principales
    has_groups = conn.execute("SHOW TABLES LIKE 'groups'").fetchone() is not None
    # Solo tiene mysql_schema_v1
    row = conn.execute("SELECT COUNT(*) AS c FROM chorus_schema_migrations WHERE name = 'mysql_schema_v1'").fetchone()
    has_only_v1 = row and row["c"] == 1
    # Total de migraciones registradas = 1
    row = conn.execute("SELECT COUNT(*) AS c FROM chorus_schema_migrations").fetchone()
    total_one = row and row["c"] == 1
    return has_groups and has_only_v1 and total_one

def _ensure_migrations_table(conn, is_mysql: bool) -> None:
    if is_mysql:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chorus_schema_migrations (
                name VARCHAR(191) PRIMARY KEY,
                applied_at VARCHAR(64) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chorus_schema_migrations (
                name TEXT PRIMARY KEY, applied_at TEXT NOT NULL
            )
        """)
```

### 2.4 Comportamiento por tipo de instalación

| Tipo | Detección | Acción |
|------|-----------|--------|
| **Nueva (MySQL)** | Sin tablas, sin migraciones | Ejecuta 001→004 en orden, registra cada una |
| **Nueva (SQLite)** | Sin tablas, sin migraciones | Ejecuta 001-015 SQLite en orden |
| **Legacy MySQL compatible** | Tablas completas + solo `mysql_schema_v1` | Ejecuta `999_legacy_baseline` → verifica integridad → registra 001-004 como baseline |
| **Legacy MySQL incompleta** | Tablas faltantes o columnas faltantes | `999_legacy_baseline` falla en verificación → **NO registra nada** → `initialise_database` continúa e intenta aplicar 001-004 (fallará por tablas existentes, error claro) |
| **Ya actualizada** | Migraciones 001-004 registradas | No hace nada (idempotente) |

**Clave**: No se falsea historial. `999_legacy_baseline` registra explícitamente que fue un **reconocimiento de baseline**, no una ejecución.

---

## 3. Reconstrucción de `osap_chorus_test` — Corrección transaccional

### 3.1 Realidad de MariaDB DDL

> **MariaDB/MySQL hacen COMMIT implícito antes y después de cada statement DDL** (CREATE, DROP, ALTER TABLE). **No hay rollback posible** para DDL dentro de una transacción.

### 3.2 Script corregido: `scripts/rebuild_test_db.py`

```python
#!/usr/bin/env python3
"""Reconstruye el esquema de osap_chorus_test desde cero.
REALIDAD: MariaDB hace COMMIT implícito en DDL.
- NO usa transacción global (no sirve para DDL)
- Cada statement se autocommit
- Si falla a mitad, el estado es parcial → el script DEBE ser reejecutable (idempotente)
- Verifica esquema al final; si falla, exit code != 0
"""
import os
import sys
import pymysql
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations" / "mysql"

MIGRATION_NAMES = [
    "001_baseline_schema",
    "002_material_library",
    "003_material_groups",
    "004_coral_integration",
]

def _execute_sql_script(cursor, script: str) -> None:
    """Ejecuta script statement por statement. Cada DDL hace autocommit."""
    import sqlparse
    cleaned = "\n".join(
        line for line in script.splitlines()
        if not line.strip().startswith("--")
    )
    statements = sqlparse.split(cleaned)
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        cursor.execute(stmt)

def _verify_schema(cursor, db_name: str) -> bool:
    """Verifica que el esquema final coincide con lo esperado."""
    checks = []

    # 1. Tablas esperadas (20 base + 4 coral = 24 aprox)
    expected_tables = {
        'chorus_schema_migrations', 'works', 'resources', 'files',
        'creation_drafts', 'editor_source_tokens', 'library_items',
        'collections', 'collection_items', 'oidc_states',
        'groups', 'group_members', 'events', 'event_groups',
        'event_rsvps', 'entity_leads', 'messages', 'message_recipients',
        'event_targets', 'group_sections', 'group_articles',
        'group_article_media'
    }
    cursor.execute("SHOW TABLES")
    actual = {row[f"Tables_in_{db_name}"] for row in cursor.fetchall()}
    missing = expected_tables - actual
    extra = actual - expected_tables
    checks.append(("tables", len(missing) == 0, f"Missing: {missing}, Extra: {extra}"))

    # 2. Columnas material en resources
    cursor.execute("""
        SELECT COLUMN_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'resources'
          AND COLUMN_NAME IN ('version_label','part_label','material_status','group_id','group_section_id')
    """, (db_name,))
    material_cols = {row['COLUMN_NAME'] for row in cursor.fetchall()}
    expected_material = {'version_label','part_label','material_status','group_id','group_section_id'}
    checks.append(("material_columns", material_cols == expected_material, f"Got: {material_cols}"))

    # 3. Columnas material en files
    cursor.execute("""
        SELECT COLUMN_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'files'
          AND COLUMN_NAME IN ('folder_path','display_name','original_name')
    """, (db_name,))
    file_cols = {row['COLUMN_NAME'] for row in cursor.fetchall()}
    expected_files = {'folder_path','display_name','original_name'}
    checks.append(("file_columns", file_cols == expected_files, f"Got: {file_cols}"))

    # 4. Columnas coral en groups
    cursor.execute("""
        SELECT COLUMN_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'groups'
          AND COLUMN_NAME IN ('foundation_date','dissolution_date','locality','region','country_code',
                              'venue','formation_type','member_count','public_email',
                              'language','repertoire','venues')
    """, (db_name,))
    coral_cols = {row['COLUMN_NAME'] for row in cursor.fetchall()}
    expected_coral = {'foundation_date','dissolution_date','locality','region','country_code',
                      'venue','formation_type','member_count','public_email',
                      'language','repertoire','venues'}
    checks.append(("coral_columns", coral_cols == expected_coral, f"Got: {coral_cols}"))

    # 5. Foreign keys críticas
    cursor.execute("""
        SELECT COUNT(*) AS c FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = %s AND CONSTRAINT_TYPE = 'FOREIGN KEY'
    """, (db_name,))
    fk_count = cursor.fetchone()['c']
    checks.append(("foreign_keys", fk_count >= 15, f"FK count: {fk_count}"))

    # 6. Migraciones registradas
    cursor.execute("SELECT name FROM chorus_schema_migrations ORDER BY name")
    applied = {row['name'] for row in cursor.fetchall()}
    expected_migrations = {'001_baseline_schema', '002_material_library', '003_material_groups', '004_coral_integration'}
    checks.append(("migrations", expected_migrations.issubset(applied), f"Applied: {applied}"))

    all_ok = all(ok for _, ok, _ in checks)
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    return all_ok

def main() -> int:
    url = os.getenv("CHORUS_DATABASE_URL")
    if not url:
        print("ERROR: CHORUS_DATABASE_URL no definido", file=sys.stderr)
        return 1

    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    db_name = (parsed.path or "").lstrip("/")

    if db_name != "osap_chorus_test":
        print(f"ERROR: Base de datos no es osap_chorus_test (es '{db_name}')", file=sys.stderr)
        return 1

    print(f"Reconstruyendo esquema en {db_name}...")

    conn = pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username or "",
        password=parsed.password or "",
        database=db_name,
        charset="utf8mb4",
        autocommit=True,  # IMPORTANTE: autocommit para DDL
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        with conn.cursor() as cur:
            # 1. Desactivar FK checks (session)
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")

            # 2. Dropear TODAS las tablas (cada DROP = autocommit)
            cur.execute("SHOW TABLES")
            tables = [row[f"Tables_in_{db_name}"] for row in cur.fetchall()]
            for table in tables:
                cur.execute(f"DROP TABLE IF EXISTS `{table}`")
            print(f"  Tablas eliminadas: {len(tables)}")

            # 3. Aplicar migraciones en orden
            for name in MIGRATION_NAMES:
                sql_path = MIGRATIONS_DIR / f"{name}.sql"
                if not sql_path.exists():
                    print(f"  ADVERTENCIA: {sql_path} no existe, saltando")
                    continue
                print(f"  Aplicando {name}...")
                script = sql_path.read_text("utf-8")
                _execute_sql_script(cur, script)

            # 4. Reactivar FK checks
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        # 5. Verificación final (nueva conexión para ver estado committeado)
        conn.close()
        conn = pymysql.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 3306,
            user=parsed.username or "",
            password=parsed.password or "",
            database=db_name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn.cursor() as cur:
            print("Verificando esquema final...")
            if not _verify_schema(cur, db_name):
                print("ERROR: Verificación de esquema falló", file=sys.stderr)
                return 1

        print("Reconstrucción completada y verificada OK")
        return 0

    except Exception as e:
        print(f"ERROR durante reconstrucción: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
```

**Puntos clave**:
- `autocommit=True` — cada DDL se confirma inmediatamente
- **No hay rollback** — si falla a mitad, el estado es parcial
- **Idempotente**: se puede reejecutar; `DROP TABLE IF EXISTS` + `CREATE TABLE` limpian
- **Verificación final obligatoria** — cuenta tablas, columnas, FKs, migraciones registradas
- **Exit code != 0** si cualquier verificación falla
- **No declara éxito parcial**

---

## 4. Protección de tests — Corrección

### 4.1 Problema actual

Fixture `autouse=True` en `conftest.py` bloquea **todos** los tests, incluidos unitarios sin BD.

### 4.2 Solución: Marcadores + fixture selectiva

```python
# tests/conftest.py
import os
import pytest
from urllib.parse import urlparse

from app.config import Settings
from app.db import connect as db_connect


def _get_effective_database_name(settings: Settings) -> str:
    """Devuelve el nombre de base de datos que Chorus USA REALMENTE."""
    conn = db_connect(settings)
    try:
        if settings.database_url:
            row = conn.execute("SELECT DATABASE() AS db").fetchone()
            return row["db"] if row else ""
        else:
            row = conn.execute("PRAGMA database_list").fetchone()
            path = row[2] if row else ""
            return os.path.basename(path) if path else "sqlite_memory"
    finally:
        conn.close()


def _verify_integration_config() -> Settings:
    """Verifica configuración real que usará create_app(). Bloquea si incorrecta."""
    settings = Settings.load()  # Carga osap.toml + env vars igual que la app

    if not settings.database_url:
        raise RuntimeError(
            "BLOQUEO: Tests de integración requieren CHORUS_DATABASE_URL "
            "apuntando a MariaDB (osap_chorus_test). "
            "Actual: database_url está vacío → usaría SQLite."
        )

    effective_db = _get_effective_database_name(settings)
    if effective_db != "osap_chorus_test":
        raise RuntimeError(
            f"BLOQUEO DE SEGURIDAD: Conexión EFECTIVA apunta a '{effective_db}', "
            f"se requiere 'osap_chorus_test'.\n"
            f"Configuración detectada:\n"
            f"  database_url = {settings.database_url}\n"
            f"  database_path = {settings.database_path}\n\n"
            f"Defina CHORUS_DATABASE_URL=mysql+pymysql://.../osap_chorus_test "
            f"antes de ejecutar pytest -m integration."
        )

    return settings


# Fixture SOLO para tests marcados @pytest.mark.integration
@pytest.fixture
def integration_settings():
    """Settings validados para tests de integración. Falla antes de cualquier test."""
    return _verify_integration_config()


# Fixture para tests de migraciones (subconjunto de integration)
@pytest.fixture
def migration_settings(integration_settings):
    return integration_settings


# NO hay fixture autouse global — los tests unitarios corren sin BD
```

### 4.3 Uso en tests

```python
# tests/test_agenda.py
import pytest
from app.main import create_app
from fastapi.testclient import TestClient

# Tests unitarios (sin BD) — SIN marcador, corren por defecto
def test_something_pure():
    assert True

# Tests de integración — REQUIEREN MariaDB
@pytest.mark.integration
def test_create_group_event_and_rsvp(integration_settings, monkeypatch):
    # integration_settings ya validó la conexión
    with TestClient(create_app(integration_settings)) as client:
        # ... test real contra MariaDB
        pass

# Tests de migraciones
@pytest.mark.integration
@pytest.mark.migrations
def test_migrations_repeatable(migration_settings):
    # ... test migraciones
    pass
```

### 4.4 Configuración pytest

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

### 4.5 Comportamiento

| Comando | Tests que corren | BD requerida |
|---------|------------------|--------------|
| `pytest` | Solo `@pytest.mark.unit` (o sin marcador) | **No** |
| `pytest -m integration` | `@pytest.mark.integration` | **Sí** (osap_chorus_test) |
| `pytest -m migrations` | `@pytest.mark.migrations` | **Sí** |
| `pytest -m "unit or integration"` | Todos | Mixta |

- **Ausencia de MariaDB** → `pytest -m integration` falla con error claro (no skip silencioso)
- **Configuración incorrecta** → Falla **antes** de cualquier test (en fixture `integration_settings`)
- **Tests unitarios** → Corren siempre, sin conexión BD

---

## 5. Configuración — Estrategia real verificada

### 5.1 Cómo funciona `Settings.load()` realmente

```python
def value(env: str, section: dict, key: str, default: str = "") -> str:
    return os.getenv(env, str(section.get(key, default))).strip()
```

**Precedencia real** (orden de prioridad):
1. **Variable de entorno** `CHORUS_<SECTION>_<KEY>` (ej: `CHORUS_STORAGE_DATABASE_URL`)
2. **Valor en `osap.toml`** bajo `[section]` → `key`
3. **Default** hardcoded en el código

**NO hay interpolación `${VAR}` en `osap.toml`**. El código **no usa** `os.path.expandvars` ni similar.

### 5.2 Estrategia de credenciales segura

#### Archivo `osap.toml` (committed, SIN secrets)

```toml
# osap.toml — configuración base, SIN contraseñas
[storage]
# database_url se define POR ENTORNO via variable de entorno
# database_path = "var/chorus.sqlite3"  # fallback solo para tests unitarios
root = "var/private"

[auth]
base_url = "http://osap-auth/auth-api"
timeout_seconds = 15
oidc_issuer = "http://osap-auth/auth-api"
oidc_client_id = "chorus-web"
# oidc_client_secret = ""  # NUNCA en repo — solo env var
oidc_redirect_uri = "http://chorus-app/api/v1/auth/oidc/callback"

[osap]
api_base_url = "http://osap-app"
timeout_seconds = 45

[editor]
base_url = "http://127.0.0.1:9601"
origin = "http://127.0.0.1:9601"
source_token_ttl_seconds = 300

[app]
cors_origins = []
public_base_url = "http://chorus-app"
secure_cookies = false
```

#### Variables de entorno por entorno (NO en repo)

| Entorno | Variable | Valor |
|---------|----------|-------|
| **Desarrollo local** | `CHORUS_STORAGE_DATABASE_URL` | `mysql+pymysql://osap2027_dev:devpass@127.0.0.1:3306/osap_chorus` |
| **Tests local/CI** | `CHORUS_STORAGE_DATABASE_URL` | `mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test` |
| **Producción** | `CHORUS_STORAGE_DATABASE_URL` | `mysql+pymysql://osap2027_prod:****@db-host:3306/osap_chorus_prod` |
| **Auth secret (todos)** | `CHORUS_AUTH_OIDC_CLIENT_SECRET` | (secreto real) |

#### Carga en `Settings.load()`

```python
database_url=value("CHORUS_STORAGE_DATABASE_URL", storage, "database_url"),  # env var > toml
```

### 5.3 Garantía de selección inequívoca

| Entorno | `CHORUS_STORAGE_DATABASE_URL` | Base resultante |
|---------|------------------------------|-----------------|
| Dev | `.../osap_chorus` | `osap_chorus` |
| Test | `.../osap_chorus_test` | `osap_chorus_test` (validado por `integration_settings`) |
| Prod | `.../osap_chorus_prod` | `osap_chorus_prod` |

**Un solo origen de verdad**: `CHORUS_STORAGE_DATABASE_URL` (variable de entorno).  
**Ningún archivo** define el nombre de base de datos en producción/tests/desarrollo.

---

## 6. Inventario definitivo de archivos a crear/modificar

### 6.1 Migraciones MySQL (4 archivos reales)

| Archivo | Acción | Contenido |
|---------|--------|-----------|
| `migrations/mysql/001_baseline_schema.sql` | **RENOMBRAR** `001_schema.sql` | Esquema completo (ya existe) |
| `migrations/mysql/002_material_library.sql` | **NUEVO** | `ALTER TABLE resources ADD version_label, part_label, material_status` + `ALTER TABLE files ADD folder_path, display_name, original_name` + índice (de SQLite 012) |
| `migrations/mysql/003_material_groups.sql` | **NUEVO** | `ALTER TABLE resources ADD group_id, group_section_id` + índice (de SQLite 013) |
| `migrations/mysql/004_coral_integration.sql` | **NUEVO** | 12 columnas coral en `groups` (informe coral) |
| `migrations/mysql/999_legacy_baseline.sql` | **NUEVO** | Verificación integridad + registro baseline (SIN DDL) |

**Eliminar**: `migrations/mysql/002_agenda_recurrence.sql`, `migrations/mysql/003_group_articles.sql` (redundantes).

### 6.2 Código aplicación

| Archivo | Cambios |
|---------|---------|
| `app/main.py` | `initialise_database()`: lógica legacy detection + baseline 999 + bucle 001-004 |
| `app/db.py` | Añadir `_execute_sql_script()` con `sqlparse`, `_ensure_migrations_table()`, `_detect_legacy_installation()` |
| `app/config.py` | Sin cambios (ya correcto) |

### 6.3 Scripts

| Archivo | Cambios |
|---------|---------|
| `scripts/rebuild_test_db.py` | **NUEVO** — reconstrucción idempotente con verificación final, sin transacción DDL |
| `scripts/migrate_osap_groups_articles.py` | Actualizar para usar migraciones 001-004 si aplica |

### 6.4 Tests

| Archivo | Cambios |
|---------|---------|
| `tests/conftest.py` | **NUEVO** — fixtures `integration_settings`, `migration_settings` (validación real) |
| `pyproject.toml` | Añadir `sqlparse` a `[dev]` y `[test]`, marcadores `unit/integration/migrations`, `addopts = "-m 'not integration'"` |
| `tests/test_agenda.py`, `test_articles.py`, `test_messages.py`, `test_material.py`, `test_entity_leads.py` | Añadir `@pytest.mark.integration`, usar fixture `integration_settings` |
| `tests/test_creation_drafts.py`, `test_v6_schema.py`, `test_oidc.py`, `test_library_integrity.py` | **REESCRIBIR** para MariaDB (usar `information_schema`, `pymysql.err.IntegrityError`), `@pytest.mark.integration @pytest.mark.migrations` |
| `tests/test_api_runtime.py` | Separar: tests MXL → `@pytest.mark.unit`; test migraciones → reescribir para MariaDB + `@pytest.mark.migrations` |

### 6.5 CI/CD

| Archivo | Cambios |
|---------|---------|
| `.github/workflows/test.yml` | **NUEVO** — 3 jobs: `unit-tests` (sin BD), `integration-tests` (MariaDB 10.4 + rebuild), `migration-tests` (subset) |

### 6.6 Documentación

| Archivo | Cambios |
|---------|---------|
| `docs/mysql.md` | Actualizar: 4 migraciones reales, baseline legacy, variables de entorno, permisos `osap2027_test` |

---

## 7. Orden de implementación (4 fases)

### Fase 1: Migraciones y reconstrucción (fundación)

1. Renombrar `migrations/mysql/001_schema.sql` → `001_baseline_schema.sql`
2. Crear `migrations/mysql/002_material_library.sql` (desde SQLite 012)
3. Crear `migrations/mysql/003_material_groups.sql` (desde SQLite 013)
4. Crear `migrations/mysql/004_coral_integration.sql` (12 columnas coral)
5. Crear `migrations/mysql/999_legacy_baseline.sql` (verificación + registro)
6. Eliminar `migrations/mysql/002_agenda_recurrence.sql` y `003_group_articles.sql`
7. Actualizar `app/db.py`: `_execute_sql_script()` con `sqlparse`, helpers
8. Actualizar `app/main.py`: `initialise_database()` con detección legacy + bucle 001-004
9. Crear `scripts/rebuild_test_db.py` (idempotente, verificación final)
10. Añadir `sqlparse` a `pyproject.toml` `[dev]` y `[test]`
11. Documentar permisos `osap2027_test` en `docs/mysql.md`

### Fase 2: Protección y configuración tests

1. Crear `tests/conftest.py` con `integration_settings`, `migration_settings`
2. Actualizar `pyproject.toml`: marcadores, `addopts`
3. Marcar tests API existentes con `@pytest.mark.integration` + fixture `integration_settings`
4. Verificar: `pytest` (solo unit), `pytest -m integration` (requiere MariaDB)

### Fase 3: Reescritura tests esquema/constraints

1. Reescribir `test_creation_drafts.py` para MariaDB + `@pytest.mark.integration @pytest.mark.migrations`
2. Reescribir `test_v6_schema.py` igual
3. Reescribir `test_oidc.py` igual
4. Reescribir `test_library_integrity.py` igual
5. Reescribir `test_api_runtime.py::test_database_migrations_are_repeatable` para MariaDB
6. Tests MXL en `test_api_runtime.py` → `@pytest.mark.unit` (sin BD)

### Fase 4: CI/CD

1. Crear `.github/workflows/test.yml` con 3 jobs
2. Verificar ejecución completa en GitHub Actions

---

## 8. Criterios de aceptación y comandos de verificación

| Criterio | Comando | Esperado |
|----------|---------|----------|
| **C1** 4 migraciones MySQL reales existen | `ls migrations/mysql/00[1-4]_*.sql | wc -l` | 4 |
| **C2** Baseline legacy existe | `ls migrations/mysql/999_legacy_baseline.sql` | Existe |
| **C3** Migraciones redundantes eliminadas | `ls migrations/mysql/002_agenda_recurrence.sql migrations/mysql/003_group_articles.sql` | No existen |
| **C4** Instalación nueva MySQL: aplica 001-004 | `CHORUS_DATABASE_URL=.../osap_chorus_test python -c "from app.main import initialise_database; from app.config import Settings; initialise_database(Settings.load())" && mysql -u osap2027_test -ptestpass -e "SELECT name FROM chorus_schema_migrations ORDER BY name" osap_chorus_test` | 4 filas: 001, 002, 003, 004 |
| **C5** Instalación legacy compatible: baseline 999 | En BD con esquema completo + solo `mysql_schema_v1`: mismo comando → `SELECT name FROM chorus_schema_migrations` | 5 filas: 001, 002, 003, 004, 999 |
| **C6** Instalación legacy incompleta: baseline falla | En BD sin columnas material: mismo comando → `SELECT name FROM chorus_schema_migrations` | Solo `mysql_schema_v1` (999 no registrada) |
| **C7** `rebuild_test_db.py` reconstruye y verifica | `CHORUS_DATABASE_URL=.../osap_chorus_test python scripts/rebuild_test_db.py` | Exit 0, verificación OK |
| **C8** `rebuild_test_db.py` falla si migración falla | Corromper una migración → ejecutar | Exit != 0 |
| **C9** Tests unitarios corren sin BD | `pytest` | 5+ tests pass, < 5s, sin conexión BD |
| **C10** Tests integración bloqueados sin MariaDB | `unset CHORUS_STORAGE_DATABASE_URL && pytest -m integration` | `RuntimeError` claro, no skip |
| **C11** Tests integración corren con MariaDB | `CHORUS_STORAGE_DATABASE_URL=.../osap_chorus_test pytest -m integration` | 100% pass |
| **C12** GitHub Actions 3 jobs verdes | Push a main | Unit + Integration + Migrations = pass |
| **C13** Sin secrets en repo | `git grep -rE "(password|secret)" -- "*.toml" "*.py" | grep -v "CHORUS_" | grep -v "testpass" | grep -v "placeholder"` | Sin resultados |

---

## 9. Resumen de decisiones clave corregidas

| Decisión | Corrección vs versión anterior |
|----------|-------------------------------|
| **4 migraciones MySQL reales** (no 15, no 3) | Basado en análisis real: 001_schema.sql ya tiene todo excepto 012/013 |
| **Baseline honesto con verificación** (no falsear historial) | `999_legacy_baseline` verifica integridad y registra explícitamente "baseline reconocido" |
| **Reconstrucción sin transacción DDL** | `autocommit=True`, verificación final obligatoria, idempotente |
| **Protección selectiva por marcadores** | Unit tests corren sin BD; integration tests validan conexión real en fixture |
| **Configuración real verificada** | Sin `${VAR}` en toml; `CHORUS_STORAGE_DATABASE_URL` es única fuente de verdad |
| **Tests esquema reescritos para MariaDB** | `information_schema` + `pymysql.err.IntegrityError`, no `sqlite3` |

---

**Fin de la propuesta técnica corregida v2.**

**Próximo paso**: Esperar autorización para implementar Fase 1.