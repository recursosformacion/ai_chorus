"""Actualizador seguro de la base de datos de Chorus (dev / test / prod).

Aplica las migraciones pendientes con:

  1. Protección sobre la CONEXIÓN EFECTIVA (base, usuario y MariaDB 10.4),
     con expectativas distintas por entorno. Nunca se fía de la URL.
  3. Copia de seguridad completa con mysqldump antes de tocar nada.
  4. Comprobaciones previas de esquema, volumen e integridad referencial.
  5. Aplicación migración a migración, registrando cada una sólo si tiene éxito.
  6. Verificación posterior de esquema e integridad.
  7. Aborto inmediato ante cualquier fallo, conservando la copia.

Por defecto NO modifica nada: hay que pedir --apply.

Entornos:
    dev   osap_chorus       osap2027        (desarrollo)
    test  osap_chorus_test  osap2027_test   (pruebas / CI)
    prod  la que se indique  la que se indique (requiere confirmación expresa)

Uso:
    python scripts/upgrade_dev_db.py --env dev --verify-only
    python scripts/upgrade_dev_db.py --env dev
    python scripts/upgrade_dev_db.py --env dev --apply
    python scripts/upgrade_dev_db.py --env test --apply
    python scripts/upgrade_dev_db.py --env prod \
        --database-url "mysql+pymysql://USUARIO:CLAVE@HOST:3306/BASE" \
        --apply --backup-to "D:\\backups" --confirm-production

La variable CHORUS_DATABASE_URL se usa si no se pasa --database-url.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.db import (
    _execute_sql_script,
    _get_table_names,
    _verify_final_schema,
    connect as db_connect,
)
from app.dbguard import probe_effective_connection
from scripts.rebuild_test_db import MIGRATIONS, _verify_spaces_schema

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations" / "mysql"

MIN_VERSION_PREFIX = "10.4."


class UpgradeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    """Destino esperado de una actualización."""

    name: str
    database: str
    user: str
    backup_dir: Path


TARGETS = {
    "dev": Target(
        name="desarrollo",
        database="osap_chorus",
        user="osap2027",
        backup_dir=Path(r"C:\Users\migarcia\AppData\Local\osap-dev\backups"),
    ),
    "test": Target(
        name="pruebas",
        database="osap_chorus_test",
        user="osap2027_test",
        backup_dir=Path(r"C:\Users\migarcia\AppData\Local\osap-dev\backups"),
    ),
    "prod": Target(
        name="producción",
        database="",  # obligatorio indicarlo
        user="",      # obligatorio indicarlo
        backup_dir=Path(r"C:\Users\migarcia\AppData\Local\osap-dev\backups\prod"),
    ),
}


def _fail(message: str) -> None:
    print(f"\nERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def _parse_url(database_url: str) -> dict[str, str]:
    from urllib.parse import urlparse

    parsed = urlparse(database_url.replace("+pymysql", ""))
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": str(parsed.port or 3306),
        "user": parsed.username or "",
        "password": parsed.password or "",
        "database": (parsed.path or "").lstrip("/"),
    }


def _guard(settings: Settings, target: Target):
    """Protección sobre la conexión efectiva. Devuelve la conexión abierta.

    Comprueba base de datos, usuario y versión MariaDB reales en el servidor,
    no el texto de la URL. Además impide cruzar entornos.
    """
    if not settings.database_url:
        _fail("No hay URL de conexión (CHORUS_DATABASE_URL o --database-url)")

    try:
        conn = db_connect(settings)
    except Exception as exc:
        _fail(f"No se pudo conectar a MariaDB: {exc}")

    try:
        effective = probe_effective_connection(conn)
    except Exception as exc:
        conn.close()
        _fail(f"No se pudo consultar la conexión efectiva: {exc}")

    problems: list[str] = []
    if effective.database != target.database:
        problems.append(
            f"base efectiva {effective.database!r} != {target.database!r} (entorno {target.name})"
        )
    if effective.user != target.user:
        problems.append(
            f"usuario efectivo {effective.user!r} != {target.user!r} (entorno {target.name})"
        )
    if not effective.is_mariadb:
        problems.append(f"el servidor no es MariaDB ({effective.version!r})")
    elif not effective.version.startswith(MIN_VERSION_PREFIX):
        problems.append(
            f"MariaDB {effective.version!r} fuera de la línea {MIN_VERSION_PREFIX}"
        )

    if problems:
        conn.close()
        _fail("Operación bloqueada: " + "; ".join(problems))
    return conn


def _mysqldump_path() -> str:
    for candidate in (
        r"C:\xampp\mysql\bin\mysqldump.exe",
        r"C:\Program Files\MariaDB 10.4\bin\mysqldump.exe",
    ):
        if Path(candidate).exists():
            return candidate
    raise UpgradeError("No se encontró mysqldump.exe (XAMPP o MariaDB 10.4)")


def make_backup(settings: Settings, target: Target) -> Path:
    info = _parse_url(settings.database_url)
    target.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = target.backup_dir / f"{info['database']}-{stamp}.sql"

    cmd = [
        _mysqldump_path(),
        f"--host={info['host']}",
        f"--port={info['port']}",
        f"--user={info['user']}",
        f"--password={info['password']}",
        "--single-transaction",
        "--quick",
        "--routines",
        "--triggers",
        "--events",
        "--default-character-set=utf8mb4",
        "--databases",
        info["database"],
    ]
    # mysqldump escribe el volcado en stdout: se captura en bytes (la salida
    # contiene UTF-8 y el codec local cp1252 falla) y se escribe al fichero.
    result = subprocess.run(cmd, capture_output=True)
    stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        raise UpgradeError(f"mysqldump falló: {stderr[:400]}")
    dump = result.stdout or b""
    if not dump:
        raise UpgradeError(f"mysqldump no generó salida: {stderr[:400]}")
    out.write_bytes(dump)
    if not out.exists() or out.stat().st_size == 0:
        raise UpgradeError("mysqldump no generó fichero o está vacío")

    head = dump[:64].decode("utf-8", errors="replace")
    if "MariaDB dump" not in head:
        raise UpgradeError(f"El volcado no parece un dump de MariaDB: {head[:60]!r}")

    print(f"Copia de seguridad: {out} ({out.stat().st_size} bytes)")
    return out


def preflight(conn) -> dict:
    problems: list[str] = []

    info = conn.execute("SELECT DATABASE() AS db, @@version AS ver").fetchone()
    print(f"Base: {info['db']}   Servidor: {info['ver']}")

    required_tables = {
        "groups", "group_members", "group_sections", "group_articles",
        "group_article_media", "works", "resources", "files",
    }
    existing = set(_get_table_names(conn))
    missing = required_tables - existing
    if missing:
        problems.append(f"faltan tablas base: {sorted(missing)}")

    if "groups" in existing:
        cols = {
            r["COLUMN_NAME"]
            for r in conn.execute(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'groups'"
            ).fetchall()
        }
        for column in ("created_by", "created_at", "updated_at", "name"):
            if column not in cols:
                problems.append(f"groups: falta columna {column}")

    volumes = {}
    for table in sorted(existing):
        volumes[table] = int(
            conn.execute(f"SELECT COUNT(*) AS c FROM `{table}`").fetchone()["c"]
        )

    orphan_checks = {
        "group_members sin grupo": (
            "SELECT COUNT(*) AS c FROM group_members m "
            "LEFT JOIN groups g ON g.id = m.group_id WHERE g.id IS NULL"
        ),
        "group_sections sin grupo": (
            "SELECT COUNT(*) AS c FROM group_sections s "
            "LEFT JOIN groups g ON g.id = s.group_id WHERE g.id IS NULL"
        ),
        "group_articles sin grupo": (
            "SELECT COUNT(*) AS c FROM group_articles a "
            "LEFT JOIN groups g ON g.id = a.group_id "
            "WHERE a.group_id IS NOT NULL AND g.id IS NULL"
        ),
        "group_article_media sin articulo": (
            "SELECT COUNT(*) AS c FROM group_article_media m "
            "LEFT JOIN group_articles a ON a.id = m.article_id WHERE a.id IS NULL"
        ),
    }
    for label, sql in orphan_checks.items():
        count = int(conn.execute(sql).fetchone()["c"])
        if count:
            problems.append(f"{label}: {count} filas")
        print(f"  {label}: {count}")

    print("\nVolumen de datos:")
    for table, count in volumes.items():
        print(f"  {table:26s} {count}")

    return {"problems": problems, "volumes": volumes}


def pending_migrations(conn) -> list[str]:
    registered = {
        r["name"]
        for r in conn.execute("SELECT name FROM chorus_schema_migrations").fetchall()
    }
    return [m for m in MIGRATIONS if m not in registered]


def apply_migrations(conn, pending: list[str]) -> None:
    for name in pending:
        path = MIGRATIONS_DIR / name
        if not path.exists():
            raise UpgradeError(f"No existe el fichero de migración {path}")
        print(f"\n--- Aplicando {name} ---")
        script = path.read_text("utf-8")
        try:
            _execute_sql_script(conn, script, is_mysql=True)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise UpgradeError(
                f"Migración {name} FALLÓ: {exc}\n"
                "No se ha registrado. El DDL de MariaDB no es transaccional, "
                "así que puede haber cambios parciales de esta migración: "
                "restaura la copia de seguridad antes de reintentar."
            ) from exc
        conn.execute(
            "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
            (name, "upgrade"),
        )
        conn.commit()
        print(f"    OK {name}")


def verify(conn, target: Target) -> None:
    print("\n=== VERIFICACIÓN POSTERIOR ===")
    ok, errors = _verify_final_schema(conn)
    print(f"  esquema final: {'OK' if ok else 'FALLO'}")
    for e in errors:
        print(f"    - {e}")

    ok2, errors2 = _verify_spaces_schema(conn)
    print(f"  esquema spaces/preparación: {'OK' if ok2 else 'FALLO'}")
    for e in errors2:
        print(f"    - {e}")

    registered = {
        r["name"]
        for r in conn.execute("SELECT name FROM chorus_schema_migrations").fetchall()
    }
    missing = [m for m in MIGRATIONS if m not in registered]
    if missing:
        errors.append(f"migraciones sin registrar: {missing}")

    if errors or errors2:
        raise UpgradeError("La verificación posterior ha fallado")

    info = conn.execute("SELECT DATABASE() AS db, CURRENT_USER() AS usr").fetchone()
    print(f"  destino: {info['db']} como {info['usr']} ({target.name})")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Actualiza la BD de Chorus (dev/test/prod) de forma segura"
    )
    parser.add_argument("--env", choices=sorted(TARGETS), default="dev")
    parser.add_argument("--database-url", default="", help="URL de conexión (si no se usa CHORUS_DATABASE_URL)")
    parser.add_argument("--apply", action="store_true", help="aplicar (por defecto sólo simula)")
    parser.add_argument("--verify-only", action="store_true", help="sólo informar del estado")
    parser.add_argument("--no-backup", action="store_true", help="omitir copia de seguridad")
    parser.add_argument("--restore", metavar="FILE", help="restaurar desde un dump")
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="confirmación explícita para --env prod",
    )
    args = parser.parse_args()

    target = TARGETS[args.env]

    if args.env == "prod":
        if not args.confirm_production:
            _fail(
                "--env prod exige --confirm-production. No se actualizará "
                "producción sin confirmación expresa."
            )
        if not args.database_url:
            _fail(
                "--env prod exige --database-url con la cadena de producción; "
                "no se usará CHORUS_DATABASE_URL por seguridad."
            )

    settings = Settings.load()
    if args.database_url:
        settings = Settings(
            **{**settings.__dict__, "database_url": args.database_url}
        )

    if args.restore:
        dump = Path(args.restore)
        if not dump.is_file():
            _fail(f"No existe el dump {dump}")
        if args.env == "prod" and not args.confirm_production:
            _fail("Restaurar en producción exige --confirm-production")
        info = _parse_url(settings.database_url)
        mysql = r"C:\xampp\mysql\bin\mysql.exe"
        cmd = [
            mysql,
            f"--host={info['host']}", f"--port={info['port']}",
            f"--user={info['user']}", f"--password={info['password']}",
            "--default-character-set=utf8mb4",
        ]
        print(f"Restaurando {dump} en {info['database']}...")
        with dump.open("rb") as handle:
            result = subprocess.run(cmd, stdin=handle, capture_output=True, text=True)
        if result.returncode != 0:
            _fail(f"La restauración falló: {result.stderr.strip()[:400]}")
        print("Restauración completada.")
        return 0

    conn = _guard(settings, target)
    try:
        if args.verify_only:
            pending = pending_migrations(conn)
            print(f"\nMigraciones pendientes ({len(pending)}):")
            for name in pending:
                print(f"  - {name}")
            ok, errors = _verify_final_schema(conn)
            print(f"\nEsquema final completo: {'OK' if ok else 'INCOMPLETO'}")
            for e in errors:
                print(f"  - {e}")
            ok2, errors2 = _verify_spaces_schema(conn)
            print(f"Esquema spaces/preparación: {'OK' if ok2 else 'INCOMPLETO'}")
            for e in errors2:
                print(f"  - {e}")
            return 0

        report = preflight(conn)
        pending = pending_migrations(conn)
        print(f"\nMigraciones pendientes ({len(pending)}): {pending if pending else 'ninguna'}")

        if not pending:
            print("\nNo hay nada que aplicar.")
            verify(conn, target)
            return 0

        if report["problems"]:
            print("\nPREFLIGHT CON PROBLEMAS:", file=sys.stderr)
            for p in report["problems"]:
                print(f"  - {p}", file=sys.stderr)
            _fail("Se aborta antes de tocar la base de datos.")

        if not args.apply:
            print(f"\n=== SIMULACIÓN ({target.name}) ===")
            print("No se ha modificado nada. Aplica realmente con --apply")
            return 0

        if not args.no_backup:
            make_backup(settings, target)
        elif args.env == "prod":
            _fail("En producción la copia de seguridad es obligatoria")

        apply_migrations(conn, pending)
        verify(conn, target)
        print(f"\n=== ACTUALIZACIÓN COMPLETADA ({target.name}) ===")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())