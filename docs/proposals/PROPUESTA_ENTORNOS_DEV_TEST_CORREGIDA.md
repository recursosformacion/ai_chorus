# Chorus 0.15 — Propuesta técnica corregida: Separación de entornos dev/test

**Fecha**: 2026-11-18  
**Versión**: Chorus 0.14.0 (base) → 0.15.0 (target)  
**Ámbito**: Solo análisis y documentación — **sin modificaciones**

---

## 1. Arquitectura final propuesta

### 1.1 Tres entornos, tres bases de datos, tres usuarios

| Entorno | Base de datos | Usuario | Propósito | Credenciales |
|---------|---------------|---------|-----------|--------------|
| **Desarrollo** | `osap_chorus` | `osap2027_dev` | Simula producción; migraciones versionadas; datos reales/sintéticos | `osap.toml` + `CHORUS_DATABASE_URL` |
| **Pruebas (CI/local)** | `osap_chorus_test` | `osap2027_test` | **Solo tests automatizados**; reconstruida desde cero cada run | `CHORUS_DATABASE_URL` inyectado por pytest/CI |
| **Producción** | `osap_chorus_prod` | (dedicado) | Fuera de alcance — gestionado por ops | Sistema externo |

### 1.2 Principios de diseño

- **Cero SQLite en tests de integración**: Todos los tests que tocan BD usan MariaDB 10.4.32 real.
- **Tests unitarios puros** (sin BD): Separados, rápidos, sin fixtures de BD.
- **Protección en tiempo de ejecución**: Verifica la conexión **efectiva** que usa `app.db.connect()`, no solo variables de entorno.
- **Reconstrucción sin privilegios DDL de BD**: `osap2027_test` solo tiene `DROP TABLE`, `CREATE TABLE`, `TRUNCATE` sobre `osap_chorus_test` — la base la crea administración previa.
- **Migraciones honestas**: Solo se registran migraciones cuyos scripts **se han ejecutado realmente**.

---

## 2. Estrategia de migraciones MariaDB — Corrección fundamental

### 2.1 Problema actual

`initialise_database()` en MySQL:
- Ejecuta solo `001_schema.sql` (esquema completo monolítico)
- Registra `"mysql_schema_v1"` como aplicada
- **Nunca ejecuta** `002_agenda_recurrence.sql` ni `003_group_articles.sql`
- **No hay trazabilidad** de qué cambios incrementales están aplicados

### 2.2 Solución: Paralelismo real con migraciones SQLite

**Opción elegida**: Dividir `001_schema.sql` en 15 migraciones incrementales paralelas a SQLite, numeradas `001`–`015`, y ejecutarlas **en bucle idéntico a SQLite**.

#### Nueva estructura `migrations/mysql/`

```
001_v6_work_resource_file.sql      -- works, resources, files
002_creation_drafts.sql            -- creation_drafts, editor_source_tokens
003_owner_and_library.sql          -- library_items, collections, collection_items
004_oidc_states.sql                -- oidc_states
005_local_draft_source.sql         -- (ajustes creation_drafts)
006_groups_events.sql              -- groups, group_members, events, event_groups, event_rsvps, entity_leads
007_entity_leads.sql               -- (ya en 006, mantener por compatibilidad numérica o fusionar)
008_entity_lead_manager.sql        -- entity_managers, entity_memberships
009_messages.sql                   -- messages, message_recipients
010_group_member_roles.sql         -- admin_role_id, musical_role_id, section_id en group_members
011_event_targets.sql              -- event_targets
012_material_library.sql           -- material_status, group_id, group_section_id en resources
013_material_groups.sql            -- (ajustes resources)
014_agenda_recurrence.sql          -- recurrence, recurrence_until, series_id, creator_badge en events
015_group_articles.sql             -- slug, kind, description... en groups + group_sections, group_articles, group_article_media
```

**Cada archivo contiene solo los statements de esa migración** (CREATE TABLE o ALTER TABLE), no el esquema completo.

#### Ejecución unificada en `initialise_database()`

```python
def initialise_database(settings: Settings) -> None:
    root = Path(__file__).resolve().parent.parent
    with _connect(settings) as conn:
        # Asegurar tabla de migraciones
        if settings.database_url:
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

        # Lista unificada de migraciones (nombres coinciden con archivos)
        migration_names = [
            "001_v6_work_resource_file",
            "002_creation_drafts",
            "003_owner_and_library",
            "004_oidc_states",
            "005_local_draft_source",
            "006_groups_events",
            "007_entity_leads",
            "008_entity_lead_manager",
            "009_messages",
            "010_group_member_roles",
            "011_event_targets",
            "012_material_library",
            "013_material_groups",
            "014_agenda_recurrence",
            "015_group_articles",
        ]

        mig_dir = "mysql" if settings.database_url else "sqlite"

        for name in migration_names:
            applied = conn.execute(
                "SELECT 1 FROM chorus_schema_migrations WHERE name = ?", (name,)
            ).fetchone()
            if applied is None:
                sql_path = root / "migrations" / mig_dir / f"{name}.sql"
                script = sql_path.read_text("utf-8")
                _execute_sql_script(conn, script, settings.database_url is not None)
                conn.execute(
                    "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
                    (name, utcnow()),
                )
```

### 2.3 Compatibilidad con instalaciones existentes

**Problema**: Instalaciones MySQL actuales ya tienen el esquema completo (creado por `001_schema.sql` monolítico) y solo tienen registrada `"mysql_schema_v1"`.

**Solución: Migración de "puesta al día" (catch-up)**

Crear `migrations/mysql/016_catchup_existing_installations.sql`:

```sql
-- Migración 016: Registrar migraciones históricas como aplicadas en instalaciones existentes
-- Solo se ejecuta si la BD ya tiene tablas pero solo tiene 'mysql_schema_v1' registrada
-- NO modifica esquema, solo registra en chorus_schema_migrations

-- Esta migración es idempotente: INSERT IGNORE evita duplicados
INSERT IGNORE INTO `chorus_schema_migrations` (`name`, `applied_at`) VALUES
('001_v6_work_resource_file', '2025-01-01T00:00:00+00:00'),
('002_creation_drafts', '2025-01-01T00:00:00+00:00'),
('003_owner_and_library', '2025-01-01T00:00:00+00:00'),
('004_oidc_states', '2025-01-01T00:00:00+00:00'),
('005_local_draft_source', '2025-01-01T00:00:00+00:00'),
('006_groups_events', '2025-01-01T00:00:00+00:00'),
('007_entity_leads', '2025-01-01T00:00:00+00:00'),
('008_entity_lead_manager', '2025-01-01T00:00:00+00:00'),
('009_messages', '2025-01-01T00:00:00+00:00'),
('010_group_member_roles', '2025-01-01T00:00:00+00:00'),
('011_event_targets', '2025-01-01T00:00:00+00:00'),
('012_material_library', '2025-01-01T00:00:00+00:00'),
('013_material_groups', '2025-01-01T00:00:00+00:00'),
('014_agenda_recurrence', '2025-01-01T00:00:00+00:00'),
('015_group_articles', '2025-01-01T00:00:00+00:00');
```

**Lógica en `initialise_database()`**:

```python
# Al inicio, detectar instalación existente MySQL
if settings.database_url:
    has_tables = conn.execute("SHOW TABLES LIKE 'groups'").fetchone() is not None
    has_only_mysql_v1 = conn.execute(
        "SELECT COUNT(*) FROM chorus_schema_migrations WHERE name = 'mysql_schema_v1'"
    ).fetchone()[0] == 1
    total_migrations = conn.execute("SELECT COUNT(*) FROM chorus_schema_migrations").fetchone()[0]

    if has_tables and has_only_mysql_v1 and total_migrations == 1:
        # Instalación legacy: aplicar catch-up
        catchup_path = root / "migrations" / "mysql" / "016_catchup_existing_installations.sql"
        _execute_sql_script(conn, catchup_path.read_text("utf-8"), True)
        # Marcar 016 como aplicada
        conn.execute(
            "INSERT IGNORE INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
            ("016_catchup_existing_installations", utcnow()),
        )
```

**Resultado**:
- Instalaciones nuevas: ejecutan 001–015 en orden, cada una registrada.
- Instalaciones existentes: detectadas, se registran 001–015 como históricas + 016 catch-up.
- Futuras migraciones (017 coral integration, etc.): se añaden a la lista y corren normalmente en ambos casos.

---

## 3. Reconstrucción de `osap_chorus_test` sin privilegios DROP/CREATE DATABASE

### 3.1 Permisos del usuario `osap2027_test`

```sql
-- Ejecutado UNA VEZ por administración (DBA)
CREATE DATABASE IF NOT EXISTS `osap_chorus_test`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'osap2027_test'@'%' IDENTIFIED BY '****';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES
  ON `osap_chorus_test`.* TO 'osap2027_test'@'%';
FLUSH PRIVILEGES;
```

**Nota**: `CREATE` y `DROP` aquí son **a nivel de tabla** (`CREATE TABLE`, `DROP TABLE`), no de base de datos. El usuario **no tiene** `CREATE DATABASE` ni `DROP DATABASE`.

### 3.2 Script de reconstrucción: `scripts/rebuild_test_db.py`

```python
#!/usr/bin/env python3
"""Reconstruye el esquema de osap_chorus_test desde cero.
NO usa DROP DATABASE / CREATE DATABASE.
Requiere: base osap_chorus_test YA EXISTE, usuario con permisos sobre tablas.
"""
import os
import sys
import pymysql
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations" / "mysql"

MIGRATION_NAMES = [
    "001_v6_work_resource_file", "002_creation_drafts", "003_owner_and_library",
    "004_oidc_states", "005_local_draft_source", "006_groups_events",
    "007_entity_leads", "008_entity_lead_manager", "009_messages",
    "010_group_member_roles", "011_event_targets", "012_material_library",
    "013_material_groups", "014_agenda_recurrence", "015_group_articles",
]

def _execute_sql_script(cursor, script: str) -> None:
    """Ejecuta script SQL statement por statement, compatible con MariaDB 10.4."""
    # Usar sqlparse si está disponible, sino fallback simple pero robusto
    try:
        import sqlparse
        statements = sqlparse.split(script)
    except ImportError:
        # Fallback: split por ';' fuera de comillas/strings
        statements = _split_sql_statements(script)

    for stmt in statements:
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        cursor.execute(stmt)

def _split_sql_statements(script: str) -> list[str]:
    """Split robusto de statements SQL sin sqlparse."""
    statements = []
    current = []
    in_single_quote = False
    in_double_quote = False
    in_backtick = False
    i = 0
    while i < len(script):
        ch = script[i]
        if ch == "'" and not in_double_quote and not in_backtick:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote and not in_backtick:
            in_double_quote = not in_double_quote
        elif ch == "`" and not in_single_quote and not in_double_quote:
            in_backtick = not in_backtick
        elif ch == ";" and not in_single_quote and not in_double_quote and not in_backtick:
            statements.append("".join(current))
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    if current:
        statements.append("".join(current))
    return statements

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
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        with conn.cursor() as cur:
            # 1. Desactivar FK checks
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")

            # 2. Dropear TODAS las tablas (no la base)
            cur.execute("SHOW TABLES")
            tables = [row[f"Tables_in_{db_name}"] for row in cur.fetchall()]
            for table in tables:
                cur.execute(f"DROP TABLE IF EXISTS `{table}`")
            print(f"  Tablas eliminadas: {len(tables)}")

            # 3. Recrear tabla de migraciones primero
            cur.execute("""
                CREATE TABLE `chorus_schema_migrations` (
                    `name` VARCHAR(191) PRIMARY KEY,
                    `applied_at` VARCHAR(64) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # 4. Aplicar migraciones 001-015 en orden
            for name in MIGRATION_NAMES:
                sql_path = MIGRATIONS_DIR / f"{name}.sql"
                if not sql_path.exists():
                    print(f"  ADVERTENCIA: {sql_path} no existe, saltando")
                    continue
                print(f"  Aplicando {name}...")
                script = sql_path.read_text("utf-8")
                _execute_sql_script(cur, script)
                cur.execute(
                    "INSERT INTO `chorus_schema_migrations` (`name`, `applied_at`) VALUES (%s, %s)",
                    (name, "2026-01-01T00:00:00+00:00"),
                )

            # 5. Reactivar FK checks
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        conn.commit()
        print("Reconstrucción completada OK")
        return 0

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
```

**Puntos clave**:
- Usa `sqlparse` si está disponible (dependencia opcional en `pyproject.toml`), fallback robusto si no.
- Solo `DROP TABLE` / `CREATE TABLE` — sin tocar la base de datos.
- Transacción única: todo o nada.
- Registra migraciones con timestamp fijo para reproducibilidad.

---

## 4. Protección de tests: Verificación de conexión EFECTIVA

### 4.1 Principio

La protección **no** lee `CHORUS_DATABASE_URL`. Obtiene la conexión real que usa `app.db.connect(settings)` y verifica la base de datos **efectiva**.

### 4.2 Implementación: `tests/conftest.py`

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
            # MySQL: SELECT DATABASE()
            row = conn.execute("SELECT DATABASE() AS db").fetchone()
            return row["db"] if row else ""
        else:
            # SQLite: PRAGMA database_list
            row = conn.execute("PRAGMA database_list").fetchone()
            # El archivo principal está en seq=0
            path = row[2] if row else ""
            return os.path.basename(path) if path else "sqlite_memory"
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def _enforce_test_database():
    """
    Fixture de sesión que se ejecuta ANTES de cualquier test.
    Verifica que la conexión efectiva apunta a osap_chorus_test.
    """
    # Cargar settings exactamente como lo hace la app (osap.toml + env vars)
    settings = Settings.load()

    # Verificación de seguridad
    effective_db = _get_effective_database_name(settings)

    if effective_db != "osap_chorus_test":
        raise RuntimeError(
            f"BLOQUEO DE SEGURIDAD: La conexión EFECTIVA de Chorus apunta a '{effective_db}', "
            f"pero los tests de integración requieren 'osap_chorus_test'.\n"
            f"Configuración detectada:\n"
            f"  database_url = {settings.database_url or '(vacío → SQLite)'}\n"
            f"  database_path = {settings.database_path}\n\n"
            f"Solución: Defina CHORUS_DATABASE_URL=mysql+pymysql://.../osap_chorus_test "
            f"antes de ejecutar pytest."
        )

    # Si pasa, la sesión continúa
    yield

    # Teardown opcional: no necesario
```

### 4.3 Uso en tests de integración

```python
# tests/test_agenda.py (ejemplo)
import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

# Tests de integración: requieren MariaDB
@pytest.mark.integration
def test_create_group_event_and_rsvp(tmp_path, monkeypatch):
    # _enforce_test_database ya corrió en conftest.py
    settings = Settings.load()  # Usa CHORUS_DATABASE_URL del entorno
    # ... resto del test igual, pero con settings real
```

### 4.4 Separación de tests: Marcadores pytest

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -m 'not integration'"  # Por defecto: SOLO tests unitarios (sin BD)
markers = [
    "unit: tests sin base de datos (rápidos, default)",
    "integration: tests que requieren MariaDB 10.4.32 real",
    "migrations: tests de migraciones específicamente",
]
```

**Ejecución**:
```bash
# Tests unitarios rápidos (default, sin BD)
pytest

# Tests de integración (requieren MariaDB + osap_chorus_test)
pytest -m integration

# Todos
pytest -m "unit or integration"
```

---

## 5. Inventario corregido de archivos y tests

### 5.1 Archivos de configuración y BD

| Archivo | Rol | Cambios requeridos |
|---------|-----|-------------------|
| `app/config.py` | `Settings.load()` — carga `osap.toml` + env vars | Ninguno (ya correcto) |
| `app/db.py` | `connect()`, `_MySQLConnection` | Añadir `_get_effective_database_name()` helper |
| `app/main.py` | `initialise_database()` | Reescribir para migraciones paralelas 001-015 + catch-up 016 |
| `osap.toml` | Config por defecto (dev) | Documentar que `database_url` apunta a `osap_chorus` |

### 5.2 Migraciones MySQL (NUEVAS: 15 archivos paralelos a SQLite)

| Archivo | Contenido | Origen |
|---------|-----------|--------|
| `migrations/mysql/001_v6_work_resource_file.sql` | CREATE works, resources, files | Extraído de `001_schema.sql` |
| `migrations/mysql/002_creation_drafts.sql` | CREATE creation_drafts, editor_source_tokens | Extraído de `001_schema.sql` |
| `migrations/mysql/003_owner_and_library.sql` | CREATE library_items, collections, collection_items | Extraído de `001_schema.sql` |
| `migrations/mysql/004_oidc_states.sql` | CREATE oidc_states | Extraído de `001_schema.sql` |
| `migrations/mysql/005_local_draft_source.sql` | ALTER creation_drafts (source_kind checks) | Extraído de `001_schema.sql` |
| `migrations/mysql/006_groups_events.sql` | CREATE groups, group_members, events, event_groups, event_rsvps, entity_leads | Extraído de `001_schema.sql` |
| `migrations/mysql/007_entity_leads.sql` | (fusionar con 006 o mantener vacío por compatibilidad) | — |
| `migrations/mysql/008_entity_lead_manager.sql` | CREATE entity_managers, entity_memberships | Nuevo (roadmap 4.12) |
| `migrations/mysql/009_messages.sql` | CREATE messages, message_recipients | Extraído de `001_schema.sql` |
| `migrations/mysql/010_group_member_roles.sql` | ALTER group_members ADD admin_role_id, musical_role_id, section_id | `003_group_articles.sql` (parcial) |
| `migrations/mysql/011_event_targets.sql` | CREATE event_targets | `002_agenda_recurrence.sql` (parcial) |
| `migrations/mysql/012_material_library.sql` | ALTER resources ADD group_id, group_section_id | `migrations/sqlite/013_material_groups.sql` |
| `migrations/mysql/013_material_groups.sql` | (ajustes resources) | — |
| `migrations/mysql/014_agenda_recurrence.sql` | ALTER events ADD recurrence, recurrence_until, series_id, creator_badge | `002_agenda_recurrence.sql` |
| `migrations/mysql/015_group_articles.sql` | ALTER groups + CREATE group_sections, group_articles, group_article_media | `003_group_articles.sql` |
| `migrations/mysql/016_catchup_existing_installations.sql` | INSERT IGNORE migraciones históricas | **NUEVO** |

### 5.3 Tests — Clasificación

| Tipo | Archivos | Motor BD | Marcador pytest |
|------|----------|----------|-----------------|
| **Unitarios (sin BD)** | `test_api_runtime.py` (parcial: `test_valid_mxl_container`, `test_only_mxl_extension`, `test_zip_without_container`, `test_non_musicxml_root`, `test_path_traversal`) | Ninguno | `@pytest.mark.unit` |
| **Integración - API/Grupos** | `test_agenda.py`, `test_articles.py`, `test_messages.py`, `test_material.py`, `test_entity_leads.py` | MariaDB 10.4.32 | `@pytest.mark.integration` |
| **Integración - Migraciones** | `test_api_runtime.py::test_database_migrations_are_repeatable` (reescrito para MariaDB) | MariaDB 10.4.32 | `@pytest.mark.integration @pytest.mark.migrations` |
| **Integración - Esquema/Constraints** | `test_creation_drafts.py`, `test_v6_schema.py`, `test_oidc.py`, `test_library_integrity.py` | **Reescribir para MariaDB** usando `information_schema` y `pymysql.err.IntegrityError` | `@pytest.mark.integration @pytest.mark.migrations` |

**Tests unitarios puros (5)**: Validación MXL, helpers, no tocan BD.
**Tests de integración (14+)**: Todos requieren MariaDB real.

---

## 6. Resolución de configuración: `osap.toml` + variables de entorno

### 6.1 Prioridad (ya implementada en `Settings.load()`)

```python
def value(env: str, section: dict, key: str, default: str = "") -> str:
    return os.getenv(env, str(section.get(key, default))).strip()
```

**Orden**: Variable de entorno > `osap.toml` > default.

### 6.2 Configuración por entorno

#### Desarrollo (`osap.toml` en repo, sin secrets)

```toml
# osap.toml (committed, sin contraseñas)
[storage]
database_url = "mysql+pymysql://osap2027_dev:${CHORUS_DB_DEV_PASSWORD}@127.0.0.1:3306/osap_chorus"
root = "var/private"

[auth]
base_url = "http://osap-auth/auth-api"
# ... resto
```

```bash
# .env.local (NO committed, solo dev local)
CHORUS_DB_DEV_PASSWORD=devpass
```

#### Tests (inyectado por pytest/CI, NO en osap.toml)

```bash
# Local
export CHORUS_DATABASE_URL=mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test
pytest -m integration

# GitHub Actions (secrets)
env:
  CHORUS_DATABASE_URL: mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test
```

#### Producción (fuera de repo, systemd/k8s)

```bash
# /etc/chorus/osap.toml (solo en servidor prod)
[storage]
database_url = "mysql+pymysql://osap2027_prod:${CHORUS_DB_PROD_PASSWORD}@db-host:3306/osap_chorus_prod"
```

### 6.3 Garantía de selección inequívoca

| Entorno | `CHORUS_DATABASE_URL` | Base resultante |
|---------|----------------------|-----------------|
| Dev local | `.../osap_chorus` | `osap_chorus` |
| Tests local/CI | `.../osap_chorus_test` | `osap_chorus_test` (bloqueado por `_enforce_test_database`) |
| Prod | `.../osap_chorus_prod` | `osap_chorus_prod` |

**Ningún entorno comparte base de datos**. La variable de entorno es la **única** fuente de verdad para el nombre de BD en runtime.

---

## 7. Ejecución SQL robusta: Sustituir `split(";")`

### 7.1 Problema actual

`_MySQLConnection.executescript()` y `rebuild_test_db.py` usan `script.split(";")` que falla con:
- `;` dentro de strings (`'valor;con;punto y coma'`)
- `;` dentro de triggers/procedures
- Comentarios multilínea

### 7.2 Solución: `sqlparse` (dependencia ligera, estándar)

**Añadir a `pyproject.toml`**:

```toml
[project.optional-dependencies]
test = ["pytest>=8,<9", "sqlparse>=0.4,<1"]
dev = ["sqlparse>=0.4,<1"]
```

**Helper compartido en `app/db.py`**:

```python
def _execute_sql_script(conn, script: str, is_mysql: bool) -> None:
    """Ejecuta script SQL statement por statement de forma robusta."""
    import sqlparse

    # Limpiar comentarios de línea completa
    cleaned = "\n".join(
        line for line in script.splitlines()
        if not line.strip().startswith("--")
    )

    statements = sqlparse.split(cleaned)
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        # Traducción SQLite -> MySQL si necesario
        if is_mysql:
            stmt = stmt.replace("?", "%s")
            stmt = stmt.replace("INSERT OR IGNORE", "INSERT IGNORE")
            stmt = stmt.replace("INSERT OR REPLACE", "REPLACE INTO")
            stmt = stmt.replace("BEGIN IMMEDIATE", "START TRANSACTION")
        conn.execute(stmt)
```

**Usar en**:
- `app/main.py` → `initialise_database()`
- `_MySQLConnection.executescript()`
- `scripts/rebuild_test_db.py`

---

## 8. GitHub Actions: MariaDB 10.4.32 + base aislada

### 8.1 Workflow: `.github/workflows/test.yml`

```yaml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  # Variables comunes
  CHORUS_CONFIG: osap.toml

jobs:
  # ---------------------------------------------------------
  # Tests unitarios (sin BD) - RÁPIDOS, en todos los PRs
  # ---------------------------------------------------------
  unit-tests:
    name: Unit tests (no DB)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[test]"
      - name: Run unit tests
        run: pytest -m unit -x -q

  # ---------------------------------------------------------
  # Tests de integración - MariaDB 10.4.32 real
  # ---------------------------------------------------------
  integration-tests:
    name: Integration tests (MariaDB 10.4)
    runs-on: ubuntu-latest
    timeout-minutes: 15
    # Sin contenedores: MariaDB 10.4 nativo via apt
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[test]"
      - name: Wait for MariaDB ready
        run: |
          for i in {1..30}; do
            if mysqladmin ping -h 127.0.0.1 -u root -prootpass --silent; then
              echo "MariaDB ready"
              break
            fi
            sleep 2
          done
      - name: Rebuild test database
        env:
          CHORUS_DATABASE_URL: mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test
        run: python scripts/rebuild_test_db.py
      - name: Run migration tests
        env:
          CHORUS_DATABASE_URL: mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test
        run: pytest -m migrations -x -v
```

### 8.2 Puntos clave

- **Tres jobs separados**: unit (rápido, sin BD), integration (completo), migrations (específico).
- **MariaDB 10.4 exacto**: `# nativo: apt install mariadb-server`.
- **Base aislada**: `osap_chorus_test` creada por el contenedor (`MYSQL_DATABASE`).
- **Usuario de tests**: `osap2027_test` con permisos solo sobre esa BD.
- **Reconstrucción obligatoria**: `rebuild_test_db.py` antes de cada job de integración.
- **Sin secrets de dev/prod**: Solo `testpass`/`rootpass` hardcoded en CI (base efímera).

---

## 9. Credenciales: Cero uso de dev/prod en tests

| Credencial | Dónde se usa | Dónde NO se usa |
|------------|--------------|-----------------|
| `osap2027_dev` / password dev | Desarrollo local, `osap.toml` con `${CHORUS_DB_DEV_PASSWORD}` | Tests, CI, repositorio |
| `osap2027_test` / `testpass` | **Solo** tests locales + GitHub Actions | Desarrollo, producción, repositorio |
| `osap2027_prod` / password prod | **Solo** sistema de producción (systemd/k8s) | Desarrollo, tests, CI, repositorio |

**En repositorio**:
- `osap.toml` usa `${CHORUS_DB_DEV_PASSWORD}` (placeholder, no valor real)
- `.github/workflows/test.yml` usa `testpass`/`rootpass` hardcoded (base efímera de CI, no sensible)
- **Ningún archivo** contiene passwords reales de dev/prod

---

## 10. Orden de implementación

### Fase 1: Migraciones y reconstrucción (fundación)

| Paso | Acción | Entregable |
|------|--------|------------|
| 1.1 | Dividir `001_schema.sql` en 15 migraciones paralelas `migrations/mysql/001`–`015` | 15 archivos `.sql` |
| 1.2 | Crear `migrations/mysql/016_catchup_existing_installations.sql` | 1 archivo `.sql` |
| 1.3 | Reescribir `initialise_database()` con bucle unificado + detección legacy | `app/main.py` |
| 1.4 | Añadir `_execute_sql_script()` con `sqlparse` a `app/db.py` | `app/db.py` |
| 1.5 | Crear `scripts/rebuild_test_db.py` con split robusto | `scripts/rebuild_test_db.py` |
| 1.6 | Añadir `sqlparse` a `pyproject.toml` `[dev]` y `[test]` | `pyproject.toml` |
| 1.7 | Documentar permisos `osap2027_test` en `docs/mysql.md` | `docs/mysql.md` |

### Fase 2: Protección y configuración de tests

| Paso | Acción | Entregable |
|------|--------|------------|
| 2.1 | Crear `tests/conftest.py` con `_enforce_test_database` (verificación conexión efectiva) | `tests/conftest.py` |
| 2.2 | Añadir marcadores `unit`, `integration`, `migrations` a `pyproject.toml` | `pyproject.toml` |
| 2.3 | Clasificar tests existentes: mover 5 tests unitarios puros a `@pytest.mark.unit` | `tests/test_api_runtime.py` (parcial) |
| 2.4 | Marcar tests de integración existentes con `@pytest.mark.integration` | `test_agenda.py`, `test_articles.py`, `test_messages.py`, `test_material.py`, `test_entity_leads.py` |

### Fase 3: Reescritura de tests de esquema/constraints para MariaDB

| Paso | Acción | Entregable |
|------|--------|------------|
| 3.1 | Reescribir `test_creation_drafts.py` usando MariaDB + `information_schema` + `pymysql.err.IntegrityError` | `tests/test_creation_drafts.py` |
| 3.2 | Reescribir `test_v6_schema.py` igual | `tests/test_v6_schema.py` |
| 3.3 | Reescribir `test_oidc.py` igual | `tests/test_oidc.py` |
| 3.4 | Reescribir `test_library_integrity.py` igual | `tests/test_library_integrity.py` |
| 3.5 | Reescribir `test_api_runtime.py::test_database_migrations_are_repeatable` para MariaDB | `tests/test_api_runtime.py` |
| 3.6 | Marcar todos con `@pytest.mark.integration @pytest.mark.migrations` | — |

### Fase 4: CI/CD

| Paso | Acción | Entregable |
|------|--------|------------|
| 4.1 | Crear `.github/workflows/test.yml` con 3 jobs (unit, integration, migrations) | `.github/workflows/test.yml` |
| 4.2 | Verificar ejecución local: `pytest -m unit`, `pytest -m integration` | Documentación |

---

## 11. Criterios de aceptación y comandos de verificación

| Criterio | Comando de verificación | Esperado |
|----------|------------------------|----------|
| **C1** Migraciones MySQL paralelas 001-015 existen | `ls migrations/mysql/0[0-9][0-9]_*.sql | wc -l` | 15 archivos |
| **C2** Catch-up 016 existe | `ls migrations/mysql/016_catchup_existing_installations.sql` | Existe |
| **C3** `initialise_database` registra 001-015 en instalación nueva | `CHORUS_DATABASE_URL=.../osap_chorus_test python -c "from app.main import initialise_database; from app.config import Settings; initialise_database(Settings.load())" && mysql -u osap2027_test -ptestpass -e "SELECT name FROM chorus_schema_migrations ORDER BY name" osap_chorus_test` | 16 filas (001-015 + 016) |
| **C4** Instalación legacy detectada y catch-up aplicado | En BD con esquema completo + solo `mysql_schema_v1`: ejecutar inicialización → `SELECT COUNT(*) FROM chorus_schema_migrations` | 17 (001-015 + 016 + mysql_schema_v1) |
| **C5** `rebuild_test_db.py` reconstruye sin DROP DATABASE | `CHORUS_DATABASE_URL=.../osap_chorus_test python scripts/rebuild_test_db.py` | Exit 0, tablas recreadas |
| **C6** `_enforce_test_database` bloquea si BD ≠ osap_chorus_test | `CHORUS_DATABASE_URL=.../osap_chorus pytest -m integration` | `RuntimeError` con mensaje claro |
| **C7** `_enforce_test_database` permite si BD = osap_chorus_test | `CHORUS_DATABASE_URL=.../osap_chorus_test pytest -m integration` | Tests corren (o fallan por lógica, no por bloqueo) |
| **C8** Tests unitarios corren sin BD | `pytest -m unit` | 5 tests pass, < 5s |
| **C9** Tests integración corren contra MariaDB | `CHORUS_DATABASE_URL=.../osap_chorus_test pytest -m integration` | 100% pass |
| **C10** GitHub Actions pasa los 3 jobs | Push a main → Actions | 3 jobs verdes |
| **C11** Sin credenciales dev/prod en repo | `git grep -rE "(osap2027_dev|osap2027_prod|2027osapdb)" -- "*.toml" "*.py" "*.yml" "*.md" | grep -v "CHORUS_DB_DEV_PASSWORD" | grep -v "testpass" | grep -v "placeholder"` | Sin resultados |

---

## 12. Resumen de decisiones clave

| Decisión | Justificación |
|----------|---------------|
| **15 migraciones MySQL paralelas a SQLite** | Trazabilidad real, idempotencia, compatibilidad futura |
| **Catch-up 016 para instalaciones legacy** | No romper existentes; migración honesta sin "falsos positivos" |
| **`sqlparse` para ejecución SQL** | Robustez ante `;` en strings, triggers, comentarios; estándar de facto |
| **Verificación de conexión EFECTIVA** | Seguridad real: evita errores de configuración, no solo env vars |
| **Marcadores pytest `unit`/`integration`** | Separación clara; default rápido (unit); CI corre integration |
| **Reescritura tests esquema para MariaDB** | `sqlite3.IntegrityError` ≠ `pymysql.err.IntegrityError`; `sqlite_master` ≠ `information_schema` |
| **`rebuild_test_db.py` sin DROP DATABASE** | Usuario de tests sin privilegios de admin; base creada por DBA |
| **Tres jobs CI separados** | Feedback rápido (unit), cobertura real (integration), específicas (migrations) |
| **Cero credenciales reales en repo** | Seguridad; placeholders en `osap.toml`, secrets solo en CI/runtime |

---

**Fin de la propuesta técnica corregida.**

**Próximo paso**: Esperar autorización para implementar por fases (Fase 1 → 4).