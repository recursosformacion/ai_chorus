"""Conexión de Chorus: SQLite para tests, MySQL/MariaDB para desarrollo y producción.

SQLite se conserva para la suite rápida. El servicio real usa `CHORUS_DATABASE_URL`
con `mysql+pymysql://...`. El adaptador traduce el subconjunto de SQL que Chorus
comparte con SQLite; no pretende ser un ORM.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.config import Settings


class _MySQLCursor:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def fetchone(self) -> dict[str, Any] | None:
        return self._cursor.fetchone()

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._cursor.fetchall())

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    @property
    def lastrowid(self) -> int | None:
        return self._cursor.lastrowid


class _MySQLConnection:
    def __init__(self, url: str) -> None:
        import pymysql
        from urllib.parse import urlparse

        parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
        self._connection = pymysql.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 3306,
            user=parsed.username or "",
            password=parsed.password or "",
            database=(parsed.path or "/").lstrip("/"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    @staticmethod
    def _sql(sql: str) -> str:
        text = sql.strip()
        if text.startswith("PRAGMA"):
            return ""
        text = text.replace("INSERT OR IGNORE", "INSERT IGNORE")
        text = text.replace("INSERT OR REPLACE", "REPLACE INTO")
        text = text.replace("BEGIN IMMEDIATE", "START TRANSACTION")
        return text.replace("?", "%s")

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> _MySQLCursor:
        translated = self._sql(sql)
        cursor = self._connection.cursor()
        if translated:
            cursor.execute(translated, params)
        return _MySQLCursor(cursor)

    def executescript(self, script: str) -> None:
        cleaned = "\n".join(
            line for line in script.splitlines() if not line.strip().startswith("--")
        )
        for statement in cleaned.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> _MySQLConnection:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


def connect(settings: Settings):
    if settings.database_url:
        return _MySQLConnection(settings.database_url)
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

