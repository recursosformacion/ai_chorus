"""Fixtures y configuración pytest para Chorus."""
import os
import pytest
from app.config import Settings
from app.db import connect as db_connect


# --- Marcadores obligatorios ---
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: tests sin base de datos (default)")
    config.addinivalue_line("markers", "integration: tests que requieren MariaDB real (osap_chorus_test)")
    config.addinivalue_line("markers", "migrations: tests de migraciones que requieren MariaDB real")


# --- Verificación de entorno de integración ---
def _verify_integration_db() -> Settings:
    """Valida conexión efectiva a MariaDB osap_chorus_test. Falla si no cumple."""
    settings = Settings.load()  # Misma carga que create_app()

    if not settings.database_url:
        raise RuntimeError("BLOQUEO: CHORUS_DATABASE_URL no definido (requerido para MariaDB)")

    conn = db_connect(settings)
    try:
        row = conn.execute(
            "SELECT DATABASE() AS db, CURRENT_USER() AS usr, @@version AS ver"
        ).fetchone()

        if row["db"] != "osap_chorus_test":
            raise RuntimeError(f"BLOQUEO: BD efectiva '{row['db']}' != 'osap_chorus_test'")

        user = row["usr"].split("@")[0] if row["usr"] else ""
        if user != "osap2027_test":
            raise RuntimeError(f"BLOQUEO: Usuario efectivo '{user}' != 'osap2027_test'")

        if not row["ver"].startswith("10.4."):
            raise RuntimeError(
                f"BLOQUEO: MariaDB {row['ver']} no es de la línea 10.4 "
                "(producción usa 10.4.32)"
            )

        return settings
    finally:
        conn.close()


# --- Fixtures selectivas (solo para tests marcados) ---
@pytest.fixture
def integration_settings():
    """Solo para @pytest.mark.integration. Falla ANTES de cualquier test."""
    return _verify_integration_db()


@pytest.fixture
def migration_settings(integration_settings):
    """Solo para @pytest.mark.migrations."""
    return integration_settings


# --- Detectar tests sin marcador en suite de integración ---
def pytest_collection_modifyitems(config, items):
    """Tests con marcador integration/migrations SIN fixture correspondiente → error."""
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


# --- Por defecto: SOLO unit ---
# Se configura en pyproject.toml: addopts = "-m unit"