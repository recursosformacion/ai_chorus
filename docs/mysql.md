# Chorus sobre MySQL/MariaDB

Chorus usa **MySQL/MariaDB 10.4.32** como único motor de base de datos para desarrollo, tests y producción.

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

`CHORUS_DATABASE_URL` es **obligatorio**. Si no está configurado, Chorus se detiene con un mensaje claro.

## Esquema y migraciones

### Migraciones MySQL (17 archivos)

| Archivo | Descripción |
|---------|-------------|
| `migrations/mysql/001_schema.sql` | Esquema base histórico (18 tablas + chorus_schema_migrations). **NO renombrar ni eliminar** — instalaciones existentes pueden tenerlo registrado. |
| `migrations/mysql/002_agenda_recurrence.sql` | Migración histórica (índice idx_events_series). **Conservar**. |
| `migrations/mysql/003_group_articles.sql` | Migración histórica (3 tablas artículos + ALTER redundantes). **Conservar**. |
| `migrations/mysql/004_material_library.sql` | **Nueva** (desde SQLite 012): columnas material en resources/files + índice. |
| `migrations/mysql/005_material_groups.sql` | **Nueva** (desde SQLite 013): columnas group_id, group_section_id en resources + índice. |
| `migrations/mysql/006_group_articles_tables.sql` | **Nueva** (desde SQLite 015 parte CREATE): 3 tablas group_sections, group_articles, group_article_media. |
| `migrations/mysql/007_events_series_index.sql` | **Nueva** (índice faltante de SQLite 014): CREATE INDEX idx_events_series. |
| `migrations/mysql/016_coral_group_fields.sql` | **Nueva (Fase 2)**: 12 columnas corales en `groups` (foundation_date, dissolution_date, locality, region, country_code, venue, formation_type, member_count, public_email, language JSON, repertoire JSON, venues JSON). |
| `migrations/mysql/017_fix_group_articles_fk.sql` | **Nueva (Fase 3)**: Elimina FKs incorrectas author_user_id/publisher_user_id/reviewed_by → groups.id en group_articles. |
| `migrations/mysql/018_group_types.sql` | **Nueva (Fase 3 Block 1)**: `group_types` (48 catálogos) + `groups.type_code`, `groups.join_code_expires_at`. |
| `migrations/mysql/019_groups_type_code.sql` | **Nueva**: Backfill `groups.type_code` desde `amigos_grupos.tipo_id`. |
| `migrations/mysql/020_group_members_granted_by.sql` | **Nueva**: `group_members.granted_by` (quién otorgó la membresía). |
| `migrations/mysql/021_group_history.sql` | **Nueva**: `group_history` (6 registros migrados desde amigos_*). |
| `migrations/mysql/022_group_articles_scope.sql` | **Nueva**: `group_articles.scope` (general→public, group→group), `group_id` nullable. |
| `migrations/mysql/023_section_templates.sql` | **Nueva**: `section_templates` (273 plantillas desde amigos_seccion_tipo). |
| `migrations/mysql/024_role_templates.sql` | **Nueva**: `role_templates` (409 plantillas desde amigos_roles). |
| `migrations/mysql/025_authorizations.sql` | **Nueva**: `authorizations` (2 registros desde amigos_autorizaciones). |
| `migrations/mysql/026_performances.sql` | **Nueva**: `performances` (1 registro evento desde amigos_actuaciones). |
| `migrations/mysql/027_performance_groups.sql` | **Nueva**: `performance_groups` (tabla de enlace groups↔performances). |
| `migrations/mysql/028_fix_group_articles_group_id_nullable.sql` | **Nueva**: Ajusta `group_articles.group_id` nullable para artículos públicos. |
| `migrations/mysql/029_create_group_roles.sql` | **Nueva (Fase 3 Block 4)**: `group_roles` (16 roles admin/musical desde amigos_group_catalog). |
| `migrations/mysql/030_create_group_social_links.sql` | **Nueva**: `group_social_links` (1 registro desde amigos_group_links). |
| `migrations/mysql/031_create_legacy_uploads.sql` | **Nueva**: `legacy_uploads` (13 registros desde amigos_uploads, file_id BIGINT preservado). |
| `migrations/mysql/032_create_activity_log.sql` | **Nueva**: `activity_log` (57 registros desde amigos_events operacionales). |
| `migrations/mysql/033_add_group_role_refs_to_members.sql` | **Nueva**: `group_members.group_admin_role_id`, `group_musical_role_id` + FKs. |

**NOTA:** No existe `009_legacy_baseline.sql` como archivo SQL. El reconocimiento de instalaciones legacy es una operación Python (`_register_legacy_baseline_recognition` en `app/db.py`).

### Datos corales (Fase 2)

- Migración `016_coral_group_fields.sql` añade 12 columnas nullables a `groups`.
- API: `POST /api/v1/groups` y `PATCH /api/v1/groups/{id}` aceptan y devuelven los 12 campos; `language`/`repertoire`/`venues` se serializan como JSON (lista / lista de `{value,position}`) y se devuelven como objetos, no cadenas.
- Conversión heredada: `scripts/migrate_coral_data.py` lee `osap_api.amigos_coral_details` + `amigos_coral_attributes` (facets `language`, `repertoire`, `place`) y rellena **solo columnas NULL** de grupos existentes (no crea grupos, no sobrescribe, idempotente).
- Mapeo: `details.*` → columnas directas; `attributes facet=language` → `language[]`; `facet=repertoire` → `repertoire[{value,position}]`; `facet=place` → `venues[{value,position}]`. Orden y posiciones originales preservados.

### Nuevas tablas Fase 3 (Block 4) — Migraciones 029–033

| Tabla | Registros | Origen | Descripción |
|-------|-----------|--------|-------------|
| `group_roles` | 16 | `amigos_group_catalog` (admin/musical) | Roles específicos del grupo con scope `admin`/`musical`, jerarquía (parent_id), orden, activación. |
| `group_social_links` | 1 | `amigos_group_links` | Enlaces a redes/web: kind (instagram, facebook, twitter, youtube, website, other), label, url, position. |
| `legacy_uploads` | 13 | `amigos_uploads` | Subidas heredadas: `legacy_file_id` BIGINT preservado, `chorus_file_id` NULL (futura equivalencia). Solo lectura. |
| `activity_log` | 57 | `amigos_events` (operacionales) | Registro de auditoría: event_type, actor, from_status/to_status, detail_json. Triggers automáticos en publish/withdraw article y member role change. |
| `performances` | 1 | `amigos_actuaciones` | Eventos/concertos generales (no específicos de grupo). |
| `performance_groups` | 0 | — | Tabla de enlace groups↔performances (muchos a muchos). |

FKs añadidas en `group_members` (migración 033): `group_admin_role_id` → `group_roles(id)`, `group_musical_role_id` → `group_roles(id)`.

### Ejecutor SQL compartido

- `app/db.py`: `_execute_sql_script()` usando `sqlparse` para dividir sentencias respetando strings, comentarios y bloques.
- `app/db.py`: `_verify_legacy_baseline()` — valida SOLO esquema histórico (001_schema.sql).
- `app/db.py`: `_verify_final_schema()` — valida esquema completo tras migraciones 004-007.
- `app/db.py`: `_register_legacy_baseline_recognition()` — registra reconocimiento legacy (operación Python, no SQL).
- `app/db.py`: `_safe_execute_migration()` — ejecuta migración SOLO si sus objetos esperados NO existen; aborta en estados ambiguos. Los índices secundarios ausentes se recrean (`_ensure_expected_indexes`) en lugar de abortar.

### Adaptador MySQL

- `app/db.py`: `_MySQLConnection` traduce `?` → `%s`, `INSERT OR IGNORE` → `INSERT IGNORE`, `BEGIN IMMEDIATE` → `START TRANSACTION`, omite `PRAGMA`.

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
   - Columnas completas y sólo falta un índice → **recrear el índice y registrar**

## Diagnóstico de migraciones

`scripts/diagnostics/inspect_migrations.py` (solo lectura) muestra conexión, migraciones
registradas, tablas, columnas de material/grupos, índices de 004-007 y el estado de
arranque de cada migración. Útil ante un `RuntimeError` de `_safe_execute_migration()`.

```powershell
$env:CHORUS_DATABASE_URL='mysql+pymysql://user:pass@127.0.0.1:3306/osap_chorus'
python scripts/diagnostics/inspect_migrations.py
python scripts/diagnostics/inspect_migrations.py --migrations 004 005
```

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

- **Unitarios** (`pytest -m unit`): Sin base de datos (~5 tests, <1s)
- **Base de datos** (`pytest -m db`): MariaDB 10.4 real (`osap_chorus_test`) con transacción + rollback
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