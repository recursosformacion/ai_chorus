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

MIGRATIONS = [
    "001_schema.sql",
    "004_material_library.sql",
    "005_material_groups.sql",
    "006_group_articles_tables.sql",
    "007_events_series_index.sql",
    "016_coral_group_fields.sql",
    # 009_legacy_baseline NO se ejecuta en reconstrucción desde cero
]


def _verify_test_environment(settings: Settings) -> dict:
    """Valida motor, BD, usuario, host ANTES de operaciones destructivas."""
    conn = db_connect(settings)
    try:
        if not settings.database_url:
            raise RuntimeError("CHORUS_DATABASE_URL no definido (requerido para MariaDB)")

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
        if not info["version"].startswith("10.4."):
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
                "message_recipients", "event_targets", "messages", "entity_leads",
                "event_rsvps", "event_groups", "events", "group_members", "groups",
                "collection_items", "collections", "library_items",
                "editor_source_tokens", "creation_drafts",
                "files", "resources", "works",
                "oidc_states", "group_article_media", "group_articles", "group_sections",
                "chorus_schema_migrations",
            ]
            for table in drop_order:
                conn.execute(f"DROP TABLE IF EXISTS `{table}`")
            conn.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()  # DDL commitea implícito en MariaDB

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
                       'group_sections', 'group_articles', 'group_article_media'}
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

            print("VERIFICACIÓN FINAL: OK")
            return 0

    except Exception as e:
        print(f"ERROR INESPERADO: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())