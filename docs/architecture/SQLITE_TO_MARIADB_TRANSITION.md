# Inventario y Plan de Transición: SQLite → MariaDB 10.4.32 (Chorus)

**Fecha**: 2026-11-19
**Versión Chorus**: 0.15.0
**Objetivo**: Eliminar SQLite completamente; MariaDB 10.4.32 como único motor en todos los entornos.

---

## 1. Inventario de dependencias SQLite

### 1.1 Código de conexión y configuración

| Archivo | Líneas | Descripción |
|---------|--------|-------------|
| `app/config.py` | 18, 79 | `database_path: str = "var/chorus.sqlite3"` — default SQLite; `CHORUS_DATABASE_PATH` env var |
| `app/db.py` | 1, 3-5, 9, 148-153, 165-167, 179-184, 202-207, 224-227, 484-491 | Doble implementación `_MySQLConnection` / `sqlite3.Connection`; `connect()` elige por `database_url`; helpers `_get_table_names`, `_get_column_names`, `_get_column_type`, `_table_exists`, `_index_exists`, `_count_foreign_keys` con ramas `if hasattr(conn, '_connection')` / `else` (SQLite) |

### 1.2 Inicialización y migraciones

| Archivo | Descripción |
|---------|-------------|
| `app/main.py` | 552-588: rama SQLite con 16 migraciones incrementales (`sqlite_migrations` tupla); 595-702: rama MySQL con 7 migraciones |
| `app/db.py` | 102-135: `_execute_sql_script` / `_translate_mysql` — traduce SQL genérico → MySQL (`?`→`%s`, `INSERT OR IGNORE`→`INSERT IGNORE`, `BEGIN IMMEDIATE`→`START TRANSACTION`, omite `PRAGMA`) |
| `migrations/sqlite/` | **16 archivos** (001-016): esquema incremental para tests unitarios |

### 1.3 Tests que dependen de SQLite

| Archivo | Tipo | Detalle |
|---------|------|---------|
| `tests/test_v6_schema.py` | Unit | Fixture `db()` con `sqlite3.connect(":memory:")`; usa `sqlite3.IntegrityError`; ejecuta migración SQLite 001 directamente |
| `tests/test_creation_drafts.py` | Unit | Fixture `db()` con SQLite en memoria; ejecuta migraciones SQLite 001 + 002; usa `sqlite3.IntegrityError` |
| `tests/test_articles.py` | Unit | Usa `database_path=str(tmp_path / "chorus.sqlite3")` vía `Settings` |
| `tests/test_messages.py` | Unit | Idem |
| `tests/test_material.py` | Unit | Idem |
| `tests/test_entity_leads.py` | Unit | Idem |
| `tests/test_api_runtime.py` | Unit | Idem (3 tests) |
| `tests/test_library_integrity.py` | Unit | Idem + conexión directa `sqlite3.connect(settings.database_path)` |
| `tests/test_oidc.py` | Unit | Idem + conexión directa `sqlite3.connect` para inspeccionar tablas |
| `tests/conftest.py` | Config | Fixtures `integration_settings`, `migration_settings` exigen `CHORUS_DATABASE_URL` (MariaDB); `_clean_groups_for_integration` limpia MariaDB; `pytest_collection_modifyitems` valida marcadores |

### 1.4 Scripts

| Archivo | Descripción |
|---------|-------------|
| `scripts/rebuild_test_db.py` | Solo MySQL — usa `MIGRATIONS` lista MySQL; verifica entorno MariaDB; DROP TABLE en orden FK; ejecuta migraciones MySQL; registra en `chorus_schema_migrations` |
| `scripts/migrate_sqlite_to_mysql.py` | Migración one-shot SQLite→MySQL (legacy) |
| `scripts/diagnostics/check_sqlite.py` | Diagnóstico SQLite |

### 1.5 Configuración pytest y CI

| Archivo | Descripción |
|---------|-------------|
| `pyproject.toml` | 23: `addopts = "-m unit -ra"` — default excluye integration/migrations; 25-28: marcadores `unit`, `integration`, `migrations` |
| `.github/workflows/test.yml` | 3 jobs: `unit-tests` (sin BD, usa SQLite implícito), `integration-tests` (MariaDB nativo), `migration-tests` (MariaDB nativo) |

### 1.6 Documentación

| Archivo | Descripción |
|---------|-------------|
| `docs/mysql.md` | Documenta dualidad: "SQLite solo para tests unitarios"; explica configuración, migraciones, tests, permisos |

---

## 2. Archivos a eliminar

| Archivo | Justificación |
|---------|---------------|
| `migrations/sqlite/` (16 archivos) | Migraciones paralelas innecesarias |
| `scripts/migrate_sqlite_to_mysql.py` | Herramienta legacy one-shot |
| `scripts/diagnostics/check_sqlite.py` | Diagnóstico SQLite |
| `tests/test_v6_schema.py` | Tests de esquema que solo validan SQLite; reemplazar por tests MariaDB |
| `tests/test_creation_drafts.py` | Tests que usan SQLite fixture directo; reescribir contra MariaDB |

---

## 3. Archivos a modificar

| Archivo | Cambios requeridos |
|---------|-------------------|
| `app/config.py` | Eliminar `database_path` default y `CHORUS_DATABASE_PATH`; exigir `database_url` (o `CHORUS_DATABASE_URL`) |
| `app/db.py` | Eliminar rama SQLite completa: `import sqlite3`, clase `_MySQLConnection` pasa a ser única implementación; helpers `_get_table_names`, `_get_column_names`, `_get_column_type`, `_table_exists`, `_index_exists`, `_count_foreign_keys` usan solo `information_schema`/`SHOW`; `connect()` solo retorna `_MySQLConnection`; eliminar `_translate_mysql` (ya no se traduce SQL) |
| `app/main.py` | Eliminar rama SQLite (líneas 558-588); `initialise_database` solo rama MySQL; lista `new_migrations` MySQL únicamente |
| `tests/conftest.py` | Eliminar lógica de detección SQLite; fixtures unitarias usan MariaDB con transacciones/rollback; `_clean_groups_for_integration` ya limpia MariaDB |
| `tests/test_articles.py`, `test_messages.py`, `test_material.py`, `test_entity_leads.py`, `test_api_runtime.py`, `test_library_integrity.py`, `test_oidc.py` | Cambiar `Settings(database_path=...)` a `Settings(database_url=...)` usando fixture MariaDB; añadir `@pytest.mark.integration` o usar fixture `integration_settings` |
| `tests/test_v6_schema.py` → **eliminar**, crear `tests/test_schema_mysql.py` contra MariaDB |
| `tests/test_creation_drafts.py` → **eliminar**, crear `tests/test_creation_drafts_mysql.py` contra MariaDB |
| `pyproject.toml` | Cambiar `addopts = "-m integration -ra"` (default = integration); actualizar descripción marcadores |
| `.github/workflows/test.yml` | Job `unit-tests` → renombrar a `integration-tests-fast` (MariaDB con transacciones); eliminar comentario "sin BD"; mantener 3 jobs pero todos contra MariaDB |
| `docs/mysql.md` | Reescribir: eliminar referencias SQLite; documentar MariaDB como único motor; configuración desarrollo local |

---

## 4. Plan de transición (fases)

### Fase 1: Preparación y tests de reemplazo (sin romper CI actual)

1. **Crear tests MariaDB equivalentes**:
   - `tests/test_schema_mysql.py` — replica `test_v6_schema.py` usando fixture `integration_settings` + transacciones
   - `tests/test_creation_drafts_mysql.py` — replica `test_creation_drafts.py` contra MariaDB

2. **Añadir fixture unitaria MariaDB en `conftest.py`**:
   ```python
   @pytest.fixture
   def unit_db(integration_settings):
       """DB MariaDB para tests rápidos: transacción + rollback automático."""
       conn = db_connect(integration_settings)
       conn.execute("START TRANSACTION")
       yield conn
       conn.rollback()
       conn.close()
   ```

3. **Migrar tests unitarios existentes** (`test_articles.py`, `test_messages.py`, etc.) a usar `unit_db` fixture y marcar `@pytest.mark.integration` (o nuevo marcador `db`).

### Fase 2: Eliminación de código SQLite

1. Modificar `app/config.py`: eliminar `database_path`, exigir `database_url`.
2. Reescribir `app/db.py`: solo `_MySQLConnection`; helpers sin ramas SQLite.
3. Simplificar `app/main.py`: solo rama MySQL en `initialise_database`.
4. Eliminar `migrations/sqlite/`, `scripts/migrate_sqlite_to_mysql.py`, `scripts/diagnostics/check_sqlite.py`.

### Fase 3: Tests y CI

1. Eliminar `test_v6_schema.py`, `test_creation_drafts.py`.
2. Actualizar `pyproject.toml`: `addopts = "-m integration -ra"` (o nuevo marcador `db`).
3. Actualizar `.github/workflows/test.yml`: un solo job `tests` que levanta MariaDB y corre `pytest -m integration` (o `pytest` sin `-m unit`).

### Fase 4: Documentación y validación

1. Reescribir `docs/mysql.md`.
2. Verificar que `initialise_database` falla si `database_url` no está configurado.
3. Ejecutar suite completa contra MariaDB local y en CI.
4. Confirmar que no hay rutas de código que permitan arrancar con SQLite.

---

## 5. Configuración MariaDB para desarrollo local

### Opción A: MariaDB nativo (Linux/macOS)
```bash
# Ubuntu/Debian
sudo apt-get install mariadb-server-10.4

# Arch
sudo pacman -S mariadb

# macOS (Homebrew)
brew install mariadb@10.4
brew services start mariadb@10.4
```

### Opción B: Docker (recomendado para consistencia)
```yaml
# docker-compose.yml para desarrollo
services:
  mariadb:
    image: mariadb:10.4
    environment:
      MYSQL_DATABASE: osap_chorus_dev
      MYSQL_USER: chorus_dev
      MYSQL_PASSWORD: devpass
      MYSQL_ROOT_PASSWORD: rootpass
    ports:
      - "3306:3306"
    volumes:
      - mariadb_dev_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  mariadb_dev_data:
```

### Variables de entorno desarrollo (`osap.toml` o `.env`)
```toml
[storage]
# database_url obligatorio en nueva versión
# database_path ELIMINADO

# Ejemplo local Docker:
# CHORUS_DATABASE_URL=mysql+pymysql://chorus_dev:devpass@127.0.0.1:3306/osap_chorus_dev
```

### Inicialización automática
```bash
# Al arrancar Chorus (sin BD):
# 1. Crea esquema completo vía 001_schema.sql
# 2. Aplica migraciones 004-007, 016, 017
# 3. Registra en chorus_schema_migrations
```

### Tests locales
```bash
# Requiere MariaDB corriendo + osap_chorus_test + osap2027_test
export CHORUS_DATABASE_URL="mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"
pytest -m integration  # tests de integración
pytest -m migrations   # tests de migraciones
pytest                 # todos (default = integration)
```

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Tests unitarios más lentos (MariaDB vs SQLite en memoria) | Usar transacciones + rollback por test; pool de conexiones; MariaDB en tmpfs en CI |
| Incompatibilidad SQL (SQLite vs MariaDB) | Suite de migraciones ya valida esquema MariaDB; `_execute_sql_script` usa sqlparse estándar |
| Datos de desarrollo existentes en SQLite | `scripts/migrate_sqlite_to_mysql.py` disponible antes de eliminar; backup obligatorio |
| CI más lento (levantar MariaDB en unit-tests) | GitHub Actions ya levanta MariaDB nativo en integration/migration jobs; unificar en 1 job reduce overhead total |
| Arranque accidental sin `CHORUS_DATABASE_URL` | `Settings.load()` lanza `RuntimeError` si `database_url` vacío; `initialise_database` falla rápido |

---

## 7. Criterios de finalización (Definition of Done)

- [ ] `app/config.py` sin `database_path` / `CHORUS_DATABASE_PATH`
- [ ] `app/db.py` sin `import sqlite3` ni ramas `else: # sqlite3.Connection`
- [ ] `app/main.py` sin rama SQLite en `initialise_database`
- [ ] `migrations/sqlite/` eliminado
- [ ] `scripts/migrate_sqlite_to_mysql.py` eliminado
- [ ] `scripts/diagnostics/check_sqlite.py` eliminado
- [ ] `tests/test_v6_schema.py` eliminado → `tests/test_schema_mysql.py` creado y pasando
- [ ] `tests/test_creation_drafts.py` eliminado → `tests/test_creation_drafts_mysql.py` creado y pasando
- [ ] Todos los tests unitarios migrados a fixture MariaDB (`unit_db` o `integration_settings`)
- [ ] `pyproject.toml`: `addopts` default = integration (o `db`)
- [ ] `.github/workflows/test.yml`: un job `tests` con MariaDB nativo
- [ ] `docs/mysql.md` reescrito sin referencias SQLite
- [ ] `pytest` (sin flags) ejecuta suite completa contra MariaDB y pasa
- [ ] `initialise_database` falla con error claro si `database_url` no configurado
- [ ] Zero referencias a `sqlite3`, `.sqlite3`, `database_path` en código fuente (excluyendo docs/historial)

---

## 8. Estimación de esfuerzo

| Fase | Archivos | Esfuerzo estimado |
|------|----------|-------------------|
| 1. Tests reemplazo | 2 nuevos + 7 migraciones | 4-6h |
| 2. Código core | 3 archivos (config, db, main) | 3-4h |
| 3. Tests y CI | 9 archivos test + 2 config | 3-4h |
| 4. Docs y validación | 1 doc + verificación | 1-2h |
| **Total** | **~15 archivos** | **11-16h** |

---

## 9. Próximos pasos inmediatos

1. **Crear `tests/test_schema_mysql.py`** y **`tests/test_creation_drafts_mysql.py`** usando fixture `integration_settings` + transacciones
2. **Añadir fixture `unit_db`** en `conftest.py` para tests rápidos con rollback
3. **Migrar un test unitario existente** (ej. `test_articles.py`) a MariaDB como prueba de concepto
4. Validar en CI antes de proceder con eliminación masiva

---

**Nota**: Este plan mantiene compatibilidad hacia atrás durante la transición (Fase 1-2 coexisten). Solo en Fase 3 se elimina SQLite definitivamente. No se modifica producción ni datos existentes en ningún momento.