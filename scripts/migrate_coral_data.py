#!/usr/bin/env python3
"""
Migración de datos corales desde tablas heredadas OSAP (amigos_coral_details, amigos_coral_attributes)
a la tabla groups de Chorus (12 campos nuevos).

Uso:
    python scripts/migrate_coral_data.py

Requiere:
- CHORUS_DATABASE_URL apuntando a la BD de Chorus (ej. osap_chorus_test)
- Variables de entorno para BD OSAP: OSAP_DB_HOST, OSAP_DB_USER, OSAP_DB_PASSWORD, OSAP_DB_NAME (default: osap_api)
"""

import os
import sys
import json
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymysql
from app.config import Settings
from app.db import connect as db_connect
from app.utils import utcnow


def get_osap_connection():
    """Conecta a la BD OSAP (osap_api) usando variables de entorno."""
    host = os.getenv("OSAP_DB_HOST", "127.0.0.1")
    port = int(os.getenv("OSAP_DB_PORT", "3306"))
    user = os.getenv("OSAP_DB_USER", "osap2027")
    password = os.getenv("OSAP_DB_PASSWORD", "2027osapdb")
    database = os.getenv("OSAP_DB_NAME", "osap_api")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def fetch_legacy_details(osap_conn):
    """Obtiene datos de amigos_coral_details."""
    with osap_conn.cursor() as cur:
        cur.execute("SELECT * FROM amigos_coral_details")
        return cur.fetchall()


def fetch_legacy_attributes(osap_conn):
    """Obtiene datos de amigos_coral_attributes agrupados por group_id."""
    with osap_conn.cursor() as cur:
        cur.execute("SELECT * FROM amigos_coral_attributes ORDER BY group_id, facet, position")
        rows = cur.fetchall()

    # Agrupar por group_id
    grouped = {}
    for row in rows:
        gid = row["group_id"]
        if gid not in grouped:
            grouped[gid] = {"language": [], "repertoire": [], "venues": []}

        facet = row["facet"]
        value = row["value"]
        position = row["position"]

        if facet == "language":
            grouped[gid]["language"].append({"value": value, "position": position})
        elif facet == "repertoire":
            grouped[gid]["repertoire"].append({"value": value, "position": position})
        elif facet == "place":
            grouped[gid]["venues"].append({"value": value, "position": position})

    # Ordenar y extraer solo valores (conservar posición)
    result = {}
    for gid, data in grouped.items():
        language = [item["value"] for item in sorted(data["language"], key=lambda x: x["position"])]
        repertoire = sorted(data["repertoire"], key=lambda x: x["position"])
        venues = sorted(data["venues"], key=lambda x: x["position"])
        result[gid] = {
            "language": language if language else None,
            "repertoire": repertoire if repertoire else None,
            "venues": venues if venues else None,
        }
    return result


def map_legacy_to_chorus(detail_row, attr_data):
    """Mapea una fila de detail + atributos a los 12 campos de Chorus."""
    gid = detail_row["group_id"]

    # Mapeo directo de campos simples
    mapped = {
        "foundation_date": detail_row.get("foundation_date"),
        "dissolution_date": detail_row.get("dissolution_date"),
        "locality": detail_row.get("locality"),
        "region": detail_row.get("region"),
        "country_code": detail_row.get("country_code"),
        "venue": detail_row.get("venue"),
        "formation_type": detail_row.get("formation_type"),
        "member_count": detail_row.get("member_count"),
        "public_email": detail_row.get("public_email"),
    }

    # JSON fields desde atributos
    attr = attr_data.get(gid, {})
    mapped["language"] = attr.get("language")
    mapped["repertoire"] = attr.get("repertoire")
    mapped["venues"] = attr.get("venues")

    return mapped


def serialize_json(value):
    """Serializa a JSON para almacenar en BD."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def get_chorus_group(conn, group_id):
    """Obtiene un grupo de Chorus por ID."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM groups WHERE id = %s", (gid,))
        return cur.fetchone()


def main():
    # Configuración
    chorus_db_url = os.getenv("CHORUS_DATABASE_URL")
    if not chorus_db_url:
        print("ERROR: CHORUS_DATABASE_URL no definido")
        return 1

    print("=== Iniciando migración de datos corales ===")
    print(f"Chorus DB: {chorus_db_url}")

    # 1. Conectar a OSAP (tabla heredada)
    try:
        osap_conn = get_osap_connection()
        print(f"Conectado a OSAP (osap_api)")
    except Exception as e:
        print(f"ERROR conectando a OSAP: {e}")
        return 1

    # 2. Cargar datos heredados
    print("Cargando datos de amigos_coral_details...")
    legacy_details = fetch_legacy_details(osap_conn)
    print(f"  {len(legacy_details)} grupos en amigos_coral_details")

    print("Cargando datos de amigos_coral_attributes...")
    attr_data = fetch_legacy_attributes(osap_conn)
    print(f"  {len(attr_data)} grupos con atributos en amigos_coral_attributes")

    osap_conn.close()

    # 3. Procesar cada grupo legacy en Chorus
    print("Conectando a Chorus...")
    updated = 0
    skipped = 0
    errors = 0

    CORAL_FIELDS = [
        "foundation_date", "dissolution_date", "locality", "region",
        "country_code", "venue", "formation_type", "member_count",
        "public_email", "language", "repertoire", "venues",
    ]

    with db_connect(Settings.load()) as chorus_conn:
        for detail in legacy_details:
            gid = detail["group_id"]
            mapped = map_legacy_to_chorus(detail, attr_data)

            # Obtener el estado actual del grupo en Chorus
            current = chorus_conn.execute(
                "SELECT " + ", ".join(CORAL_FIELDS) + " FROM groups WHERE id = %s",
                (gid,),
            ).fetchone()

            if current is None:
                print(f"  Grupo {gid}: NO existe en Chorus, se omite (no se crea grupo nuevo)")
                skipped += 1
                continue

            # Construir UPDATE SOLO para columnas actualmente NULL (no sobrescribir)
            fields = []
            values = []
            overwritten = []
            for field in CORAL_FIELDS:
                value = mapped.get(field)
                if value is None:
                    continue  # No hay dato de origen
                if current.get(field) is not None:
                    overwritten.append(field)
                    continue  # Ya existe en Chorus: no sobrescribir
                if field in ("language", "repertoire", "venues"):
                    fields.append(f"{field}=%s")
                    values.append(json.dumps(value, ensure_ascii=False))
                else:
                    fields.append(f"{field}=%s")
                    values.append(value)

            if overwritten:
                print(f"  Grupo {gid}: conservados valores existentes en {overwritten}")

            if not fields:
                print(f"  Grupo {gid}: sin campos NULL que rellenar, se omite")
                skipped += 1
                continue

            values.append(gid)
            try:
                chorus_conn.execute(
                    f"UPDATE groups SET {', '.join(fields)} WHERE id = %s",
                    tuple(values),
                )
                chorus_conn.commit()
                print(f"  Grupo {gid}: ACTUALIZADO ({len(fields)} campos)")
                updated += 1
            except Exception as e:
                print(f"  ERROR en grupo {gid}: {e}")
                errors += 1

    print(f"\n=== Resumen ===")
    print(f"  Actualizados: {updated}")
    print(f"  Omitidos (sin grupo en Chorus): {skipped}")
    print(f"  Errores: {errors}")
    print("=== Migración completada ===")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())