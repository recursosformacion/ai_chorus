"""Conexión de Chorus: MySQL/MariaDB para desarrollo, tests y producción.

El servicio real usa `CHORUS_DATABASE_URL` con `mysql+pymysql://...`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import sqlparse

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
        # ON CONFLICT (...) DO UPDATE -> ON DUPLICATE KEY UPDATE (MariaDB/MySQL)
        import re
        text = re.sub(
            r"ON CONFLICT\s*\([^)]+\)\s+DO UPDATE SET",
            "ON DUPLICATE KEY UPDATE",
            text,
            flags=re.IGNORECASE
        )
        return text.replace("?", "%s")

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> _MySQLCursor:
        translated = self._sql(sql)
        cursor = self._connection.cursor()
        if translated:
            cursor.execute(translated, params)
        return _MySQLCursor(cursor)

    def executescript(self, script: str) -> None:
        _execute_sql_script(self, script, is_mysql=True)

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


def _execute_sql_script(conn: Any, script: str, is_mysql: bool) -> None:
    """
    Ejecuta un script SQL dividiendo correctamente las sentencias.
    Usa sqlparse para tokenizar respetando strings, comentarios y bloques.
    """
    # sqlparse.split respeta ; dentro de strings/comentarios
    statements = sqlparse.split(script)

    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        # Eliminar TODOS los comentarios (-- y /* */)
        stmt_clean = sqlparse.format(stmt, strip_comments=True).strip()
        if not stmt_clean:
            continue

        # Traducción MySQL si aplica
        if is_mysql:
            stmt_clean = _translate_mysql(stmt_clean)

        if stmt_clean:
            conn.execute(stmt_clean)


def _translate_mysql(sql: str) -> str:
    """Traduce SQL genérico a MySQL/MariaDB."""
    text = sql.strip()
    if text.startswith("PRAGMA"):
        return ""
    text = text.replace("INSERT OR IGNORE", "INSERT IGNORE")
    text = text.replace("INSERT OR REPLACE", "REPLACE INTO")
    text = text.replace("BEGIN IMMEDIATE", "START TRANSACTION")
    return text.replace("?", "%s")


def _get_table_names(conn: Any) -> list[str]:
    """Obtiene lista de nombres de tablas en la base de datos actual."""
    rows = conn.execute("SHOW TABLES").fetchall()
    # SHOW TABLES devuelve dict con clave 'Tables_in_<dbname>'
    for row in rows:
        for key, val in row.items():
            if key.startswith("Tables_in_"):
                yield val
                break


def _get_column_names(conn: Any, table: str) -> set[str]:
    """Obtiene conjunto de nombres de columnas de una tabla."""
    rows = conn.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?",
        (table,)
    ).fetchall()
    return {row["COLUMN_NAME"] for row in rows}


def _get_column_type(conn: Any, table: str, column: str) -> str | None:
    """Obtiene el tipo de una columna."""
    row = conn.execute(
        "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?",
        (table, column)
    ).fetchone()
    return row["COLUMN_TYPE"] if row else None


def _table_exists(conn: Any, table: str) -> bool:
    """Verifica si una tabla existe."""
    tables = set(_get_table_names(conn))
    return table in tables


def _index_exists(conn: Any, table: str, index_name: str) -> bool:
    """Verifica si un índice existe en una tabla."""
    row = conn.execute(
        "SELECT 1 FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND INDEX_NAME = ?",
        (table, index_name)
    ).fetchone()
    return row is not None


def _count_foreign_keys(conn: Any) -> int:
    """Cuenta claves foráneas en tablas de la aplicación."""
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = DATABASE() "
        "AND CONSTRAINT_TYPE = 'FOREIGN KEY' "
        "AND TABLE_NAME IN ('works','resources','files','creation_drafts',"
        "'editor_source_tokens','library_items','collections','collection_items',"
        "'oidc_states','groups','group_members','events','event_groups',"
        "'event_rsvps','entity_leads','messages','event_targets','message_recipients',"
        "'group_sections','group_articles','group_article_media')"
    ).fetchone()
    return int(row["cnt"]) if row else 0


def _verify_legacy_baseline(conn: Any, settings: Settings) -> tuple[bool, list[str]]:
    """
    Valida SOLO el esquema histórico de 001_schema.sql.
    Returns (ok, errors). Does NOT modify database.
    NO valida objetos que añaden migraciones 004-007.
    """
    errors = []

    # 1. Tablas base (18 aplicación + chorus_schema_migrations)
    expected_tables = {
        'works', 'resources', 'files', 'creation_drafts', 'editor_source_tokens',
        'library_items', 'collections', 'collection_items', 'oidc_states',
        'groups', 'group_members', 'events', 'event_groups', 'event_rsvps',
        'entity_leads', 'messages', 'event_targets', 'message_recipients',
        'chorus_schema_migrations'
    }
    existing = set(_get_table_names(conn))
    missing = expected_tables - existing
    if missing:
        errors.append(f"Tablas base faltantes: {sorted(missing)}")

    # 2. Columnas críticas DEL BASELINE (solo las que están en 001_schema.sql)
    baseline_critical_columns = {
        'groups': {'slug', 'kind', 'description', 'status', 'editorial_mode', 'technical_description'},
        'group_members': {'admin_role_id', 'musical_role_id', 'section_id', 'display_name'},
        'events': {'recurrence', 'recurrence_until', 'series_id', 'creator_badge'},
        # resources y files: NINGUNA columna material/grupos en baseline
    }
    for table, cols in baseline_critical_columns.items():
        existing_cols = _get_column_names(conn, table)
        missing_cols = cols - existing_cols
        if missing_cols:
            errors.append(f"{table}: columnas baseline faltantes {sorted(missing_cols)}")

    # 3. FKs históricas (14 esperadas en 001_schema.sql)
    fk_count = _count_foreign_keys(conn)
    if fk_count < 14:
        errors.append(f"FKs históricas: {fk_count}/14")

    # 4. Tablas artículos (pueden venir de 003 histórica — NO son obligatorias en baseline)
    article_tables = {'group_sections', 'group_articles', 'group_article_media'}
    existing_article = article_tables & existing
    if existing_article and existing_article != article_tables:
        errors.append(f"Tablas artículos parciales: {sorted(existing_article)} (esperadas las 3 o ninguna)")

    # 5. Índice idx_events_series (puede venir de 002 histórica — NO obligatorio en baseline)
    # Solo informativo, no error de baseline

    return len(errors) == 0, errors


def _verify_final_schema(conn: Any) -> tuple[bool, list[str]]:
    """
    Valida esquema COMPLETO tras aplicar migraciones 004-007.
    Se usa en rebuild_test_db.py y tests de migraciones.
    """
    errors = []

    # Todas las tablas finales
    required_tables = {
        'works', 'resources', 'files', 'creation_drafts', 'editor_source_tokens',
        'library_items', 'collections', 'collection_items', 'oidc_states',
        'groups', 'group_members', 'events', 'event_groups', 'event_rsvps',
        'entity_leads', 'messages', 'event_targets', 'message_recipients',
        'group_sections', 'group_articles', 'group_article_media',
        'chorus_schema_migrations'
    }
    existing = set(_get_table_names(conn))
    missing = required_tables - existing
    if missing:
        errors.append(f"Tablas finales faltantes: {sorted(missing)}")

    # Columnas materiales (004, 005)
    material_columns = {
        'resources': {'version_label', 'part_label', 'material_status', 'group_id', 'group_section_id'},
        'files': {'folder_path', 'display_name', 'original_name'},
    }
    for table, cols in material_columns.items():
        existing_cols = _get_column_names(conn, table)
        missing_cols = cols - existing_cols
        if missing_cols:
            errors.append(f"{table}: columnas material faltantes {sorted(missing_cols)}")

    # Índice events series (007)
    if not _index_exists(conn, 'events', 'idx_events_series'):
        errors.append("Índice idx_events_series faltante en events")

    # FKs finales (14 históricas + FKs de group_articles, group_article_media)
    fk_count = _count_foreign_keys(conn)
    if fk_count < 16:  # 14 base + 2 FKs nuevas (group_articles→groups, group_article_media→group_articles)
        errors.append(f"FKs finales: {fk_count}/16+")

    return len(errors) == 0, errors


def _analyze_003_state(conn: Any) -> str:
    """
    Retorna estado de 003_group_articles.sql:
    - COMPLETED_OK: registrada + 3 tablas presentes
    - REGISTERED_TABLES_MISSING: registrada + tablas faltantes → ABORTAR
    - PARTIAL_TABLES: registrada + tablas parciales → ABORTAR
    - TABLES_EXIST_UNREGISTERED: no registrada + 3 tablas presentes
    - NORMAL: no registrada + tablas ausentes
    - PARTIAL_TABLES_UNREGISTERED: no registrada + tablas parciales → ABORTAR
    """
    registered = _is_migration_registered(conn, "003_group_articles.sql")
    tables_exist = {t for t in ['group_sections', 'group_articles', 'group_article_media']
                    if _table_exists(conn, t)}

    if registered:
        if tables_exist == {'group_sections', 'group_articles', 'group_article_media'}:
            return "COMPLETED_OK"  # Saltar 006
        elif len(tables_exist) == 0:
            return "REGISTERED_TABLES_MISSING"  # ABORTAR
        else:
            return "PARTIAL_TABLES"  # ABORTAR
    else:
        if tables_exist == {'group_sections', 'group_articles', 'group_article_media'}:
            return "TABLES_EXIST_UNREGISTERED"  # Saltar 006
        elif len(tables_exist) == 0:
            return "NORMAL"  # Ejecutar 006
        else:
            return "PARTIAL_TABLES_UNREGISTERED"  # ABORTAR


def _is_migration_registered(conn: Any, name: str) -> bool:
    """Verifica si una migración está registrada."""
    row = conn.execute(
        "SELECT 1 FROM chorus_schema_migrations WHERE name = ?", (name,)
    ).fetchone()
    return row is not None


# Tablas donde puede vivir cada índice gestionado por 004-007.
_INDEX_PARENT_TABLES = ("resources", "events", "group_articles", "group_article_media")

# Sentencias de recreación de índices secundarios (idempotentes a nivel lógico).
_INDEX_STATEMENTS = {
    "idx_resources_material":
        "CREATE INDEX idx_resources_material ON resources (work_id, material_status)",
    "idx_resources_group_status":
        "CREATE INDEX idx_resources_group_status ON resources (group_id, material_status)",
    "idx_events_series":
        "CREATE INDEX idx_events_series ON events (series_id, starts_at)",
}

# Columnas que 004_material_library.sql comparte con 001_schema.sql.
# Se define, además, su valor por defecto en el baseline.
_BASELINE_COLUMN_DEFAULTS = {
    ("resources", "material_status"): "'draft'",
}

# Columnas que 004 añade y que el baseline NO define: si ya existen, el
# esquema lo creó otra vía y no se puede reejecutar el ALTER a ciegas.
_MIGRATION_ONLY_COLUMNS = {
    "004_material_library.sql": {
        ("resources", "version_label"),
        ("resources", "part_label"),
        ("files", "folder_path"),
        ("files", "display_name"),
        ("files", "original_name"),
    },
}


def _get_expected_objects(mig_name: str) -> dict[str, set[str]]:
    """Devuelve objetos esperados por migración."""
    objects = {
        "004_material_library.sql": {
            "resources": {"version_label", "part_label", "material_status"},
            "files": {"folder_path", "display_name", "original_name"},
            "indexes": {"idx_resources_material"},
        },
        "005_material_groups.sql": {
            "resources": {"group_id", "group_section_id"},
            "indexes": {"idx_resources_group_status"},
        },
        "006_group_articles_tables.sql": {
            "tables": {"group_sections", "group_articles", "group_article_media"},
            "indexes": {"idx_group_articles_group", "idx_group_articles_status", "idx_group_article_media_article"},
        },
        "007_events_series_index.sql": {
            "indexes": {"idx_events_series"},
        },
    }
    return objects.get(mig_name, {})


def _get_existing_objects(conn: Any, expected: dict[str, set[str]]) -> dict[str, set[str]]:
    """Obtiene objetos existentes que coinciden con los esperados."""
    existing = {}
    for obj_type, names in expected.items():
        if obj_type == "tables":
            existing_tables = {t for t in names if _table_exists(conn, t)}
            if existing_tables:
                existing["tables"] = existing_tables
        elif obj_type == "indexes":
            existing_idx = {i for i in names if any(_index_exists(conn, t, i) for t in _INDEX_PARENT_TABLES)}
            if existing_idx:
                existing["indexes"] = existing_idx
        else:  # columnas (obj_type es nombre de tabla: "resources", "files", etc.)
            # names es un set de nombres de columnas para esa tabla
            existing_cols = _get_column_names(conn, obj_type) & names
            if existing_cols:
                existing.setdefault("columns", {})[obj_type] = existing_cols
    return existing


def _register_migration(conn: Any, name: str) -> None:
    """Registra una migración como aplicada."""
    from app.utils import utcnow
    conn.execute(
        "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
        (name, utcnow())
    )
    conn.commit()


def _register_legacy_baseline_recognition(conn: Any) -> None:
    """Registra reconocimiento de baseline histórico. Solo para instalaciones legacy."""
    from app.utils import utcnow
    conn.execute(
        "INSERT IGNORE INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
        ("001_schema.sql", "legacy-baseline")
    )
    conn.execute(
        "INSERT IGNORE INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
        ("009_legacy_baseline", utcnow())
    )
    conn.commit()


def _ensure_expected_indexes(conn: Any, mig_name: str, present: set[str]) -> set[str]:
    """Recrea los índices esperados que falten.

    Un índice ausente no deja el esquema ambiguo: las columnas existen y el
    índice sólo mejora consultas, por lo que se crea de forma idempotente.
    Retorna el conjunto de índices esperados (todos presentes tras la llamada).
    """
    expected_indexes = _get_expected_objects(mig_name).get("indexes", set())
    missing = set(expected_indexes) - set(present)
    if not missing:
        return set(expected_indexes)

    for index_name in sorted(missing):
        statement = _INDEX_STATEMENTS.get(index_name)
        if not statement:
            raise RuntimeError(
                f"Índice {index_name} de {mig_name} sin sentencia de recreación. ABORTAR."
            )
        conn.execute(statement)
        conn.commit()
    return set(expected_indexes)


def _safe_execute_migration(conn: Any, mig_name: str, mig_script: str) -> str:
    """
    Ejecuta migración SOLO si sus objetos esperados NO existen.
    Retorna: 'SKIP', 'SKIP_EXISTED', 'EXECUTE' o lanza RuntimeError.
    """
    expected = _get_expected_objects(mig_name)
    existing = _get_existing_objects(conn, expected)
    registered = _is_migration_registered(conn, mig_name)

    # Comparar objetos esperados vs existentes
    all_expected = set()
    for obj_type, names in expected.items():
        if obj_type == "tables":
            all_expected.update(names)
        elif obj_type == "indexes":
            all_expected.update(names)
        else:  # obj_type es nombre de tabla ("resources", "files", etc.)
            # names es un set de nombres de columnas para esa tabla
            for col in names:
                all_expected.add(f"{obj_type}.{col}")

    all_existing = set()
    for obj_type, names in existing.items():
        if obj_type == "tables":
            all_existing.update(names)
        elif obj_type == "indexes":
            all_existing.update(names)
        else:  # obj_type es "columns"
            for table, cols in names.items():
                for col in cols:
                    all_existing.add(f"{table}.{col}")

    if registered:
        if all_expected == all_existing:
            return "SKIP"  # Ya aplicada correctamente
        else:
            missing = all_expected - all_existing
            raise RuntimeError(
                f"Migración {mig_name} registrada pero objetos incompletos: "
                f"faltan {sorted(missing)}. ABORTAR."
            )
    else:
        expected_indexes = set(expected.get("indexes", set()))
        existing_indexes = {i for i in all_existing if i in expected_indexes}
        existing_structural = all_existing - expected_indexes
        expected_structural = all_expected - expected_indexes

        if expected_structural == existing_structural:
            # Columnas/tablas completas: sólo faltan (o sobran) índices.
            _ensure_expected_indexes(conn, mig_name, existing_indexes)
            _register_migration(conn, mig_name)
            return "SKIP_EXISTED"  # Objetos existen sin registro
        elif _is_reexecutable(conn, mig_name, existing_structural):
            # Columnas de la migración ya incluidas por el baseline
            # (001_schema.sql) sin registro: reejecutar es inocuo.
            return "EXECUTE"
        elif existing_structural:
            raise RuntimeError(
                f"Estado ambiguo para {mig_name}: objetos parciales {sorted(all_existing)} "
                f"sin registro de migración. ABORTAR."
            )
        else:
            return "EXECUTE"  # Ejecutar normalmente


def _is_reexecutable(conn: Any, mig_name: str, existing_structural: set[str]) -> bool:
    """Indica si reejecutar la migración no altera el esquema existente.

    Sólo se admite cuando TODO el solapamiento con migraciones previas son
    columnas del baseline con idéntico tipo y valor por defecto, y ninguna
    columna propia de la migración existe ya (en ese caso, el ALTER fallaría).
    """
    if mig_name not in _MIGRATION_ONLY_COLUMNS:
        return False

    if existing_structural & {
        f"{table}.{column}" for table, column in _MIGRATION_ONLY_COLUMNS[mig_name]
    }:
        return False

    for (table, column), default in _BASELINE_COLUMN_DEFAULTS.items():
        row = conn.execute(
            "SELECT COLUMN_TYPE, COLUMN_DEFAULT FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?",
            (table, column),
        ).fetchone()
        if not row:
            return False
        column_type = str(row["COLUMN_TYPE"]).lower()
        column_default = str(row["COLUMN_DEFAULT"])
        if not column_type.startswith("varchar(32)") or column_default != default:
            return False
    return True


def connect(settings: Settings):
    settings.validate_database()
    return _MySQLConnection(settings.database_url)