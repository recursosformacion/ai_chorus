# Auditoría: Separación de entornos de desarrollo y pruebas (Chorus 0.14)

**Fecha**: 2026-11-18  
**Ámbito**: Solo análisis — **sin modificaciones**  
**Versión**: Chorus 0.14.0

---

## 1. Estado actual de la arquitectura

### 1.1 Configuración de conexión (`app/config.py`, `app/db.py`)

| Elemento | Valor actual |
|----------|--------------|
| **Configuración** | `Settings` dataclass cargada desde `osap.toml` + variables de entorno |
| **Selector de motor** | `database_url` (MySQL/MariaDB) **o** `database_path` (SQLite) — mutuamente excluyentes |
| **Variable de entorno** | `CHORUS_DATABASE_URL` → `mysql+pymysql://user:pass@host/db` |
| **Fallback SQLite** | `CHORUS_DATABASE_PATH` (default: `var/chorus.sqlite3`) |
| **Adaptador MySQL** | `_MySQLConnection` en `app/db.py`: traduce `?`→`%s`, `INSERT OR IGNORE`→`INSERT IGNORE`, omite `PRAGMA` |
| **Base de datos desarrollo** | `osap_chorus` (hardcoded en scripts, docs, `osap.toml` de ejemplo) |
| **Base de datos pruebas** | **No existe** — todos los tests usan SQLite en `tmp_path` |

**Problema crítico**: No hay forma declarativa de seleccionar `osap_chorus` vs `osap_chorus_test` sin cambiar `CHORUS_DATABASE_URL`. La variable `database_path` solo sirve para SQLite.

---

### 1.2 Migraciones — Diferencia entre SQLite y MySQL

#### SQLite (15 migraciones, `migrations/sqlite/`)

```
001_v6_work_resource_file.sql
002_creation_drafts.sql
003_owner_and_library.sql
004_oidc_states.sql
005_local_draft_source.sql
006_groups_events.sql
007_entity_leads.sql
008_entity_lead_manager.sql
009_messages.sql
010_group_member_roles.sql
011_event_targets.sql
012_material_library.sql
013_material_groups.sql
014_agenda_recurrence.sql
015_group_articles.sql
```

Se ejecutan **todas** en orden dentro de `initialise_database()` (líneas 501-526 `app/main.py`).

#### MySQL/MariaDB (3 migraciones, `migrations/mysql/`)

```
001_schema.sql        -- Esquema COMPLETO (todas las tablas incluidas 006-015 equivalentes)
002_agenda_recurrence.sql   -- Solo ALTER TABLE events (recurrence, series_id, creator_badge)
003_group_articles.sql      -- ALTER TABLE groups + CREATE group_sections, group_articles, group_article_media
```

**Problema crítico**: En `initialise_database()` (líneas 480-496), **si `database_url` está seteado, solo se ejecuta `001_schema.sql`** y se registra como `"mysql_schema_v1"`. **Las migraciones 002 y 003 NUNCA se ejecutan en MySQL**.

```python
# app/main.py líneas 480-496
if settings.database_url:
    conn.executescript((root / "migrations" / "mysql" / "001_schema.sql").read_text("utf-8"))
    applied = conn.execute("SELECT 1 FROM chorus_schema_migrations WHERE name = ?", ("mysql_schema_v1",)).fetchone()
    if applied is None:
        conn.execute("INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)", ("mysql_schema_v1", utcnow()))
    # Solo crea event_targets si no existe
    conn.execute("CREATE TABLE IF NOT EXISTS event_targets ...")
    return  # ← SALE AQUÍ — no ejecuta 002 ni 003
```

**Resultado**: Una instalación MySQL fresca tiene el esquema completo (porque `001_schema.sql` ya incluye todo), pero **las migraciones incrementales 002 y 003 no quedan registradas**, lo que rompe la trazabilidad y la idempotencia en actualizaciones.

---

### 1.3 Tests actuales (`tests/`, `pyproject.toml`)

#### Configuración pytest (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

No hay `conftest.py`, no hay fixtures compartidas, no hay configuración de base de datos de tests.

#### Inventario de tests (9 archivos)

| Archivo | Tests | Motor DB | Dependencias SQLite-específicas |
|---------|-------|----------|--------------------------------|
| `test_api_runtime.py` | 6 | SQLite (`tmp_path`) | `sqlite3.connect`, `sqlite_master`, `PRAGMA` |
| `test_agenda.py` | 5 | SQLite | Ninguna directa (usa `_settings` con SQLite) |
| `test_articles.py` | 5 | SQLite | Ninguna directa |
| `test_creation_drafts.py` | 7 | SQLite **en memoria** | `sqlite3.connect(":memory:")`, `sqlite3.IntegrityError`, migraciones SQLite |
| `test_entity_leads.py` | 3 | SQLite | Ninguna directa |
| `test_library_integrity.py` | ~ | SQLite | `sqlite3.connect` directo |
| `test_material.py` | 2 | SQLite | Ninguna directa |
| `test_messages.py` | ~ | SQLite | Ninguna directa |
| `test_oidc.py` | ~ | SQLite | `sqlite3.connect` directo |
| `test_v6_schema.py` | 8 | SQLite **en memoria** | `sqlite3.connect(":memory:")`, `sqlite3.IntegrityError`, migraciones SQLite |

#### Patrones de uso

- **Tests API/integración** (`test_agenda`, `test_articles`, `test_messages`, `test_material`, `test_entity_leads`): Crean `Settings(database_path=tmp_path/...)` → usan SQLite en archivo temporal. **Fácilmente migrables a MariaDB** cambiando `Settings` a `database_url`.
- **Tests esquema/constraints** (`test_creation_drafts`, `test_v6_schema`, `test_api_runtime::test_database_migrations_are_repeatable`, `test_oidc`, `test_library_integrity`): Usan `sqlite3.connect(":memory:")` o `sqlite3` directo, consultan `sqlite_master`, esperan `sqlite3.IntegrityError`. **NO son portables a MariaDB** sin reescritura.

---

## 2. Archivos implicados

### Configuración y conexión
- `app/config.py` — `Settings.load()`, variables de entorno
- `app/db.py` — `connect()`, `_MySQLConnection`, traducción SQL
- `osap.toml` — configuración por defecto (desarrollo)

### Migraciones
- `app/main.py` — `initialise_database()` (líneas 477-526)
- `migrations/mysql/001_schema.sql`, `002_agenda_recurrence.sql`, `003_group_articles.sql`
- `migrations/sqlite/001_v6_work_resource_file.sql` ... `015_group_articles.sql`

### Tests
- `pyproject.toml` — configuración pytest
- `tests/test_*.py` — 9 archivos de tests
- `tests/test_agenda.py` — helpers compartidos (`_profile`, `install_fake_auth`, `_settings`)

### Scripts y docs
- `scripts/migrate_osap_groups_articles.py` — migración datos OSAP (usa `osap_chorus`)
- `script/migrate_sqlite_to_mysql.py` — migración SQLite→MySQL
- `docs/mysql.md` — documentación uso MySQL

---

## 3. Problemas encontrados

| # | Problema | Archivo/Función | Severidad |
|---|----------|-----------------|-----------|
| 1 | **Migraciones MySQL incompletas**: `initialise_database` solo ejecuta `001_schema.sql` y registra `mysql_schema_v1`; `002` y `003` nunca corren | `app/main.py:480-496` | **Crítico** |
| 2 | **Esquema MySQL monolítico**: `001_schema.sql` incluye tablas de migraciones 006-015, no hay paralelismo con SQLite | `migrations/mysql/001_schema.sql` | **Alto** |
| 3 | **Tests ligados a SQLite**: 5/9 archivos usan `sqlite3` directo, `:memory:`, `sqlite_master`, `sqlite3.IntegrityError` | `tests/test_creation_drafts.py`, `test_v6_schema.py`, `test_api_runtime.py`, `test_oidc.py`, `test_library_integrity.py` | **Alto** |
| 4 | **Sin base de datos de tests**: No existe `osap_chorus_test`; tests no pueden correr contra MariaDB real | — | **Alto** |
| 5 | **Sin protección de entorno**: Tests pueden ejecutarse contra cualquier `CHORUS_DATABASE_URL` (incluyendo producción) | `tests/*.py` | **Crítico** |
| 6 | **Sin fixtures pytest compartidas**: Cada test reimplementa `_settings`, `install_fake_auth`, `_profile` | `tests/*.py` | **Medio** |
| 7 | **Adaptador SQL limitado**: `_MySQLConnection._sql()` solo traduce 4 patrones; no cubre `ON CONFLICT`, `RETURNING`, CTEs complejos | `app/db.py:52-60` | **Medio** |
| 8 | **Nombre BD hardcoded**: `osap_chorus` aparece en scripts, docs, `check_*.py` | `scripts/*.py`, `docs/mysql.md` | **Bajo** |
| 9 | **Sin CI/CD**: No hay GitHub Actions para tests automatizados | — | **Medio** |

---

## 4. Riesgos de compatibilidad con MariaDB 10.4.32

| Riesgo | Detalle | Mitigación |
|--------|---------|------------|
| `JSON_ARRAYAGG` | No existe en MariaDB 10.4 (sí en 10.5+) | Usar Python para construir JSON (ya documentado en informe coral) |
| `CHECK constraints` | MariaDB 10.4 los ignora (solo parsea) | Validar en Python; no confiar en BD |
| `INSERT ... ON DUPLICATE KEY` | Sintaxis distinta a `ON CONFLICT` SQLite | El adaptador ya traduce `INSERT OR IGNORE` → `INSERT IGNORE` |
| `LAST_INSERT_ID()` vs `lastrowid` | Distinto comportamiento con `INSERT IGNORE` | Probar en migraciones |
| `VARCHAR(191)` índices | Requerido para `utf8mb4` + índices únicos compuestos | Ya usado en `001_schema.sql` ✓ |
| `DATETIME` vs `VARCHAR` timestamps | Chorus guarda ISO strings en `VARCHAR(64)` | Mantener consistencia; no usar `DATETIME` nativo |
| Transacciones | `BEGIN IMMEDIATE` → `START TRANSACTION` | Adaptador lo hace ✓ |
| Foreign keys | `ON DELETE CASCADE` soportado | Verificar en `001_schema.sql` ✓ |

---

## 5. Diseño propuesto: Separación de entornos

### 5.1 Bases de datos

| Entorno | Base de datos | Usuario | Propósito |
|---------|---------------|---------|-----------|
| **Desarrollo** | `osap_chorus` | `osap2027_dev` | Simula producción; datos reales/sintéticos; migraciones versionadas |
| **Pruebas** | `osap_chorus_test` | `osap2027_test` | **Solo tests automatizados**; reconstruida desde cero en cada run |
| **Producción** | `osap_chorus_prod` | (separado) | Fuera de alcance |

### 5.2 Configuración por variables de entorno

```bash
# Desarrollo (osap.toml o .env)
CHORUS_DATABASE_URL=mysql+pymysql://osap2027_dev:****@127.0.0.1:3306/osap_chorus
CHORUS_CONFIG=osap.toml

# Tests (inyectado por pytest / CI)
CHORUS_DATABASE_URL=mysql+pymysql://osap2027_test:****@127.0.0.1:3306/osap_chorus_test
CHORUS_CONFIG=osap.toml  # mismo archivo, distinta URL por env var
```

### 5.3 Protección obligatoria en tests

**Archivo nuevo**: `tests/conftest.py` con fixture de sesión que valida la BD:

```python
# tests/conftest.py
import os
import pytest
from urllib.parse import urlparse

@pytest.fixture(scope="session", autouse=True)
def _enforce_test_database():
    """Aborta si CHORUS_DATABASE_URL no apunta a osap_chorus_test."""
    url = os.getenv("CHORUS_DATABASE_URL", "")
    if not url:
        pytest.skip("CHORUS_DATABASE_URL no definido — tests requieren MariaDB test")
    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    db_name = (parsed.path or "").lstrip("/")
    if db_name != "osap_chorus_test":
        raise RuntimeError(
            f"BLOQUEO DE SEGURIDAD: Tests requieren base 'osap_chorus_test', "
            f"pero CHORUS_DATABASE_URL apunta a '{db_name}'. "
            f"Defina CHORUS_DATABASE_URL=mysql+pymysql://.../osap_chorus_test"
        )
```

### 5.4 Reconstrucción de base de pruebas desde cero

**Script nuevo**: `scripts/rebuild_test_db.py`

```python
#!/usr/bin/env python3
"""Reconstruye osap_chorus_test desde cero aplicando todas las migraciones MySQL."""
import os
import sys
import pymysql
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations" / "mysql"

def main():
    url = os.getenv("CHORUS_DATABASE_URL")
    if not url:
        sys.exit("CHORUS_DATABASE_URL requerido")
    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    db_name = (parsed.path or "").lstrip("/")
    if db_name != "osap_chorus_test":
        sys.exit(f"Rehusado: base de datos no es osap_chorus_test (es '{db_name}')")

    conn = pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username or "",
        password=parsed.password or "",
        charset="utf8mb4",
        autocommit=True,
    )
    with conn.cursor() as cur:
        # Dropear y recrear base
        cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
        cur.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"USE `{db_name}`")

        # Aplicar migraciones en orden
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            print(f"Aplicando {sql_file.name}...")
            script = sql_file.read_text("utf-8")
            for stmt in script.split(";"):
                stmt = stmt.strip()
                if stmt and not stmt.startswith("--"):
                    cur.execute(stmt)
    conn.close()
    print("osap_chorus_test reconstruida OK")

if __name__ == "__main__":
    main()
```

### 5.5 Migraciones MySQL — Paralelismo con SQLite

**Opción A (recomendada)**: Mantener `001_schema.sql` como esquema base completo, pero **registrar TODAS las migraciones** en `initialise_database`:

```python
# app/main.py — initialise_database() bloque MySQL
if settings.database_url:
    conn.executescript((root / "migrations" / "mysql" / "001_schema.sql").read_text("utf-8"))
    # Registrar TODAS las migraciones equivalentes como aplicadas
    for name in (
        "mysql_schema_v1",           # 001_schema.sql
        "002_agenda_recurrence",     # 002_agenda_recurrence.sql
        "003_group_articles",        # 003_group_articles.sql
    ):
        applied = conn.execute("SELECT 1 FROM chorus_schema_migrations WHERE name = ?", (name,)).fetchone()
        if applied is None:
            conn.execute("INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)", (name, utcnow()))
    conn.execute("CREATE TABLE IF NOT EXISTS event_targets ...")
    return
```

**Opción B (más limpia)**: Dividir `001_schema.sql` en migraciones incrementales paralelas a SQLite (001-015) y ejecutarlas en bucle igual que SQLite. Más trabajo, mejor trazabilidad.

---

## 6. Cambios necesarios, ordenados por fases

### Fase 1: Preparación de BD y migraciones (sin tocar tests)

| Paso | Acción | Archivos |
|------|--------|----------|
| 1.1 | Corregir `initialise_database` para registrar migraciones 002 y 003 en MySQL | `app/main.py` |
| 1.2 | Crear usuario `osap2027_test` en MariaDB con permisos solo sobre `osap_chorus_test` | (manual DBA) |
| 1.3 | Crear script `scripts/rebuild_test_db.py` | Nuevo |
| 1.4 | Documentar variables de entorno para dev/test en `docs/mysql.md` | `docs/mysql.md` |

### Fase 2: Infraestructura de tests

| Paso | Acción | Archivos |
|------|--------|----------|
| 2.1 | Crear `tests/conftest.py` con fixture `_enforce_test_database` (bloqueo seguridad) | Nuevo |
| 2.2 | Crear fixture `settings_mariadb` que usa `CHORUS_DATABASE_URL` (test) | `tests/conftest.py` |
| 2.3 | Extraer helpers compartidos (`_profile`, `install_fake_auth`, `make_mxl`) a `tests/conftest.py` | `tests/conftest.py`, eliminar duplicados |
| 2.4 | Añadir opción pytest `--mariadb` para seleccionar motor (default: SQLite para velocidad) | `pyproject.toml`, `conftest.py` |

### Fase 3: Migración de tests a MariaDB (incremental)

| Grupo | Tests | Estrategia |
|-------|-------|------------|
| **API/integración** (fáciles) | `test_agenda`, `test_articles`, `test_messages`, `test_material`, `test_entity_leads` | Cambiar `_settings` para usar fixture `settings_mariadb` |
| **Esquema/constraints** (difíciles) | `test_creation_drafts`, `test_v6_schema`, `test_api_runtime::test_database_migrations_are_repeatable`, `test_oidc`, `test_library_integrity` | **Reescribir** usando MariaDB real + `information_schema` / `pymysql.err.IntegrityError` |

### Fase 4: CI/CD

| Paso | Acción |
|------|--------|
| 4.1 | Crear `.github/workflows/test.yml` con MariaDB 10.4 service container |
| 4.2 | Job `test-sqlite` (rápido, PRs) |
| 4.3 | Job `test-mariadb` (completo, merge/main, usa `osap_chorus_test`) |
| 4.4 | Paso `rebuild_test_db` antes de tests MariaDB |

---

## 7. Comandos propuestos para ejecutar tests

### Desarrollo local (SQLite — rápido)

```bash
# Tests unitarios rápidos con SQLite (default)
pytest -x -q

# Tests específicos
pytest tests/test_agenda.py -v
```

### Desarrollo local (MariaDB — real)

```bash
# 1. Preparar base de test (una vez o tras cambios de migraciones)
CHORUS_DATABASE_URL=mysql+pymysql://osap2027_test:****@127.0.0.1:3306/osap_chorus_test \
python scripts/rebuild_test_db.py

# 2. Ejecutar tests contra MariaDB
CHORUS_DATABASE_URL=mysql+pymysql://osap2027_test:****@127.0.0.1:3306/osap_chorus_test \
pytest -x -q
```

### GitHub Actions (CI)

```yaml
# .github/workflows/test.yml (esquema)
jobs:
  test-sqlite:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[test]"
      - run: pytest -x -q

  test-mariadb:
    runs-on: ubuntu-latest
    # Sin contenedores: MariaDB 10.4 nativo via apt
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[test]"
      - name: Rebuild test DB
        env:
          CHORUS_DATABASE_URL: mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test
        run: python scripts/rebuild_test_db.py
      - name: Run tests
        env:
          CHORUS_DATABASE_URL: mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test
        run: pytest -x -q
```

---

## 8. Criterios verificables para considerar terminada esta tarea

| Criterio | Verificación |
|----------|--------------|
| **C1** `initialise_database` registra las 3 migraciones MySQL | `SELECT name FROM chorus_schema_migrations` en `osap_chorus` devuelve `mysql_schema_v1`, `002_agenda_recurrence`, `003_group_articles` |
| **C2** Existe `osap_chorus_test` con usuario dedicado | `mysql -u osap2027_test -p -e "SHOW DATABASES"` lista solo `osap_chorus_test` |
| **C3** `scripts/rebuild_test_db.py` reconstruye esquema completo | Ejecutar script → `SHOW TABLES` en `osap_chorus_test` muestra 20+ tablas |
| **C4** `tests/conftest.py` bloquea tests si BD ≠ `osap_chorus_test` | `CHORUS_DATABASE_URL=.../osap_chorus pytest` → `RuntimeError` con mensaje claro |
| **C5** Tests API/integración pasan contra MariaDB | `CHORUS_DATABASE_URL=.../osap_chorus_test pytest tests/test_agenda.py tests/test_articles.py tests/test_messages.py tests/test_material.py tests/test_entity_leads.py -v` → 100% pass |
| **C6** GitHub Actions ejecuta ambos jobs (SQLite + MariaDB) | Push a main → workflows verdes |
| **C7** No hay credenciales en repositorio | `git grep -i password` → solo placeholders/ejemplos en `.md` |
| **C8** Documentación actualizada | `docs/mysql.md` explica dev/test/prod, variables, comandos |

---

## 9. Resumen de riesgos y decisiones

| Decisión | Justificación |
|----------|---------------|
| **Mantener SQLite para tests rápidos** | Feedback < 5s en PRs; MariaDB solo en CI/merge |
| **Bloqueo obligatorio en `conftest.py`** | Evita accidentes contra dev/prod; fail-fast claro |
| **Reconstrucción desde cero (no transacciones)** | Tests limpios, deterministas, sin "test pollution" |
| **Fase 3 incremental** | Tests de esquema requieren reescritura profunda; no bloquear Fase 1-2 |
| **MariaDB 10.4 en CI** | Coincide con versión declarada; detecta incompatibilidades reales |

---

**Fin de la auditoría. Esperando revisión y autorización para proceder a la implementación por fases.**