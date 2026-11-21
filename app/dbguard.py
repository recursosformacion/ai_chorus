"""Protección centralizada de la base de datos de pruebas de Chorus.

Cualquier operación destructiva (DELETE masivo en fixtures, DROP en la
reconstrucción, ejecución de migraciones) debe pasar por este módulo y
comprobar la **conexión efectiva**, nunca el texto de `CHORUS_DATABASE_URL`.

Reglas:
  - Base de datos efectiva: ``osap_chorus_test``.
  - Usuario efectivo: ``osap2027_test``.
  - Servidor MariaDB de la línea 10.4 (la de producción es 10.4.32).

Si la conexión es válida pero apunta a otro destino se lanza
``UnsafeTestDatabaseError``: el llamador debe abortar sin ejecutar sentencias
destructivas. Si no hay MariaDB utilizable se lanza
``DatabaseUnavailableError``, que permite omitir los tests que lo requieran.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EXPECTED_DATABASE = "osap_chorus_test"
EXPECTED_USER = "osap2027_test"
EXPECTED_VERSION_PREFIX = "10.4."

_PROBE_SQL = (
    "SELECT DATABASE() AS db, CURRENT_USER() AS usr, @@version AS ver, @@version_comment AS vc"
)


class DatabaseUnavailableError(RuntimeError):
    """No hay MariaDB de pruebas utilizable (falta URL o no hay conexión)."""


class UnsafeTestDatabaseError(RuntimeError):
    """La conexión efectiva no es la base de pruebas autorizada."""


@dataclass(frozen=True)
class EffectiveConnection:
    """Identidad real de una conexión, tal como la ve el servidor."""

    database: str | None
    user: str
    version: str
    version_comment: str = ""

    @property
    def is_mariadb(self) -> bool:
        return "mariadb" in f"{self.version} {self.version_comment}".lower()

    @property
    def is_supported_version(self) -> bool:
        return self.is_mariadb and self.version.startswith(EXPECTED_VERSION_PREFIX)

    def describe(self) -> str:
        return (
            f"base={self.database!r} usuario={self.user!r} "
            f"version={self.version!r} comment={self.version_comment!r}"
        )


def _row_get(row: Any, key: str) -> Any:
    """Lee una columna de una fila dict-like o secuencial."""
    if row is None:
        return None
    try:
        return row[key]
    except (TypeError, KeyError, IndexError):
        pass
    if isinstance(row, (tuple, list)) and row:
        return row[0]
    return None


def probe_effective_connection(conn: Any) -> EffectiveConnection:
    """Consulta al servidor la identidad efectiva de la conexión."""
    row = conn.execute(_PROBE_SQL).fetchone()
    if row is None:
        raise UnsafeTestDatabaseError(
            "El servidor no devolvió información de la conexión efectiva"
        )
    user_raw = _row_get(row, "usr") or ""
    return EffectiveConnection(
        database=_row_get(row, "db"),
        user=str(user_raw).split("@")[0],
        version=str(_row_get(row, "ver") or ""),
        version_comment=str(_row_get(row, "vc") or ""),
    )


def check_effective_connection(conn: Any) -> EffectiveConnection:
    """Valida que la conexión efectiva sea la base de pruebas autorizada.

    Lanza ``UnsafeTestDatabaseError`` si no coincide base, usuario o versión.
    """
    if conn is None:
        raise DatabaseUnavailableError("No hay conexión de base de datos")

    try:
        effective = probe_effective_connection(conn)
    except UnsafeTestDatabaseError:
        raise
    except Exception as exc:  # error de driver/conexión
        raise DatabaseUnavailableError(
            f"No se pudo consultar la conexión efectiva: {exc}"
        ) from exc

    problems: list[str] = []
    if effective.database != EXPECTED_DATABASE:
        problems.append(
            f"base de datos efectiva {effective.database!r} != {EXPECTED_DATABASE!r}"
        )
    if effective.user != EXPECTED_USER:
        problems.append(
            f"usuario efectivo {effective.user!r} != {EXPECTED_USER!r}"
        )
    if not effective.is_mariadb:
        problems.append(f"el servidor no es MariaDB ({effective.describe()})")
    elif not effective.version.startswith(EXPECTED_VERSION_PREFIX):
        problems.append(
            f"MariaDB {effective.version!r} fuera de la línea {EXPECTED_VERSION_PREFIX}"
        )

    if problems:
        raise UnsafeTestDatabaseError(
            "Operación destructiva bloqueada: " + "; ".join(problems)
        )
    return effective


# Alias explícito para los puntos de llamada destructivos.
assert_safe_test_database = check_effective_connection


def guard_from_settings(settings: Any, opener: Any = None) -> EffectiveConnection:
    """Abre una conexión con ``settings``, la valida y la cierra.

    ``opener`` permite inyectar un creador de conexiones (para tests). Por
    defecto usa ``app.db.connect``.
    """
    database_url = getattr(settings, "database_url", None)
    if not database_url:
        raise DatabaseUnavailableError(
            "CHORUS_DATABASE_URL no definido (requerido para MariaDB)"
        )

    if opener is None:
        from app.db import connect as opener  # import diferido

    try:
        conn = opener(settings)
    except Exception as exc:
        raise DatabaseUnavailableError(
            f"No se pudo conectar a MariaDB: {exc}"
        ) from exc

    try:
        return check_effective_connection(conn)
    finally:
        close = getattr(conn, "close", None)
        if callable(close):
            close()