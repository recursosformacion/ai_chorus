"""Protección de la base de datos de pruebas (app.dbguard).

Se verifica que ninguna operación destructiva pueda ejecutarse si la conexión
efectiva no es osap_chorus_test / osap2027_test / MariaDB 10.4.
"""

from __future__ import annotations

import pytest

from app.dbguard import (
    EXPECTED_DATABASE,
    EXPECTED_USER,
    DatabaseUnavailableError,
    UnsafeTestDatabaseError,
    check_effective_connection,
    guard_from_settings,
    probe_effective_connection,
)


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConnection:
    """Conexión simulada que registra las sentencias ejecutadas."""

    def __init__(self, row, *, fail_on_connect=False):
        self._row = row
        self.executed: list[str] = []
        self.closed = False
        self._fail_on_connect = fail_on_connect

    def execute(self, sql, params=()):
        self.executed.append(sql)
        if self._fail_on_connect:
            raise RuntimeError("connection refused")
        return _FakeCursor(self._row)

    def close(self):
        self.closed = True


VALID_ROW = {
    "db": EXPECTED_DATABASE,
    "usr": f"{EXPECTED_USER}@localhost",
    "ver": "10.4.32-MariaDB",
    "vc": "mariadb.org binary distribution",
}

DESTRUCTIVE_SQL = "DELETE FROM groups"


# --------------------------------------------------------------------------
# Conexión válida
# --------------------------------------------------------------------------
@pytest.mark.unit
def test_valid_connection_is_accepted():
    conn = _FakeConnection(VALID_ROW)
    effective = check_effective_connection(conn)
    assert effective.database == EXPECTED_DATABASE
    assert effective.user == EXPECTED_USER
    assert effective.is_mariadb
    assert effective.is_supported_version
    # El guard es de sólo lectura: no ejecuta sentencias destructivas
    assert all("DELETE" not in sql.upper() for sql in conn.executed)


@pytest.mark.unit
def test_guard_allows_destructive_sql_only_after_validation():
    """Tras validar, el llamador puede ejecutar su DELETE (el guard no lo prohíbe)."""
    conn = _FakeConnection(VALID_ROW)
    check_effective_connection(conn)
    conn.execute(DESTRUCTIVE_SQL)
    assert DESTRUCTIVE_SQL in conn.executed


# --------------------------------------------------------------------------
# Casos inválidos: debe abortar y no ejecutar nada destructivo
# --------------------------------------------------------------------------
@pytest.mark.unit
def test_wrong_database_is_rejected_without_destructive_sql():
    conn = _FakeConnection({**VALID_ROW, "db": "osap_chorus"})
    with pytest.raises(UnsafeTestDatabaseError) as exc:
        check_effective_connection(conn)
    assert "osap_chorus" in str(exc.value)
    # No se ejecutó ninguna sentencia destructiva
    assert all("DELETE" not in sql.upper() for sql in conn.executed)


@pytest.mark.unit
def test_wrong_user_is_rejected_without_destructive_sql():
    conn = _FakeConnection({**VALID_ROW, "usr": "root@localhost"})
    with pytest.raises(UnsafeTestDatabaseError) as exc:
        check_effective_connection(conn)
    assert "root" in str(exc.value)
    assert all("DELETE" not in sql.upper() for sql in conn.executed)


@pytest.mark.unit
def test_incompatible_version_is_rejected():
    for version, comment in (
        ("10.3.39-MariaDB", "mariadb.org binary distribution"),
        ("8.0.36", "MySQL Community Server"),
    ):
        conn = _FakeConnection({**VALID_ROW, "ver": version, "vc": comment})
        with pytest.raises(UnsafeTestDatabaseError):
            check_effective_connection(conn)


@pytest.mark.unit
def test_missing_connection_is_rejected():
    with pytest.raises(DatabaseUnavailableError):
        check_effective_connection(None)


@pytest.mark.unit
def test_unreachable_server_is_reported_as_unavailable():
    conn = _FakeConnection(VALID_ROW, fail_on_connect=True)
    with pytest.raises(DatabaseUnavailableError):
        check_effective_connection(conn)


@pytest.mark.unit
def test_empty_probe_result_is_rejected():
    conn = _FakeConnection(None)
    with pytest.raises(UnsafeTestDatabaseError):
        probe_effective_connection(conn)


@pytest.mark.unit
def test_guard_from_settings_without_url_raises_unavailable():
    class _Settings:
        database_url = None

    with pytest.raises(DatabaseUnavailableError):
        guard_from_settings(_Settings())


@pytest.mark.unit
def test_guard_from_settings_validates_effective_connection_and_closes():
    class _Settings:
        database_url = f"mysql+pymysql://{EXPECTED_USER}:x@127.0.0.1:3306/{EXPECTED_DATABASE}"

    conn = _FakeConnection(VALID_ROW)
    effective = guard_from_settings(_Settings(), opener=lambda settings: conn)
    assert effective.database == EXPECTED_DATABASE
    assert conn.closed, "El guard debe cerrar la conexión que abre"


@pytest.mark.unit
def test_guard_from_settings_rejects_wrong_database():
    class _Settings:
        database_url = "mysql+pymysql://osap2027_test:x@127.0.0.1:3306/otra_cosa"

    # La URL dice una cosa, pero la conexión efectiva manda
    conn = _FakeConnection({**VALID_ROW, "db": "produccion"})
    with pytest.raises(UnsafeTestDatabaseError):
        guard_from_settings(_Settings(), opener=lambda settings: conn)
    assert conn.closed
    assert all("DELETE" not in sql.upper() for sql in conn.executed)


@pytest.mark.unit
def test_settings_url_alone_is_not_trusted():
    """Una URL que apunta a la BD correcta no basta si la conexión no lo es."""
    class _Settings:
        database_url = f"mysql+pymysql://{EXPECTED_USER}:x@127.0.0.1:3306/{EXPECTED_DATABASE}"

    conn = _FakeConnection({**VALID_ROW, "db": "osap_chorus"})
    with pytest.raises(UnsafeTestDatabaseError):
        guard_from_settings(_Settings(), opener=lambda settings: conn)


# --------------------------------------------------------------------------
# El punto de entrada que usan los fixtures de conftest
# --------------------------------------------------------------------------
class _SettingsWithUrl:
    database_url = f"mysql+pymysql://{EXPECTED_USER}:x@127.0.0.1:3306/{EXPECTED_DATABASE}"


@pytest.mark.unit
def test_conftest_guard_rejects_wrong_database_without_deleting(monkeypatch):
    """Los fixtures deben abortar (fail), no omitir, si la BD efectiva no es la suya."""
    from tests import conftest

    conn = _FakeConnection({**VALID_ROW, "db": "otra_base"})
    monkeypatch.setattr(conftest, "db_connect", lambda settings: conn)

    with pytest.raises(UnsafeTestDatabaseError):
        conftest.assert_safe_test_connection(_SettingsWithUrl())

    assert all("DELETE" not in sql.upper() for sql in conn.executed)


@pytest.mark.unit
def test_conftest_guard_rejects_wrong_user_without_deleting(monkeypatch):
    from tests import conftest

    conn = _FakeConnection({**VALID_ROW, "usr": "root@localhost"})
    monkeypatch.setattr(conftest, "db_connect", lambda settings: conn)

    with pytest.raises(UnsafeTestDatabaseError):
        conftest.assert_safe_test_connection(_SettingsWithUrl())

    assert all("DELETE" not in sql.upper() for sql in conn.executed)


@pytest.mark.unit
def test_conftest_guard_rejects_incompatible_version(monkeypatch):
    from tests import conftest

    conn = _FakeConnection({**VALID_ROW, "ver": "10.6.12-MariaDB", "vc": "mariadb.org"})
    monkeypatch.setattr(conftest, "db_connect", lambda settings: conn)

    with pytest.raises(UnsafeTestDatabaseError):
        conftest.assert_safe_test_connection(_SettingsWithUrl())


@pytest.mark.unit
def test_conftest_guard_reports_unavailable_when_connection_fails(monkeypatch):
    """Sin conexión posible se reporta como no disponible (para omitir el test)."""
    from tests import conftest

    def _boom(settings):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(conftest, "db_connect", _boom)

    with pytest.raises(DatabaseUnavailableError):
        conftest.assert_safe_test_connection(_SettingsWithUrl())


@pytest.mark.unit
def test_conftest_guard_reports_unavailable_without_url():
    from tests import conftest

    class _NoUrl:
        database_url = None

    with pytest.raises(DatabaseUnavailableError):
        conftest.assert_safe_test_connection(_NoUrl())


@pytest.mark.unit
def test_conftest_guard_accepts_valid_connection(monkeypatch):
    """La conexión válida se devuelve lista para su uso."""
    from tests import conftest

    conn = _FakeConnection(VALID_ROW)
    monkeypatch.setattr(conftest, "db_connect", lambda settings: conn)

    returned = conftest.assert_safe_test_connection(_SettingsWithUrl())
    assert returned is conn
    assert all("DELETE" not in sql.upper() for sql in conn.executed)