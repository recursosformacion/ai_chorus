"""Fixtures y configuración pytest para Chorus."""
import os
import pytest
from app.config import Settings
from app.db import connect as db_connect


# --- Marcadores obligatorios ---
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: tests sin base de datos (rápidos)")
    config.addinivalue_line("markers", "integration: tests que requieren MariaDB 10.4.32 real (osap_chorus_test)")
    config.addinivalue_line("markers", "migrations: tests de migraciones que requieren MariaDB real")
    config.addinivalue_line("markers", "db: tests que usan MariaDB con transacción aislada (unit_db)")


# --- Verificación de entorno de integración ---
def _verify_integration_db() -> Settings:
    """Valida conexión efectiva a MariaDB osap_chorus_test. Falla si no cumple."""
    settings = Settings.load()  # Misma carga que create_app()

    if not settings.database_url:
        pytest.skip("CHORUS_DATABASE_URL no definido (requerido para MariaDB)")

    conn = db_connect(settings)
    try:
        row = conn.execute(
            "SELECT DATABASE() AS db, CURRENT_USER() AS usr, @@version AS ver"
        ).fetchone()

        if row["db"] != "osap_chorus_test":
            pytest.skip(f"BD efectiva '{row['db']}' != 'osap_chorus_test'")

        user = row["usr"].split("@")[0] if row["usr"] else ""
        if user != "osap2027_test":
            pytest.skip(f"Usuario efectivo '{user}' != 'osap2027_test'")

        if not row["ver"].startswith("10.4."):
            pytest.skip(
                f"MariaDB {row['ver']} no es de la línea 10.4 "
                "(producción usa 10.4.32)"
            )

        return settings
    finally:
        conn.close()


# --- Fixtures selectivas (solo para tests marcados) ---
@pytest.fixture
def integration_settings():
    """Solo para @pytest.mark.integration. Skip si no hay MariaDB válido."""
    return _verify_integration_db()


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


@pytest.fixture(autouse=True)
def _clean_groups_for_integration(request):
    """Limpia la tabla groups antes de cada test de integración/migraciones."""
    # Solo se ejecuta para tests con marcador integration o migrations
    marker = request.node.get_closest_marker("integration") or request.node.get_closest_marker("migrations")
    if marker:
        # Verificar que CHORUS_DATABASE_URL está definido
        if not os.getenv("CHORUS_DATABASE_URL"):
            pytest.skip("CHORUS_DATABASE_URL no definido, saltando limpieza")
        settings = Settings.load()
        with db_connect(settings) as conn:
            # Eliminar en orden inverso por FK
            conn.execute("DELETE FROM group_members")
            conn.execute("DELETE FROM groups")
            conn.commit()


@pytest.fixture(autouse=True)
def _clean_db_for_db_tests(request):
    """Limpia tablas principales antes de cada test @pytest.mark.db."""
    marker = request.node.get_closest_marker("db")
    if marker:
        if not os.getenv("CHORUS_DATABASE_URL"):
            pytest.skip("CHORUS_DATABASE_URL no definido, saltando limpieza")
        settings = Settings.load()
        with db_connect(settings) as conn:
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
            conn.execute("DELETE FROM group_members")
            conn.execute("DELETE FROM groups")
            conn.execute("DELETE FROM group_article_media")
            conn.execute("DELETE FROM group_articles")
            conn.execute("DELETE FROM group_sections")
            conn.execute("DELETE FROM entity_leads")
            conn.commit()


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