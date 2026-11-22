"""Fixtures y configuración pytest para Chorus."""
import os
import pytest
from app.config import Settings
from app.db import connect as db_connect
from app.dbguard import (
    DatabaseUnavailableError,
    UnsafeTestDatabaseError,
    check_effective_connection,
)


# --- Marcadores obligatorios ---
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: tests sin base de datos (rápidos)")
    config.addinivalue_line("markers", "integration: tests que requieren MariaDB 10.4.32 real (osap_chorus_test)")
    config.addinivalue_line("markers", "migrations: tests de migraciones que requieren MariaDB real")
    config.addinivalue_line("markers", "db: tests que usan MariaDB con transacción aislada (unit_db)")


# --- Protección de la base de pruebas ---
def assert_safe_test_connection(settings: Settings):
    """Punto único de comprobación antes de cualquier limpieza destructiva.

    Devuelve una conexión validada. Nunca abre la BD de producción: si la
    conexión efectiva no es osap_chorus_test/osap2027_test/MariaDB 10.4 se
    aborta con error (no se ejecuta ningún DELETE).
    """
    if not settings.database_url:
        raise DatabaseUnavailableError(
            "CHORUS_DATABASE_URL no definido (requerido para MariaDB)"
        )
    try:
        conn = db_connect(settings)
    except Exception as exc:
        # No se puede conectar: se reporta como MariaDB no disponible para que
        # el test se omita, en lugar de ejecutar limpiezas a ciegas.
        raise DatabaseUnavailableError(f"No se pudo conectar a MariaDB: {exc}") from exc
    # Valida la conexión REAL contra el servidor antes de devolverla. Si no es
    # la BD de pruebas autorizada se cierra y se aborta sin ejecutar nada.
    try:
        check_effective_connection(conn)
    except BaseException:
        close = getattr(conn, "close", None)
        if callable(close):
            close()
        raise
    return conn


# --- Verificación de entorno de integración ---
def _verify_integration_db() -> Settings:
    """Valida conexión efectiva a MariaDB osap_chorus_test.

    - Sin MariaDB utilizable -> skip (la suite debe poder correr sin BD).
    - Conectado a otro destino -> fallo: es una configuración peligrosa.
    """
    settings = Settings.load()  # Misma carga que create_app()

    if not settings.database_url:
        pytest.skip("CHORUS_DATABASE_URL no definido (requerido para MariaDB)")

    try:
        conn = db_connect(settings)
    except Exception as exc:
        pytest.skip(f"MariaDB no disponible: {exc}")
        return settings  # pragma: no cover (pytest.skip lanza)

    try:
        check_effective_connection(conn)
    except UnsafeTestDatabaseError as exc:
        # Conecta, pero no es la BD de pruebas autorizada: detener el test.
        pytest.fail(str(exc))
    except DatabaseUnavailableError as exc:
        pytest.skip(str(exc))
    finally:
        conn.close()

    return settings


# --- Fixtures selectivas (solo para tests marcados) ---
@pytest.fixture
def integration_settings():
    """Solo para @pytest.mark.integration. Skip si no hay MariaDB válido."""
    return _verify_integration_db()


class _PermissiveIdentity:
    """Doble por defecto del proveedor de identidad para la suite.

    Los tests que no tratan la identidad sólo necesitan que los listados
    resuelvan nombres; se resuelve cualquier identificador con un nombre
    determinista. Los tests de identidad instalan su propio doble mediante
    ``install_identity`` (que se aplica después y por tanto prevalece).
    """

    def __init__(self):
        self.calls: list[list[str]] = []

    def lookup(self, user_ids):
        from app.identity import PublicIdentity, canonical_uuid

        ids = list(user_ids)
        self.calls.append(ids)
        resolved = {}
        for uid in dict.fromkeys(ids):
            if not uid:
                continue
            try:
                canonical = canonical_uuid(uid)
            except (ValueError, AttributeError, TypeError):
                continue
            resolved[canonical] = PublicIdentity(
                user_id=canonical, name=f"Usuario {canonical[:8]}"
            )
        return resolved

    def resolve_public_names(self, user_ids):
        return {
            uid: identity.name
            for uid, identity in self.lookup(user_ids).items()
            if identity.name
        }

    def resolve_identity(self, user_id: str):
        from app.identity import PublicIdentity, canonical_uuid

        self.calls.append([user_id])
        if not user_id:
            return None
        try:
            canonical = canonical_uuid(user_id)
        except (ValueError, AttributeError, TypeError):
            return None
        return PublicIdentity(user_id=canonical, name=f"Usuario {canonical[:8]}")

    def resolve_one(self, user_id: str):
        identity = self.resolve_identity(user_id)
        return identity.name if identity is not None else None


@pytest.fixture(autouse=True)
def _default_identity_stub(monkeypatch):
    """Doble de identidad por defecto: evita que la suite dependa de M2M real.

    No sustituye a las pruebas del contrato M2M, que instalan su propio doble.
    """
    import app.main as main_module

    monkeypatch.setattr(main_module, "IdentityClient", lambda *a, **k: _PermissiveIdentity())


@pytest.fixture
def unit_db(integration_settings):
    """MariaDB aislado para tests rápidos: transacción + rollback automático.
    Se salta automáticamente si no hay MariaDB configurado.
    """
    conn = db_connect(integration_settings)
    conn.execute("START TRANSACTION")
    try:
        yield conn
    finally:
        conn.execute("ROLLBACK")
        conn.close()


def _purge_integration_tables(conn) -> None:
    """Vacía las tablas que la suite puede haber tocado, en orden de dependencia.

    La protección de BD se hace antes de llamar aquí
    (``assert_safe_test_connection``).
    """
    conn.execute("DELETE FROM preparation_work_items")
    conn.execute("DELETE FROM preparation_work_files")
    conn.execute("DELETE FROM preparation_works")
    conn.execute("DELETE FROM spaces")
    conn.execute("DELETE FROM group_members")
    # group_sections no tiene FK a groups: hay que borrarla explícitamente o
    # sus filas sobreviven a la eliminación del grupo.
    conn.execute("DELETE FROM group_sections")
    conn.execute("DELETE FROM groups")
    # Registro de auditoría: las operaciones de los tests generan filas
    conn.execute("DELETE FROM activity_log")
    # Cadenas Work -> Resource -> File (works.required_resource_id es
    # circular, por eso se desactivan temporalmente las FKs)
    conn.execute("SET FOREIGN_KEY_CHECKS = 0")
    conn.execute("DELETE FROM library_items")
    conn.execute("DELETE FROM files")
    conn.execute("DELETE FROM resources")
    conn.execute("DELETE FROM works")
    conn.execute("SET FOREIGN_KEY_CHECKS = 1")


def _purge_tables_safely(settings) -> None:
    """Ejecuta la purga final sobre la BD de pruebas.

    Garantías:

    - Sin MariaDB utilizable (``DatabaseUnavailableError`` /
      ``UnsafeTestDatabaseError``): no hay BD que limpiar, se retorna sin más.
      La protección ``dbguard`` no se altera.
    - Si la purga falla: se intenta ``ROLLBACK``, se **cierra siempre** la
      conexión y se lanza ``pytest.fail`` con el error original. El fallo es
      visible en el informe de sesión en lugar de quedar silenciado.
    """
    try:
        conn = assert_safe_test_connection(settings)
    except (DatabaseUnavailableError, UnsafeTestDatabaseError):
        return

    error: Exception | None = None
    try:
        _purge_integration_tables(conn)
        conn.commit()
    except Exception as exc:
        error = exc
        try:
            conn.rollback()
        except Exception:
            # El fallo original es el que se reporta; el rollback es best-effort.
            pass
    finally:
        conn.close()

    if error is not None:
        pytest.fail(
            "La purga final de la BD de pruebas no pudo completarse: "
            f"{type(error).__name__}: {error}",
            pytrace=False,
        )


@pytest.fixture(scope="session", autouse=True)
def _purge_tables_at_session_end():
    """Limpieza final: la BD de pruebas no queda con residuos de la sesión.

    Si la purga no puede completarse, la sesión termina con un error visible.
    """
    yield
    if not os.getenv("CHORUS_DATABASE_URL"):
        # Sin MariaDB de pruebas no hay residuos que limpiar.
        return
    _purge_tables_safely(Settings.load())


@pytest.fixture(autouse=True)
def _clean_groups_for_integration(request):
    """Limpia tablas de grupos/espacios antes de tests de integración/migraciones.

    La protección de BD es autónoma: este fixture no depende de que
    ``integration_settings`` se haya ejecutado antes.
    """
    marker = request.node.get_closest_marker("integration") or request.node.get_closest_marker("migrations")
    if not marker:
        return

    settings = Settings.load()
    try:
        conn = assert_safe_test_connection(settings)
    except DatabaseUnavailableError as exc:
        pytest.skip(f"BD de pruebas no disponible: {exc}")
    except UnsafeTestDatabaseError as exc:
        pytest.fail(str(exc))

    try:
        _purge_integration_tables(conn)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _clean_db_for_db_tests(request):
    """Limpia tablas principales antes de cada test @pytest.mark.db.

    Misma protección autónoma de BD que el fixture anterior.
    """
    marker = request.node.get_closest_marker("db")
    if not marker:
        return

    settings = Settings.load()
    try:
        conn = assert_safe_test_connection(settings)
    except DatabaseUnavailableError as exc:
        pytest.skip(f"BD de pruebas no disponible: {exc}")
    except UnsafeTestDatabaseError as exc:
        pytest.fail(str(exc))

    try:
        # Eliminar en orden inverso por FK
        conn.execute("DELETE FROM editor_source_tokens")
        conn.execute("DELETE FROM creation_drafts")
        conn.execute("DELETE FROM collection_items")
        conn.execute("DELETE FROM collections")
        conn.execute("DELETE FROM library_items")
        conn.execute("DELETE FROM files")
        conn.execute("DELETE FROM resources")
        conn.execute("DELETE FROM works")
        conn.execute("DELETE FROM oidc_states")
        conn.execute("DELETE FROM message_recipients")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM event_targets")
        conn.execute("DELETE FROM event_rsvps")
        conn.execute("DELETE FROM event_groups")
        conn.execute("DELETE FROM events")
        # preparation_works/spaces cuelgan de groups: limpiarlos antes
        conn.execute("DELETE FROM preparation_work_files")
        conn.execute("DELETE FROM preparation_work_items")
        conn.execute("DELETE FROM preparation_works")
        conn.execute("DELETE FROM spaces")
        conn.execute("DELETE FROM group_members")
        # group_sections no tiene FK a groups: borrado explícito
        conn.execute("DELETE FROM group_sections")
        conn.execute("DELETE FROM groups")
        # Registro de auditoría: las operaciones de los tests generan filas
        conn.execute("DELETE FROM activity_log")
        conn.execute("DELETE FROM group_article_media")
        conn.execute("DELETE FROM group_articles")
        conn.execute("DELETE FROM group_sections")
        conn.execute("DELETE FROM entity_leads")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def migration_settings(integration_settings):
    """Solo para @pytest.mark.migrations."""
    return integration_settings


# --- Detectar tests sin marcador en suite de integración ---
def pytest_collection_modifyitems(config, items):
    """Tests con marcador integration/migrations SIN fixture correspondiente → error.
    Solo aplica si MariaDB está configurado (CHORUS_DATABASE_URL definido).
    """
    if not os.getenv("CHORUS_DATABASE_URL"):
        return  # Sin BD configurada, no validamos fixtures

    for item in items:
        has_integration = item.get_closest_marker("integration") is not None
        has_migrations = item.get_closest_marker("migrations") is not None
        if has_integration or has_migrations:
            # Verificar que usa fixture integration_settings o migration_settings
            if "integration_settings" not in item.fixturenames and "migration_settings" not in item.fixturenames:
                pytest.fail(
                    f"Test {item.nodeid} marcado integration/migrations pero no usa fixture "
                    "integration_settings/migration_settings. Añade el parámetro al test."
                )


# --- Por defecto: TODOS los tests ---
# Se configura en pyproject.toml: addopts = "-ra"