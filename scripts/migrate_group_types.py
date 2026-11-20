#!/usr/bin/env python3
"""
Carga idempotente de 48 registros group_types desde OSAP amigos_group_types.
Estrategia: INSERT ... ON DUPLICATE KEY UPDATE (preserva code PK, actualiza resto).
"""

from __future__ import annotations

import pymysql
from typing import Any


SOURCE_DSN = "mysql+pymysql://osap2027:2027osapdb@127.0.0.1:3306/osap_api"
TARGET_DSN = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"


GROUP_TYPES_DATA = [
    {"code": "vocal", "parent_code": None, "name": "Agrupaciones Vocales", "kind": "coral", "sort_order": 0},
    {"code": "coral", "parent_code": "vocal", "name": "Coral", "kind": "coral", "sort_order": 1},
    {"code": "coro_mixto", "parent_code": "coral", "name": "Coro Mixto (SATB)", "kind": "coral", "sort_order": 2},
    {"code": "coro_voces_blancas", "parent_code": "coral", "name": "Coro de Voces Blancas", "kind": "coral", "sort_order": 3},
    {"code": "coro_voces_graves", "parent_code": "coral", "name": "Coro de Voces Graves", "kind": "coral", "sort_order": 4},
    {"code": "ensemble_vocal", "parent_code": "vocal", "name": "Ensemble Vocal", "kind": "ensemble", "sort_order": 5},
    {"code": "grupo_camara_vocal", "parent_code": "vocal", "name": "Grupo de Cámara Vocal", "kind": "ensemble", "sort_order": 6},
    {"code": "cuarteto_vocal", "parent_code": "vocal", "name": "Cuarteto Vocal", "kind": "ensemble", "sort_order": 7},
    {"code": "escolania", "parent_code": "vocal", "name": "Escolanía", "kind": "coral", "sort_order": 8},
    {"code": "orfeon", "parent_code": "vocal", "name": "Orfeón", "kind": "coral", "sort_order": 9},
    {"code": "schola_cantorum", "parent_code": "vocal", "name": "Schola Cantorum", "kind": "coral", "sort_order": 10},
    {"code": "orquestal", "parent_code": None, "name": "Agrupaciones Orquestales", "kind": "orquesta", "sort_order": 11},
    {"code": "orquesta_sinfonica", "parent_code": "orquestal", "name": "Orquesta Sinfónica", "kind": "orquesta", "sort_order": 12},
    {"code": "orquesta_filarmonica", "parent_code": "orquestal", "name": "Orquesta Filarmónica", "kind": "orquesta", "sort_order": 13},
    {"code": "orquesta_camara", "parent_code": "orquestal", "name": "Orquesta de Cámara", "kind": "orquesta", "sort_order": 14},
    {"code": "orquesta_cuerdas", "parent_code": "orquestal", "name": "Orquesta de Cuerdas", "kind": "orquesta", "sort_order": 15},
    {"code": "orquesta_barroca", "parent_code": "orquestal", "name": "Orquesta Barroca", "kind": "orquesta", "sort_order": 16},
    {"code": "orquesta_pulso_pua", "parent_code": "orquestal", "name": "Orquesta de Pulso y Púa (Rondalla / Plectro)", "kind": "orquesta", "sort_order": 17},
    {"code": "bandas", "parent_code": None, "name": "Bandas y Agrupaciones de Viento", "kind": "banda", "sort_order": 18},
    {"code": "banda_musica", "parent_code": "bandas", "name": "Banda de Música", "kind": "banda", "sort_order": 19},
    {"code": "banda_sinfonica", "parent_code": "bandas", "name": "Banda Sinfónica", "kind": "banda", "sort_order": 20},
    {"code": "banda_militar", "parent_code": "bandas", "name": "Banda Militar", "kind": "banda", "sort_order": 21},
    {"code": "agrupacion_musical", "parent_code": "bandas", "name": "Agrupación Musical (Procesional)", "kind": "banda", "sort_order": 22},
    {"code": "cornetas_tambores", "parent_code": "bandas", "name": "Banda de Cornetas y Tambores", "kind": "banda", "sort_order": 23},
    {"code": "fanfarria", "parent_code": "bandas", "name": "Fanfarria", "kind": "banda", "sort_order": 24},
    {"code": "brass_band", "parent_code": "bandas", "name": "Brass Band", "kind": "banda", "sort_order": 25},
    {"code": "charanga", "parent_code": "bandas", "name": "Charanga", "kind": "banda", "sort_order": 26},
    {"code": "camara", "parent_code": None, "name": "Música de Cámara", "kind": "ensemble", "sort_order": 27},
    {"code": "duo", "parent_code": "camara", "name": "Dúo", "kind": "ensemble", "sort_order": 28},
    {"code": "trio_piano", "parent_code": "camara", "name": "Trío con Piano", "kind": "ensemble", "sort_order": 29},
    {"code": "trio_cuerdas", "parent_code": "camara", "name": "Trío de Cuerdas", "kind": "ensemble", "sort_order": 30},
    {"code": "cuarteto_cuerdas", "parent_code": "camara", "name": "Cuarteto de Cuerdas", "kind": "ensemble", "sort_order": 31},
    {"code": "quinteto_madera", "parent_code": "camara", "name": "Quinteto de Viento-Madera", "kind": "ensemble", "sort_order": 32},
    {"code": "quinteto_metales", "parent_code": "camara", "name": "Quinteto de Metales", "kind": "ensemble", "sort_order": 33},
    {"code": "octeto", "parent_code": "camara", "name": "Octeto", "kind": "ensemble", "sort_order": 34},
    {"code": "jazz", "parent_code": None, "name": "Jazz, Moderna y Popular", "kind": "grupo", "sort_order": 35},
    {"code": "big_band", "parent_code": "jazz", "name": "Big Band", "kind": "grupo", "sort_order": 36},
    {"code": "combo_jazz", "parent_code": "jazz", "name": "Combo de Jazz", "kind": "grupo", "sort_order": 37},
    {"code": "rock_pop", "parent_code": "jazz", "name": "Grupo de Rock / Pop", "kind": "grupo", "sort_order": 38},
    {"code": "blues_funk", "parent_code": "jazz", "name": "Banda de Blues / Funk", "kind": "grupo", "sort_order": 39},
    {"code": "orquesta_baile", "parent_code": "jazz", "name": "Orquesta de Baile / Verbena", "kind": "grupo", "sort_order": 40},
    {"code": "tradicional", "parent_code": None, "name": "Tradicional y Folclore", "kind": "grupo", "sort_order": 41},
    {"code": "grupo_folk", "parent_code": "tradicional", "name": "Grupo Folk", "kind": "grupo", "sort_order": 42},
    {"code": "banda_gaitas", "parent_code": "tradicional", "name": "Banda de Gaitas", "kind": "banda", "sort_order": 43},
    {"code": "cobla", "parent_code": "tradicional", "name": "Cobla", "kind": "grupo", "sort_order": 44},
    {"code": "tuna", "parent_code": "tradicional", "name": "Tuna", "kind": "grupo", "sort_order": 45},
    {"code": "mariachi", "parent_code": "tradicional", "name": "Mariachi", "kind": "grupo", "sort_order": 46},
    {"code": "grupo_tradicional", "parent_code": "tradicional", "name": "Grupo de Música Tradicional", "kind": "grupo", "sort_order": 47},
]


def parse_dsn(dsn: str) -> dict[str, Any]:
    """Parse mysql+pymysql://user:pass@host:port/db"""
    import urllib.parse
    dsn = dsn.replace("mysql+pymysql://", "mysql://")
    parsed = urllib.parse.urlparse(dsn)
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": parsed.username or "",
        "password": parsed.password or "",
        "database": (parsed.path or "/").lstrip("/"),
    }


def load_group_types() -> tuple[int, int]:
    """Carga los 48 registros. Retorna (insertados, actualizados)."""
    src = parse_dsn(SOURCE_DSN)
    tgt = parse_dsn(TARGET_DSN)

    # Leer origen para verificación
    with pymysql.connect(**src, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor) as sconn:
        with sconn.cursor() as scur:
            scur.execute("SELECT code, parent_code, name, kind, sort_order FROM amigos_group_types")
            source_rows = {r["code"]: r for r in scur.fetchall()}

    print(f"Origen: {len(source_rows)} registros en amigos_group_types")

    # Cargar en destino
    with pymysql.connect(**tgt, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor) as tconn:
        with tconn.cursor() as tcur:
            # Verificar tabla existe
            tcur.execute("SHOW TABLES LIKE 'group_types'")
            if not tcur.fetchone():
                raise RuntimeError("Tabla group_types no existe. Ejecutar migración 018 primero.")

            inserted = 0
            updated = 0

            for row in GROUP_TYPES_DATA:
                code = row["code"]
                tcur.execute(
                    """
                    INSERT INTO group_types (code, parent_code, name, kind, sort_order)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        parent_code = VALUES(parent_code),
                        name = VALUES(name),
                        kind = VALUES(kind),
                        sort_order = VALUES(sort_order)
                    """,
                    (row["code"], row["parent_code"], row["name"], row["kind"], row["sort_order"]),
                )
                if tcur.rowcount == 1:
                    inserted += 1
                elif tcur.rowcount == 2:
                    updated += 1

            tconn.commit()

            # Verificación
            tcur.execute("SELECT code, parent_code, name, kind, sort_order FROM group_types")
            target_rows = {r["code"]: r for r in tcur.fetchall()}

    print(f"Destino: {len(target_rows)} registros en group_types")
    print(f"  Insertados: {inserted}, Actualizados: {updated}")

    # Validar integridad
    errors = []
    for code, src_row in source_rows.items():
        if code not in target_rows:
            errors.append(f"FALTA en destino: {code}")
            continue
        tgt_row = target_rows[code]
        for field in ("parent_code", "name", "kind", "sort_order"):
            src_val = src_row[field]
            tgt_val = tgt_row[field]
            if src_val != tgt_val:
                errors.append(f"DIVERGENCIA {code}.{field}: origen={src_val!r} destino={tgt_val!r}")

    # Verificar códigos extra en destino
    extra = set(target_rows.keys()) - set(source_rows.keys())
    for code in extra:
        errors.append(f"EXTRA en destino (no en origen): {code}")

    if errors:
        print("\nERRORES DE VALIDACION:")
        for e in errors:
            print(f"  - {e}")
        return inserted, updated

    print("\nOK: 48 codigos, jerarquia, nombres, kinds y sort_order conservados.")
    return inserted, updated


if __name__ == "__main__":
    load_group_types()