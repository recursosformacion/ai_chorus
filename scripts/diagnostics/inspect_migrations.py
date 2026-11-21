#!/usr/bin/env python3
"""Inspecciona el estado de esquema y migraciones de la base de datos de Chorus.

Comprueba qué migraciones están registradas en `chorus_schema_migrations` y si
sus objetos (columnas, tablas e índices) existen realmente, señalando los casos
que `initialise_database()` rechazaría al arrancar.

Uso:
    python scripts/diagnostics/inspect_migrations.py
    python scripts/diagnostics/inspect_migrations.py --migrations 004 005

La conexión se toma de `CHORUS_DATABASE_URL` (o de `osap.toml`), igual que la
aplicación. Es una herramienta de SOLO LECTURA: no crea ni modifica objetos.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import db as dbm
from app.config import Settings

# Columnas clave por tabla que interesan en la revisión de material y grupos.
_INSPECTED_COLUMNS = {
    "resources": ("material_status", "version_label", "part_label", "group_id", "group_section_id"),
    "files": ("folder_path", "display_name", "original_name"),
}

_ARTICLE_TABLES = ("group_sections", "group_articles", "group_article_media")

# Migraciones con reglas de verificación declaradas en app/db.py.
_KNOWN_MIGRATIONS = (
    "001_schema.sql",
    "004_material_library.sql",
    "005_material_groups.sql",
    "006_group_articles_tables.sql",
    "007_events_series_index.sql",
)


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _show_server(conn) -> None:
    row = conn.execute(
        "SELECT DATABASE() AS db, CURRENT_USER() AS usr, @@version AS ver"
    ).fetchone()
    print(f"Base de datos : {row['db']}")
    print(f"Usuario       : {row['usr']}")
    print(f"Versión       : {row['ver']}")


def _show_migrations(conn) -> dict[str, str]:
    _print_header("Migraciones registradas")
    rows = conn.execute(
        "SELECT name, applied_at FROM chorus_schema_migrations ORDER BY name"
    ).fetchall()
    if not rows:
        print("  (ninguna)")
        return {}
    for row in rows:
        print(f"  {row['name']:<45} {row['applied_at']}")
    return {row["name"]: row["applied_at"] for row in rows}


def _show_tables(conn) -> None:
    _print_header("Tablas")
    tables = sorted(dbm._get_table_names(conn))
    print(f"  {len(tables)} tablas: {', '.join(tables)}")

    present = [t for t in _ARTICLE_TABLES if t in tables]
    state = "completas" if len(present) == len(_ARTICLE_TABLES) else ("parciales" if present else "ausentes")
    print(f"  Artículos: {state} ({', '.join(present) or 'ninguna'})")


def _show_columns(conn) -> None:
    _print_header("Columnas de material y grupos")
    for table, columns in _INSPECTED_COLUMNS.items():
        existing = dbm._get_column_names(conn, table)
        print(f"  {table}:")
        for column in columns:
            row = conn.execute(
                "SELECT COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?",
                (table, column),
            ).fetchone()
            if row is None:
                print(f"    - {column:<18} FALTA")
            else:
                print(
                    f"    - {column:<18} {row['COLUMN_TYPE']:<14} "
                    f"NULL={row['IS_NULLABLE']} DEFAULT={row['COLUMN_DEFAULT']}"
                )
        if not existing:
            print("    (la tabla no existe)")


def _show_indexes(conn) -> None:
    _print_header("Índices gestionados por 004-007")
    for table in ("resources", "events"):
        rows = conn.execute(
            "SELECT INDEX_NAME, GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS cols "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? "
            "GROUP BY INDEX_NAME ORDER BY INDEX_NAME",
            (table,),
        ).fetchall()
        print(f"  {table}:")
        for row in rows:
            print(f"    - {row['INDEX_NAME']:<30} ({row['cols']})")


def _show_migration_states(conn, filter_prefixes: list[str]) -> None:
    """Reproduce la decisión de arranque para cada migración seleccionada."""
    _print_header("Estado de arranque (_safe_execute_migration)")
    names = [
        name for name in _KNOWN_MIGRATIONS
        if not filter_prefixes or any(name.startswith(p) for p in filter_prefixes)
    ]
    if not names:
        print("  (sin migraciones que coincidan)")
        return

    for name in names:
        try:
            # Sólo lectura: se comparan objetos, no se ejecuta el SQL.
            expected = dbm._get_expected_objects(name)
            existing = dbm._get_existing_objects(conn, expected)
            registered = dbm._is_migration_registered(conn, name)
            count = sum(
                sum(len(cols) for cols in value.values()) if isinstance(value, dict) else len(value)
                for value in existing.values()
            )
            print(
                f"  {name:<45} registrada={str(registered):<5} "
                f"objetos_presentes={count}"
            )
        except Exception as exc:  # pragma: no cover - herramienta de diagnóstico
            print(f"  {name:<45} ERROR: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--migrations",
        nargs="*",
        default=[],
        help="Prefijos de migración a revisar (por defecto: todas las conocidas)",
    )
    args = parser.parse_args()

    settings = Settings.load()
    if not settings.database_url:
        print("CHORUS_DATABASE_URL no está definida.", file=sys.stderr)
        return 1

    conn = dbm.connect(settings)
    try:
        _print_header("Conexión")
        _show_server(conn)
        registered = _show_migrations(conn)
        _show_tables(conn)
        _show_columns(conn)
        _show_indexes(conn)
        _show_migration_states(conn, args.migrations)

        missing = sorted(set(_KNOWN_MIGRATIONS) - set(registered))
        _print_header("Resumen")
        if missing:
            print(f"  Migraciones sin registrar: {', '.join(missing)}")
            print("  El arranque intentará aplicarlas o registrarlas.")
        else:
            print("  Todas las migraciones conocidas están registradas.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
