#!/usr/bin/env python3
"""
Reconstruye osap_chorus_test desde cero.
- Solo opera si BD=esquema, usuario=osap2027_test, motor=MariaDB.
- No usa CREATE DATABASE ni DROP DATABASE.
- Ejecuta migraciones en orden, registra tras éxito.
- Verifica resultado en conexión nueva.
- Exit != 0 en cualquier fallo.
"""

import sys
from pathlib import Path

# Añadir path del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.db import connect as db_connect, _execute_sql_script, _verify_final_schema
from app.dbguard import (
    DatabaseUnavailableError,
    UnsafeTestDatabaseError,
    check_effective_connection,
)

MIGRATIONS = [
    "001_schema.sql",
    "004_material_library.sql",
    "005_material_groups.sql",
    "006_group_articles_tables.sql",
    "017_fix_group_articles_fk.sql",
    "007_events_series_index.sql",
    "016_coral_group_fields.sql",
    "018_group_types.sql",
    "019_groups_type_code.sql",
    "020_group_members_granted_by.sql",
    "021_group_history.sql",
    "022_group_articles_scope.sql",
    "023_section_templates.sql",
    "024_role_templates.sql",
    "025_authorizations.sql",
    "026_performances.sql",
    "027_performance_groups.sql",
    "028_fix_group_articles_group_id_nullable.sql",
    "029_create_group_roles.sql",
    "030_create_group_social_links.sql",
    "031_create_legacy_uploads.sql",
    "032_create_activity_log.sql",
    "033_add_group_role_refs_to_members.sql",
    "034_unify_group_member_roles.sql",
    "035_preparation_works.sql",
    "036_add_notification_preferences.sql",
    "037_spaces.sql",
    "038_preparation_work_items.sql",
    "039_preparation_work_files.sql",
    "040_migrate_preparation_works_to_spaces.sql",
    "041_consolidate_spaces.sql",
    "042_personal_projects.sql",
    # 009_legacy_baseline NO se ejecuta en reconstrucción desde cero
]


def _verify_test_environment(settings: Settings) -> dict:
    """Valida motor, BD y usuario ANTES de operaciones destructivas.

    Usa el guard centralizado (app.dbguard): la comprobación se hace sobre la
    conexión efectiva, no sobre el texto de CHORUS_DATABASE_URL.
    """
    if not settings.database_url:
        raise RuntimeError("CHORUS_DATABASE_URL no definido (requerido para MariaDB)")

    conn = db_connect(settings)
    try:
        try:
            effective = check_effective_connection(conn)
        except UnsafeTestDatabaseError as exc:
            raise RuntimeError(str(exc)) from exc

        row = conn.execute(
            "SELECT DATABASE() AS db, CURRENT_USER() AS usr, @@hostname AS host, @@port AS port, @@version AS ver"
        ).fetchone()

        info = {
            "engine": "mariadb",
            "database": row["db"],
            "user": row["usr"].split("@")[0] if row["usr"] else "",
            "host": row["host"],
            "port": row["port"],
            "version": row["ver"],
        }

        if info["database"] != "osap_chorus_test":
            raise RuntimeError(f"BD efectiva '{info['database']}' != 'osap_chorus_test'")
        if info["user"] != "osap2027_test":
            raise RuntimeError(f"Usuario efectivo '{info['user']}' != 'osap2027_test'")

        # Verificar línea MariaDB 10.4 (producción usa 10.4.32)
        if not effective.is_supported_version:
            raise RuntimeError(
                f"Versión MariaDB {info['version']} no es de la línea 10.4 "
                "(producción usa 10.4.32)"
            )

        # Verificar grants efectivos (sin crear objetos)
        grants = conn.execute("SHOW GRANTS FOR CURRENT_USER").fetchall()
        grant_text = " ".join(next(iter(g.values())) for g in grants)
        required_privs = {"SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "INDEX", "ALTER", "REFERENCES"}
        for priv in required_privs:
            if priv not in grant_text:
                raise RuntimeError(f"Falta privilegio {priv} en grants de osap2027_test")

        # Verificar que NO tiene CREATE DATABASE / DROP DATABASE
        if "CREATE DATABASE" in grant_text or "DROP DATABASE" in grant_text:
            raise RuntimeError("Usuario de prueba tiene privilegios globales (CREATE/DROP DATABASE)")

        return info
    finally:
        conn.close()


def _verify_spaces_schema(conn) -> tuple[bool, list[str]]:
    """Verifica el esquema de espacios y trabajos de preparación.

    Comprueba tablas, columnas, nulabilidad, FKs e índices. No modifica la BD.
    """
    errors: list[str] = []

    from app.db import _get_table_names

    required_tables = {'spaces', 'preparation_works', 'preparation_work_items', 'preparation_work_files'}
    existing = set(_get_table_names(conn))
    missing = required_tables - existing
    if missing:
        return False, [f"Tablas spaces faltantes: {sorted(missing)}"]

    def col(table: str, column: str):
        return conn.execute(
            "SELECT IS_NULLABLE, COLUMN_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?",
            (table, column),
        ).fetchone()

    # --- spaces ---
    for column in ('id', 'space_type', 'owner_sub', 'name', 'created_at', 'updated_at'):
        if col('spaces', column) is None:
            errors.append(f"spaces: falta columna {column}")
    row = col('spaces', 'group_id')
    if row is None:
        errors.append("spaces: falta columna group_id")
    elif row['IS_NULLABLE'] != 'YES':
        errors.append("spaces.group_id debe ser NULLABLE (espacios personales)")
    row = col('spaces', 'owner_sub')
    if row is None:
        errors.append("spaces: falta columna owner_sub")
    elif row['IS_NULLABLE'] != 'YES':
        errors.append("spaces.owner_sub debe ser NULLABLE (sólo personal tiene dueño)")
    row = col('spaces', 'space_type')
    if row is not None and 'personal' not in str(row['COLUMN_TYPE']):
        errors.append("spaces.space_type debe incluir 'personal'")
    if col('spaces', 'general_group_id') is None:
        errors.append("spaces: falta columna generada general_group_id (mig 041)")
    check = conn.execute(
        "SELECT COUNT(*) AS n FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'spaces' "
        "AND CONSTRAINT_NAME = 'chk_space_ownership' AND CONSTRAINT_TYPE = 'CHECK'"
    ).fetchone()
    if not check or int(check['n']) != 1:
        errors.append("spaces: falta chk_space_ownership (mig 042)")
    invalid_spaces = conn.execute(
        "SELECT COUNT(*) AS n FROM spaces WHERE NOT ("
        "(space_type='personal' AND owner_sub IS NOT NULL AND group_id IS NULL) OR "
        "(space_type='group' AND owner_sub IS NULL AND group_id IS NOT NULL) OR "
        "(space_type='project' AND ((owner_sub IS NOT NULL AND group_id IS NULL) OR "
        "(owner_sub IS NULL AND group_id IS NOT NULL)))"
    ).fetchone()
    if int(invalid_spaces['n']) != 0:
        errors.append("spaces: existen filas con ownership inválido (mig 042)")

    # --- preparation_works: space_id obligatorio, group_id eliminado ---
    row = col('preparation_works', 'space_id')
    if row is None:
        errors.append("preparation_works: falta columna space_id")
    elif row['IS_NULLABLE'] != 'NO':
        errors.append("preparation_works.space_id debe ser NOT NULL")
    if col('preparation_works', 'group_id') is not None:
        errors.append("preparation_works.group_id debe haberse eliminado (mig 040)")

    # --- preparation_work_items ---
    for column in ('id', 'preparation_work_id', 'work_id', 'resource_id'):
        row = col('preparation_work_items', column)
        if row is None:
            errors.append(f"preparation_work_items: falta columna {column}")
        elif row['IS_NULLABLE'] != 'NO':
            errors.append(f"preparation_work_items.{column} debe ser NOT NULL")

    # --- preparation_work_files ---
    for column in ('id', 'preparation_work_id', 'file_id'):
        row = col('preparation_work_files', column)
        if row is None:
            errors.append(f"preparation_work_files: falta columna {column}")
        elif row['IS_NULLABLE'] != 'NO':
            errors.append(f"preparation_work_files.{column} debe ser NOT NULL")

    # --- FKs esperadas ---
    expected_fks = {
        'spaces': {'fk_space_group'},
        'preparation_works': {'fk_prepworks_space'},
        'preparation_work_items': {'fk_pwi_prepwork', 'fk_pwi_work', 'fk_pwi_resource', 'fk_pwi_work_resource'},
        'preparation_work_files': {'fk_pwf_prepwork', 'fk_pwf_file'},
    }
    for table, names in expected_fks.items():
        rows = conn.execute(
            "SELECT CONSTRAINT_NAME FROM information_schema.REFERENTIAL_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = ?",
            (table,),
        ).fetchall()
        present = {r['CONSTRAINT_NAME'] for r in rows}
        absent = names - present
        if absent:
            errors.append(f"{table}: faltan FKs {sorted(absent)}")
        if table == 'preparation_works' and 'fk_preparation_works_group' in present:
            errors.append("preparation_works: FK antigua fk_preparation_works_group sigue presente")

    # --- Índices esperados ---
    for table, index in (
        ('spaces', 'idx_spaces_owner'),
        ('spaces', 'uq_spaces_general_group'),
        ('preparation_works', 'idx_preparation_works_space'),
        ('preparation_work_items', 'idx_pwi_prepwork'),
        ('preparation_work_files', 'idx_pwf_prepwork'),
    ):
        row = conn.execute(
            "SELECT 1 FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND INDEX_NAME = ?",
            (table, index),
        ).fetchone()
        if row is None:
            errors.append(f"{table}: falta índice {index}")

    # --- Integridad referencial y consistencia de datos ---
    integrity_checks = (
        ("Trabajos sin espacio válido",
         "SELECT COUNT(*) AS c FROM preparation_works pw "
         "LEFT JOIN spaces s ON s.id = pw.space_id WHERE s.id IS NULL"),
        ("Items sin trabajo válido",
         "SELECT COUNT(*) AS c FROM preparation_work_items i "
         "LEFT JOIN preparation_works w ON w.id = i.preparation_work_id WHERE w.id IS NULL"),
        ("Referencias de archivo sin trabajo válido",
         "SELECT COUNT(*) AS c FROM preparation_work_files f "
         "LEFT JOIN preparation_works w ON w.id = f.preparation_work_id WHERE w.id IS NULL"),
        ("Referencias de archivo con file_id inexistente",
         "SELECT COUNT(*) AS c FROM preparation_work_files f "
         "LEFT JOIN files fi ON fi.id = f.file_id WHERE fi.id IS NULL"),
        ("Items con Resource que no pertenece a su Work",
         "SELECT COUNT(*) AS c FROM preparation_work_items i "
         "JOIN resources r ON r.id = i.resource_id WHERE r.work_id <> i.work_id"),
        ("Espacios personales con group_id",
         "SELECT COUNT(*) AS c FROM spaces WHERE space_type = 'personal' AND group_id IS NOT NULL"),
        ("Espacios de grupo/proyecto sin group_id",
         "SELECT COUNT(*) AS c FROM spaces WHERE space_type IN ('group','project') AND group_id IS NULL"),
        ("Espacios no personales con owner_sub",
         "SELECT COUNT(*) AS c FROM spaces WHERE space_type IN ('group','project') AND owner_sub IS NOT NULL"),
        ("Espacios personales sin owner_sub",
         "SELECT COUNT(*) AS c FROM spaces WHERE space_type = 'personal' AND owner_sub IS NULL"),
        ("Grupos con más de un espacio general",
         "SELECT COUNT(*) AS c FROM (SELECT group_id FROM spaces "
         "WHERE space_type = 'group' GROUP BY group_id HAVING COUNT(*) > 1) t"),
    )
    for label, sql in integrity_checks:
        row = conn.execute(sql).fetchone()
        count = int(row["c"]) if row else -1
        if count != 0:
            errors.append(f"integridad: {label} ({count} filas)")

    return len(errors) == 0, errors


def main():
    # 1. Cargar settings (usa CHORUS_DATABASE_URL del entorno)
    settings = Settings.load()

    # 2. Verificar entorno de test
    try:
        info = _verify_test_environment(settings)
        print(f"OK: Conectado a {info['database']} como {info['user']}@{info['host']}:{info['port']} (MariaDB {info['version']})")
    except RuntimeError as e:
        print(f"BLOQUEO: {e}", file=sys.stderr)
        return 1

    # 3. Reconstruir
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations" / "mysql"

    try:
        with db_connect(settings) as conn:
            # 3.1 DROP todas las tablas aplicación (desactivar FK checks temporalmente)
            conn.execute("SET FOREIGN_KEY_CHECKS = 0")
            drop_order = [
                # Espacios y preparación (hijas primero)
                "preparation_work_files",
                "preparation_work_items",
                "preparation_works",
                "spaces",
                "message_recipients", "event_targets", "messages", "entity_leads",
                "event_rsvps", "event_groups", "events", "group_members", "groups",
                "collection_items", "collections", "library_items",
                "editor_source_tokens", "creation_drafts",
                "files", "resources", "works",
                "oidc_states", "group_article_media", "group_articles", "group_sections",
                "group_roles", "group_social_links", "legacy_uploads", "activity_log",
                "section_templates", "role_templates", "authorizations", "performances",
                "performance_groups", "group_types", "group_history",
                "chorus_schema_migrations",
            ]
            for table in drop_order:
                conn.execute(f"DROP TABLE IF EXISTS `{table}`")
            conn.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()  # DDL commitea implícitamente en MariaDB

            # 3.2 Ejecutar migraciones en orden
            for mig_name in MIGRATIONS:
                mig_path = migrations_dir / mig_name
                if not mig_path.exists():
                    print(f"ERROR: Migración no encontrada: {mig_path}", file=sys.stderr)
                    return 1

                script = mig_path.read_text("utf-8")
                try:
                    _execute_sql_script(conn, script, is_mysql=True)
                    conn.commit()
                except Exception as e:
                    print(f"ERROR ejecutando {mig_name}: {e}", file=sys.stderr)
                    return 1

                # Registrar tras éxito
                try:
                    from app.utils import utcnow
                    conn.execute(
                        "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
                        (mig_name, utcnow())
                    )
                    conn.commit()
                except Exception as e:
                    print(f"ERROR registrando {mig_name}: {e}", file=sys.stderr)
                    return 1

                print(f"  Aplicada: {mig_name}")

        # 4. Verificación final en CONEXIÓN NUEVA (ve estado committeado)
        with db_connect(settings) as conn:
            # Verificar tablas
            from app.db import _get_table_names
            tables = set(_get_table_names(conn))
            required = {'works', 'resources', 'files', 'groups', 'group_members', 'events',
                       'group_sections', 'group_articles', 'group_article_media',
                       'group_roles', 'group_social_links', 'legacy_uploads', 'activity_log',
                       'section_templates', 'role_templates', 'authorizations', 'performances',
                       'performance_groups', 'group_types', 'group_history',
                       'preparation_works',
                       'spaces', 'preparation_work_items', 'preparation_work_files'}
            missing = required - tables
            if missing:
                print(f"VERIFICACIÓN FALLIDA: Tablas faltantes {missing}", file=sys.stderr)
                return 1

            # Verificar migraciones registradas
            applied = {row['name'] for row in conn.execute("SELECT name FROM chorus_schema_migrations").fetchall()}
            expected_applied = set(MIGRATIONS)
            if not expected_applied.issubset(applied):
                print(f"VERIFICACIÓN FALLIDA: Migraciones no registradas {expected_applied - applied}", file=sys.stderr)
                return 1

            # Verificar esquema final completo
            ok, errors = _verify_final_schema(conn)
            if not ok:
                print(f"VERIFICACIÓN FALLIDA: {errors}", file=sys.stderr)
                return 1

            # Verificar esquema de espacios y preparación (columnas, nulabilidad, FKs)
            ok, errors = _verify_spaces_schema(conn)
            if not ok:
                print(f"VERIFICACIÓN FALLIDA (spaces): {errors}", file=sys.stderr)
                return 1

            print("VERIFICACIÓN FINAL: OK")
            return 0

    except Exception as e:
        print(f"ERROR INESPERADO: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())