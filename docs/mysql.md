# Chorus sobre MySQL/MariaDB

Chorus usa **SQLite solo para tests unitarios**. Desarrollo y producción usan MySQL/MariaDB **10.4.32**.

## Configuración

En `osap.toml`:

```toml
[storage]
# database_url se define POR ENTORNO via variable de entorno CHORUS_DATABASE_URL
root = "var/private"
```

O por entorno:

```powershell
$env:CHORUS_DATABASE_URL = "mysql+pymysql://usuario:password@127.0.0.1:3306/osap_chorus"
```

Si `database_url` está vacío, se usa `database_path` (SQLite) para la suite de tests unitarios.

## Esquema y migraciones

### Migraciones MySQL (7 archivos)

| Archivo | Descripción |
|---------|-------------|
| `migrations/mysql/001_schema.sql` | Esquema base histórico (18 tablas + chorus_schema_migrations). **NO renombrar ni eliminar** — instalaciones existentes pueden tenerlo registrado. |
| `migrations/mysql/002_agenda_recurrence.sql` | Migración histórica (índice idx_events_series). **Conservar**. |
| `migrations/mysql/003_group_articles.sql` | Migración histórica (3 tablas artículos + ALTER redundantes). **Conservar**. |
| `migrations/mysql/004_material_library.sql` | **Nueva** (desde SQLite 012): columnas material en resources/files + índice. |
| `migrations/mysql/005_material_groups.sql` | **Nueva** (desde SQLite 013): columnas group_id, group_section_id en resources + índice. |
| `migrations/mysql/006_group_articles_tables.sql` | **Nueva** (desde SQLite 015 parte CREATE): 3 tablas group_sections, group_articles, group_article_media. |
| `migrations/mysql/007_events_series_index.sql` | **Nueva** (índice faltante de SQLite 014): CREATE INDEX idx_events_series. |

**NOTA:** No existe `009_legacy_baseline.sql` como archivo SQL. El reconocimiento de instalaciones legacy es una operación Python (`_register_legacy_baseline_recognition` en `app/db.py`).

### Ejecutor SQL compartido

- `app/db.py`: `_execute_sql_script()` usando `sqlparse` para dividir sentencias respetando strings, comentarios y bloques.
- `app/db.py`: `_verify_legacy_baseline()` — valida SOLO esquema histórico (001_schema.sql).
- `app/db.py`: `_verify_final_schema()` — valida esquema completo tras migraciones 004-007.
- `app/db.py`: `_register_legacy_baseline_recognition()` — registra reconocimiento legacy (operación Python, no SQL).
- `app/db.py`: `_safe_execute_migration()` — ejecuta migración SOLO si sus objetos esperados NO existen; aborta en estados ambiguos.

### Adaptador MySQL

- `app/db.py`: `_MySQLConnection` traduce `?` → `%s`, `INSERT OR IGNORE` → `INSERT IGNORE`, `BEGIN IMMEDIATE` → `START TRANSACTION`, omite `PRAGMA`.
- Las migraciones SQLite se conservan para tests unitarios.

## Inicialización automática

`initialise_database()` en `app/main.py`:

1. **Instalación nueva MySQL** (sin tablas):
   - Ejecuta 001_schema.sql → registra `001_schema.sql`
   - Ejecuta 004→007 en orden → registra cada una
   - NO ejecuta reconocimiento legacy

2. **Instalación histórica** (esquema 001 ya presente):
   - Valida baseline histórico (`_verify_legacy_baseline`): 18 tablas, 14 FKs, columnas críticas
   - Si falla → aborta con error detallado
   - Registra reconocimiento legacy: `001_schema.sql` (legacy-baseline) + `009_legacy_baseline` (timestamp)
   - Analiza estado de 002/003 históricas → salta 006/007 si ya aplicadas
   - Ejecuta 004→007 pendientes

3. **Instalaciones con estados parciales/ambiguos**:
   - Migración registrada pero objetos faltantes → **ABORTAR**
   - Objetos parciales sin registro → **ABORTAR**
   - Objetos existentes sin registro → registrar y saltar (idempotencia)

## Reconstrucción de base de tests

`scripts/rebuild_test_db.py`:

- Solo opera sobre `osap_chorus_test` con usuario `osap2027_test`
- Verifica motor, BD, usuario, versión (línea 10.4; producción usa 10.4.32), grants ANTES de operaciones destructivas
- No usa `CREATE DATABASE` ni `DROP DATABASE`
- DROP TABLE IF EXISTS en orden inverso FK
- Ejecuta migraciones 001, 004-007 en orden, registra tras éxito
- Verificación final en conexión NUEVA (ve estado committeado)
- Exit != 0 en cualquier fallo
- NO ejecuta reconocimiento legacy (solo para instalaciones reales)

## Tests

- **Unitarios** (`pytest`): SQLite en `tmp_path`, sin BD externa (~25 tests, <10s)
- **Integración** (`pytest -m integration`): MariaDB 10.4 real (`osap_chorus_test`)
- **Migraciones** (`pytest -m migrations`): MariaDB 10.4 real, tests de migraciones

Entorno: **Apache + MariaDB local**. La aplicación se ejecuta directamente sobre el sistema (sin contenedores).
CI: 3 jobs (unit, integration, migrations) con MariaDB 10.4 **instalado nativamente vía apt** en `ubuntu-22.04` (sin `services` de contenedor).

## Permisos usuario de pruebas

```sql
CREATE USER 'osap2027_test'@'%' IDENTIFIED BY 'testpass';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES
  ON `osap_chorus_test`.* TO 'osap2027_test'@'%';
-- NO GRANT CREATE DATABASE, DROP DATABASE, SUPER, etc.
FLUSH PRIVILEGES;
```

## Migrar datos (legacy)

```powershell
python scripts/migrate_sqlite_to_mysql.py `
  --sqlite var/chorus.sqlite3 `
  --url "mysql+pymysql://usuario:password@127.0.0.1:3306/osap_chorus"
```

El script crea el esquema, copia todas las tablas conservando IDs y aborta si MySQL ya tiene datos (usar `--replace` solo en desarrollo). No modifica el SQLite.

## Producción

1. Crear base `osap_chorus` (o `osap_chorus_prod`) y usuario con permisos solo sobre ella.
2. Configurar `CHORUS_DATABASE_URL` en el servicio systemd.
3. Reiniciar Chorus y verificar `/health`, agenda y mensajes.