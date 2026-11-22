"""La purga final de la BD de pruebas debe fallar de forma visible.

Antes, ``_purge_tables_at_session_end`` hacía ``except Exception: pass``: si la
limpieza fallaba, pytest terminaba sin advertirlo.
"""
from __future__ import annotations

import pytest
from _pytest.outcomes import Failed

from tests import conftest


class _FakeConnection:
    """Conexión simulada que registra el ciclo de vida y puede fallar."""

    def __init__(self, *, fail_on=None):
        self.executed: list[str] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self._fail_on = fail_on

    def execute(self, sql, params=()):
        self.executed.append(sql)
        if self._fail_on and self._fail_on in sql:
            raise RuntimeError(f"fallo simulado en: {self._fail_on}")
        return self

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.mark.unit
def test_purge_succeeds_and_closes_connection(monkeypatch):
    conn = _FakeConnection()
    monkeypatch.setattr(conftest, "assert_safe_test_connection", lambda settings: conn)

    conftest._purge_tables_safely(object())

    assert conn.committed, "La purga correcta debe hacer commit"
    assert conn.closed, "La conexión debe cerrarse siempre"
    assert conn.executed[0] == "DELETE FROM preparation_work_items"


@pytest.mark.unit
def test_purge_failure_is_visible_and_closes_connection(monkeypatch):
    """Un fallo en la purga debe lanzar pytest.fail y cerrar la conexión."""
    conn = _FakeConnection(fail_on="DELETE FROM groups")
    monkeypatch.setattr(conftest, "assert_safe_test_connection", lambda settings: conn)

    with pytest.raises(Failed) as exc:
        conftest._purge_tables_safely(object())

    message = str(exc.value)
    assert "purga final" in message.lower()
    assert "fallo simulado" in message, "El error original debe ser visible"
    assert conn.closed, "La conexión debe cerrarse aunque la purga falle"
    assert conn.rolled_back, "Debe intentarse el rollback"


@pytest.mark.unit
def test_purge_failure_on_commit_is_visible(monkeypatch):
    """Si falla el commit, también se reporta y se cierra la conexión."""
    conn = _FakeConnection()

    def _boom():
        raise RuntimeError("fallo en commit")

    conn.commit = _boom
    monkeypatch.setattr(conftest, "assert_safe_test_connection", lambda settings: conn)

    with pytest.raises(Failed) as exc:
        conftest._purge_tables_safely(object())

    assert "fallo en commit" in str(exc.value)
    assert conn.closed


@pytest.mark.unit
def test_purge_skips_when_no_test_database(monkeypatch):
    """Sin MariaDB utilizable no hay residuos: no se falla."""
    conn = _FakeConnection()

    def _raise(settings):
        raise conftest.DatabaseUnavailableError("sin MariaDB")

    monkeypatch.setattr(conftest, "assert_safe_test_connection", _raise)

    # No debe lanzar
    conftest._purge_tables_safely(object())
    assert conn.executed == []


@pytest.mark.unit
def test_purge_skips_when_connection_is_unsafe(monkeypatch):
    """Si el destino no es la BD de pruebas autorizada, no se purga ni se falla."""
    conn = _FakeConnection()

    def _raise(settings):
        raise conftest.UnsafeTestDatabaseError("destino no autorizado")

    monkeypatch.setattr(conftest, "assert_safe_test_connection", _raise)

    conftest._purge_tables_safely(object())
    assert conn.executed == []


@pytest.mark.unit
def test_purge_covers_all_expected_tables(monkeypatch):
    """La purga vacía las tablas en orden de dependencia."""
    conn = _FakeConnection()
    monkeypatch.setattr(conftest, "assert_safe_test_connection", lambda settings: conn)

    conftest._purge_tables_safely(object())

    deletes = [sql for sql in conn.executed if sql.startswith("DELETE")]
    expected = [
        "DELETE FROM preparation_work_items",
        "DELETE FROM preparation_work_files",
        "DELETE FROM preparation_works",
        "DELETE FROM spaces",
        "DELETE FROM group_members",
        "DELETE FROM group_sections",
        "DELETE FROM groups",
        "DELETE FROM activity_log",
        "DELETE FROM library_items",
        "DELETE FROM files",
        "DELETE FROM resources",
        "DELETE FROM works",
    ]
    assert deletes == expected

    # Las FKs se desactivan antes de las tablas dependientes y se reactivan al final
    assert "SET FOREIGN_KEY_CHECKS = 0" in conn.executed
    assert "SET FOREIGN_KEY_CHECKS = 1" in conn.executed
    assert conn.executed.index("SET FOREIGN_KEY_CHECKS = 0") < conn.executed.index(
        "DELETE FROM library_items"
    )
    assert conn.executed[-1] == "SET FOREIGN_KEY_CHECKS = 1"