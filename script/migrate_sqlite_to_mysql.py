"""Migra los datos de Chorus de SQLite a MySQL/MariaDB conservando IDs.

Uso:
  python script/migrate_sqlite_to_mysql.py --sqlite var/chorus.sqlite3 \
      --url mysql+pymysql://user:pass@127.0.0.1:3306/osap_chorus

Es una migración de una sola vez para desarrollo. Hace backup lógico del SQLite
(no lo modifica), crea el esquema MySQL y copia todas las tablas. Si MySQL ya tiene
datos, aborta salvo que se pase --replace.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import pymysql
except ImportError:  # pragma: no cover
    print("Instala pymysql: python -m pip install pymysql", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "migrations" / "mysql" / "001_schema.sql"
SKIP_TABLES = {"chorus_schema_migrations"}


def _target_connection(url: str):
    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    return pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username or "",
        password=parsed.password or "",
        database=(parsed.path or "/").lstrip("/"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _create_schema(target) -> None:
    with target.cursor() as cursor:
        script = "\n".join(
            line for line in SCHEMA.read_text("utf-8").splitlines()
            if not line.strip().startswith("--")
        )
        for statement in script.split(";"):
            if statement.strip():
                cursor.execute(statement)
    target.commit()


def _table_columns(conn, table: str, mysql: bool) -> list[str]:
    if mysql:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
                (table,),
            )
            return [row["COLUMN_NAME"] for row in cursor.fetchall()]
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default="var/chorus.sqlite3")
    parser.add_argument("--url", required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    source = sqlite3.connect(ROOT / args.sqlite)
    source.row_factory = sqlite3.Row
    target = _target_connection(args.url)
    _create_schema(target)

    tables = [
        row[0]
        for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        if row[0] not in SKIP_TABLES
    ]
    with target.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        if args.replace:
            for table in tables:
                cursor.execute(f"DELETE FROM `{table}`")
        else:
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) AS n FROM `{table}`")
                if cursor.fetchone()["n"]:
                    print(f"MySQL ya contiene datos en {table}; usa --replace", file=sys.stderr)
                    return 1
        for table in tables:
            source_cols = _table_columns(source, table, mysql=False)
            target_cols = set(_table_columns(target, table, mysql=True))
            cols = [col for col in source_cols if col in target_cols]
            if not cols:
                continue
            rows = source.execute(f'SELECT {", ".join(chr(34)+c+chr(34) for c in cols)} FROM "{table}"').fetchall()
            if not rows:
                continue
            placeholders = ", ".join(["%s"] * len(cols))
            columns = ", ".join(f"`{col}`" for col in cols)
            cursor.executemany(
                f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders})",
                [tuple(row[col] for col in cols) for row in rows],
            )
            print(f"{table}: {len(rows)} filas")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    target.commit()
    source.close()
    target.close()
    print("Migración completada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

