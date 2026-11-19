# Integración coral Chorus 0.15 — Informe técnico corregido y validado

**Estado**: Solo análisis y documentación. **No se modifica ningún archivo, repositorio ni base de datos.**

**Autorización pendiente**: Se requiere autorización expresa tras revisión de este informe.

---

## 1. Modelo definitivo — 12 campos nuevos en `groups`

| # | Columna | Tipo (MySQL) | Tipo (SQLite) | NULL | Descripción |
|---|---------|--------------|---------------|------|-------------|
| 1 | `foundation_date` | `VARCHAR(32)` | `TEXT` | Sí | Fecha de fundación (ISO) |
| 2 | `dissolution_date` | `VARCHAR(32)` | `TEXT` | Sí | Fecha de disolución (ISO) |
| 3 | `locality` | `VARCHAR(255)` | `TEXT` | Sí | Localidad |
| 4 | `region` | `VARCHAR(255)` | `TEXT` | Sí | Provincia/región |
| 5 | `country_code` | `CHAR(2)` | `TEXT` | Sí | Código país ISO-3166-1 alpha-2 |
| 6 | `venue` | `VARCHAR(500)` | `TEXT` | Sí | Sede principal (dato escalar de `coral_details.venue`) |
| 7 | `formation_type` | `VARCHAR(64)` | `TEXT` | Sí | Tipo de formación (p.ej. `mixed`, `male`, `female`, `children`) |
| 8 | `member_count` | `INT` | `INTEGER` | Sí | Número de miembros |
| 9 | `public_email` | `VARCHAR(320)` | `TEXT` | Sí | Correo público de contacto |
| 10 | `language` | `JSON` | `TEXT` | Sí | Array de códigos ISO-639-1 ordenados por `position` (p.ej. `["ca","es"]`) |
| 11 | `repertoire` | `JSON` | `TEXT` | Sí | Array de objetos `{value, position}` ordenados por `position` |
| 12 | `venues` | `JSON` | `TEXT` | Sí | Array de objetos `{value, position}` ordenados por `position` (desde `facet='place'`) |

**Total: 12 columnas** (no 11, no 19).

**Campos excluidos deliberadamente**:
- `director_person_id`, `director_label` → No se crea columna `director` ni tabla `directors`. El rol de director se expresa mediante `musical_role_id = 'director'` en `group_members` (texto libre, convención provisional, no normalizado).
- `website` → Ya existe `website` en `groups`.
- `linked_entity` → Mapea a `entity_id` existente (no se duplica).
- `created_at`, `updated_at` de `coral_details` → No se migran; Chorus usa sus propias timestamps.

---

## 2. Correspondencia exacta de los dos grupos de prueba

### Coral Lo Rossinyol (`719c3051fab035e1`)

| Campo | Valor origen | Valor final en Chorus |
|-------|--------------|----------------------|
| `foundation_date` | `1900-01-01` | `"1900-01-01"` |
| `dissolution_date` | `NULL` | `NULL` |
| `locality` | `Sant Antoni de Vilamajor` | `"Sant Antoni de Vilamajor"` |
| `region` | `Barcelona` | `"Barcelona"` |
| `country_code` | `ES` | `"ES"` |
| `venue` | `Escplas Velles/El Patronat` | `"Escplas Velles/El Patronat"` |
| `formation_type` | `mixed` | `"mixed"` |
| `member_count` | `20` | `20` |
| `public_email` | `NULL` | `NULL` |
| `language` | attrs: `facet=language, value=ca, pos=0` | `["ca"]` |
| `repertoire` | (sin registros) | `NULL` |
| `venues` | attrs: `facet=place, value=La Sala, pos=1` y `El Patronat, pos=2` | `[{"value":"La Sala","position":1},{"value":"El Patronat","position":2}]` |

### Coral Turo del Vent (`df72ae26985011a4`)

| Campo | Valor origen | Valor final en Chorus |
|-------|--------------|----------------------|
| `foundation_date` | `1984-09-01` | `"1984-09-01"` |
| `dissolution_date` | `NULL` | `NULL` |
| `locality` | `Llinars del valles` | `"Llinars del valles"` |
| `region` | `Barcelona` | `"Barcelona"` |
| `country_code` | `ES` | `"ES"` |
| `venue` | `Mas Baga` | `"Mas Baga"` |
| `formation_type` | `mixed` | `"mixed"` |
| `member_count` | `30` | `30` |
| `public_email` | `NULL` | `NULL` |
| `language` | (sin registros) | `NULL` |
| `repertoire` | attrs: pos 0 y 1 | `[{"value":"Abarca una amplia variedad...","position":0},{"value":"centrado en los 60 años...","position":1}]` |
| `venues` | attrs: `facet=place, value=Teatre Auditori..., pos=2` | `[{"value":"Teatre Auditori de Llinars del Vallès","position":2}]` |

### Grupo Prueba (`1809b94b243a5f46`)

- No existe en `amigos_coral_details` ni en `amigos_coral_attributes`.
- **Todos los 12 campos = `NULL`** (no arrays vacíos, no cadenas vacías).

---

## 3. SQL de creación de columnas (por motor)

### MySQL / MariaDB 10.4.32 (`migrations/mysql/016_coral_integration.sql`)

```sql
-- Chorus 0.15: integración de ficha coral (12 columnas)
-- NO usar JSON_ARRAYAGG (no existe en MariaDB 10.4)
-- Las columnas JSON se poblarán desde Python en la migración controlada

ALTER TABLE `groups`
  ADD COLUMN `foundation_date` VARCHAR(32) NULL AFTER `technical_description`,
  ADD COLUMN `dissolution_date` VARCHAR(32) NULL AFTER `foundation_date`,
  ADD COLUMN `locality` VARCHAR(255) NULL AFTER `dissolution_date`,
  ADD COLUMN `region` VARCHAR(255) NULL AFTER `locality`,
  ADD COLUMN `country_code` CHAR(2) NULL AFTER `region`,
  ADD COLUMN `venue` VARCHAR(500) NULL AFTER `country_code`,
  ADD COLUMN `formation_type` VARCHAR(64) NULL AFTER `venue`,
  ADD COLUMN `member_count` INT NULL AFTER `formation_type`,
  ADD COLUMN `public_email` VARCHAR(320) NULL AFTER `member_count`,
  ADD COLUMN `language` JSON NULL AFTER `public_email`,
  ADD COLUMN `repertoire` JSON NULL AFTER `language`,
  ADD COLUMN `venues` JSON NULL AFTER `repertoire`;
```

### SQLite (`migrations/sqlite/016_coral_integration.sql`)

```sql
-- Chorus 0.15: integración de ficha coral (12 columnas)
-- SQLite: JSON se guarda como TEXT; validación CHECK opcional
-- NO usar json_group_array aquí; poblamiento desde Python

ALTER TABLE groups ADD COLUMN foundation_date TEXT NULL;
ALTER TABLE groups ADD COLUMN dissolution_date TEXT NULL;
ALTER TABLE groups ADD COLUMN locality TEXT NULL;
ALTER TABLE groups ADD COLUMN region TEXT NULL;
ALTER TABLE groups ADD COLUMN country_code TEXT NULL;
ALTER TABLE groups ADD COLUMN venue TEXT NULL;
ALTER TABLE groups ADD COLUMN formation_type TEXT NULL;
ALTER TABLE groups ADD COLUMN member_count INTEGER NULL;
ALTER TABLE groups ADD COLUMN public_email TEXT NULL;
ALTER TABLE groups ADD COLUMN language TEXT NULL;
ALTER TABLE groups ADD COLUMN repertoire TEXT NULL;
ALTER TABLE groups ADD COLUMN venues TEXT NULL;

-- Constraints opcionales para validar JSON sintácticamente
-- CREATE TRIGGER chk_groups_language_json ...
-- (Omitidos por simplicidad; validación real en capa Python)
```

**Nota**: El orden `AFTER` en MySQL es informativo; en SQLite se añaden al final.

---

## 4. Estrategia de migración común en Python (MariaDB + SQLite)

**Principio**: Una sola función Python que lee OSAP ordenado por `position`, construye estructuras JSON en memoria y escribe en Chorus. **No se usa SQL de agregación JSON** (ni `JSON_ARRAYAGG` ni `json_group_array`), así el código es idéntico para ambos motores.

### Pseudocódigo / Estructura real

```python
def migrate_coral_details(settings: Settings) -> None:
    """
    Migración controlada, idempotente por grupo.
    Debe ejecutarse UNA VEZ tras aplicar el ALTER TABLE (migración 016).
    """
    from app.db import connect as db_connect
    import pymysql
    import json
    from urllib.parse import urlparse

    # 1. Conexión OSAP (solo lectura)
    osap_url = os.environ.get("OSAP_DATABASE_URL")
    if not osap_url:
        raise RuntimeError("OSAP_DATABASE_URL requerido")
    parsed = urlparse(osap_url.replace("mysql+pymysql://", "mysql://", 1))
    osap = pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username or "",
        password=parsed.password or "",
        database=(parsed.path or "/").lstrip("/"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

    # 2. Conexión Chorus (lectura/escritura)
    chorus = db_connect(settings)

    try:
        with osap.cursor() as osap_cur, chorus:
            # 2a. Leer TODOS los coral_details
            osap_cur.execute("SELECT * FROM amigos_coral_details")
            details_by_gid = {str(row["group_id"]): row for row in osap_cur.fetchall()}

            # 2b. Leer TODOS los coral_attributes ordenados por facet, position
            osap_cur.execute(
                "SELECT group_id, facet, value, position "
                "FROM amigos_coral_attributes ORDER BY group_id, facet, position"
            )
            attrs_by_gid: dict[str, dict[str, list[dict]]] = {}
            for row in osap_cur.fetchall():
                gid = str(row["group_id"])
                facet = row["facet"]
                attrs_by_gid.setdefault(gid, {}).setdefault(facet, []).append({
                    "value": row["value"],
                    "position": row["position"],
                })

            # 3. Para cada grupo en Chorus que tenga datos en OSAP
            chorus_groups = chorus.execute("SELECT id FROM groups").fetchall()
            for g in chorus_groups:
                gid = g["id"]
                det = details_by_gid.get(gid)
                attrs = attrs_by_gid.get(gid, {})

                if det is None and not attrs:
                    # Grupo sin datos coral → dejar NULL (no tocar)
                    continue

                # 4. Construir valores
                foundation_date = det["foundation_date"] if det and det.get("foundation_date") else None
                dissolution_date = det["dissolution_date"] if det and det.get("dissolution_date") else None
                locality = det["locality"] if det and det.get("locality") else None
                region = det["region"] if det and det.get("region") else None
                country_code = det["country_code"] if det and det.get("country_code") else None
                venue = det["venue"] if det and det.get("venue") else None
                formation_type = det["formation_type"] if det and det.get("formation_type") else None
                member_count = det["member_count"] if det and det.get("member_count") is not None else None
                public_email = det["public_email"] if det and det.get("public_email") else None

                # language: array de strings (solo value), ordenado por position
                lang_rows = attrs.get("language", [])
                language = json.dumps([r["value"] for r in lang_rows], ensure_ascii=False) if lang_rows else None

                # repertoire: array de objetos {value, position}
                rep_rows = attrs.get("repertoire", [])
                repertoire = json.dumps(rep_rows, ensure_ascii=False) if rep_rows else None

                # venues: desde facet='place', array de objetos {value, position}
                place_rows = attrs.get("place", [])
                venues = json.dumps(place_rows, ensure_ascii=False) if place_rows else None

                # 5. POLÍTICA DE PROTECCIÓN: comprobar valores existentes no-NULL
                existing = chorus.execute(
                    "SELECT foundation_date, dissolution_date, locality, region, country_code, "
                    "venue, formation_type, member_count, public_email, language, repertoire, venues "
                    "FROM groups WHERE id = ?", (gid,)
                ).fetchone()

                # Si YA EXISTE algún valor no-NULL en las nuevas columnas, ABORTAR
                conflict_fields = []
                for field, new_val in [
                    ("foundation_date", foundation_date), ("dissolution_date", dissolution_date),
                    ("locality", locality), ("region", region), ("country_code", country_code),
                    ("venue", venue), ("formation_type", formation_type), ("member_count", member_count),
                    ("public_email", public_email), ("language", language),
                    ("repertoire", repertoire), ("venues", venues),
                ]:
                    existing_val = existing[field] if existing else None
                    if existing_val is not None and existing_val != "":
                        # Ya hay dato en Chorus → no sobrescribir
                        conflict_fields.append(field)

                if conflict_fields:
                    raise RuntimeError(
                        f"Grupo {gid}: migración abortada. "
                        f"Campos con datos existentes en Chorus que se perderían: {conflict_fields}. "
                        f"Revisar manualmente antes de forzar."
                    )

                # 6. UPDATE solo si no hay conflictos
                chorus.execute(
                    "UPDATE groups SET "
                    "foundation_date=?, dissolution_date=?, locality=?, region=?, country_code=?, "
                    "venue=?, formation_type=?, member_count=?, public_email=?, "
                    "language=?, repertoire=?, venues=?, updated_at=? "
                    "WHERE id=?",
                    (
                        foundation_date, dissolution_date, locality, region, country_code,
                        venue, formation_type, member_count, public_email,
                        language, repertoire, venues, utcnow(), gid
                    ),
                )

            chorus.commit()
    finally:
        osap.close()
```

### Puntos clave de la estrategia

| Aspecto | Decisión |
|---------|----------|
| **Orden** | `ORDER BY group_id, facet, position` en la lectura de atributos garantiza orden correcto en arrays JSON |
| **NULL vs []** | Ausencia de registros de origen → `NULL` (no array vacío). Coincide con Lo Rossinyol `repertoire=NULL` y Turo `language=NULL` |
| **Protección** | `UPDATE` solo si **todas** las 12 columnas son `NULL`/`""` en Chorus. Un solo valor existente aborta todo el grupo |
| **Idempotencia** | Si se re-ejecuta, el chequeo de conflicto detecta valores ya migrados y aborta (seguro) |
| **Transacción** | `COMMIT` único al final; `ROLLBACK` si cualquier error |
| **Motor-agnóstica** | Mismo código para MariaDB y SQLite; `db_connect` abstrae la conexión |

---

## 5. Registro de migración (idempotencia real)

La migración **016** se registra en `chorus_schema_migrations` igual que las anteriores:

```python
# En initialise_database (app/main.py) — bloque MySQL
applied = conn.execute(
    "SELECT 1 FROM chorus_schema_migrations WHERE name = ?", ("016_coral_integration",)
).fetchone()
if applied is None:
    conn.executescript((root / "migrations" / "mysql" / "016_coral_integration.sql").read_text("utf-8"))
    conn.execute(
        "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
        ("016_coral_integration", utcnow()),
    )

# Bloque SQLite (lista ordenada)
for name in (
    ...,
    "015_group_articles.sql",
    "016_coral_integration.sql",  # ← AÑADIR AQUÍ
):
    applied = conn.execute(
        "SELECT 1 FROM chorus_schema_migrations WHERE name = ?", (name,)
    ).fetchone()
    if applied is None:
        conn.executescript("BEGIN IMMEDIATE;\n" + (root / "migrations" / "sqlite" / name).read_text("utf-8") + "\nCOMMIT;")
        conn.execute(
            "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
            (name, utcnow()),
        )
```

**Clarificación sobre idempotencia**:
- El **fichero SQL (016)** contiene solo `ALTER TABLE ADD COLUMN`. **No es repetible**: ejecutarlo dos veces falla en la segunda (columna ya existe).
- La **migración de datos (Python)** es la que debe ser idempotente: se ejecuta **una vez** tras aplicar el SQL, y su chequeo de conflictos evita re-ejecución accidental.
- En instalaciones nuevas: `initialise_database` aplica 001→016 en orden, luego se lanza el script Python.
- En instalaciones existentes: se aplica 016 (si no está), luego se lanza el script Python.

---

## 6. API — Conversión JSON explícita (no automática)

**FastAPI/Pydantic NO convierte automáticamente** el texto JSON devuelto por MariaDB (`JSON`) o SQLite (`TEXT`) a listas/objetos Python. Hay que hacerlo en la capa de acceso a datos.

### Dónde realizar la conversión

En `app/main.py`, en las funciones que leen `groups` y devuelven DTOs. Buscar `_group_dto` o equivalente y añadir:

```python
import json

def _parse_json_field(value: str | None) -> list | dict | None:
    if value is None or value == "":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None  # o log + None

def _group_dto(row: sqlite3.Row | dict, role: str, can_manage: bool) -> dict[str, Any]:
    # ... campos existentes ...
    return {
        "id": row["id"],
        "entity_id": row["entity_id"],
        "name": row["name"],
        "timezone": row["timezone"],
        "join_code": row["join_code"],
        "role": role,
        "can_manage": can_manage,
        # NUEVOS CAMPOS CORAL:
        "foundation_date": row["foundation_date"],
        "dissolution_date": row["dissolution_date"],
        "locality": row["locality"],
        "region": row["region"],
        "country_code": row["country_code"],
        "venue": row["venue"],
        "formation_type": row["formation_type"],
        "member_count": row["member_count"],
        "public_email": row["public_email"],
        "language": _parse_json_field(row["language"]),
        "repertoire": _parse_json_field(row["repertoire"]),
        "venues": _parse_json_field(row["venues"]),
    }
```

### Validación en Pydantic (POST/PATCH)

```python
from typing import Annotated
from pydantic import BeforeValidator

def _validate_json_array(value: str | list | None) -> list | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError
            return parsed
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON array")
    if isinstance(value, list):
        return value
    raise ValueError("Expected array or JSON string")

JsonArray = Annotated[list | None, BeforeValidator(_validate_json_array)]

class GroupBody(BaseModel):
    # ... existentes ...
    foundation_date: str | None = Field(default=None, max_length=32)
    dissolution_date: str | None = Field(default=None, max_length=32)
    locality: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=255)
    country_code: str | None = Field(default=None, max_length=2)
    venue: str | None = Field(default=None, max_length=500)
    formation_type: str | None = Field(default=None, max_length=64)
    member_count: int | None = Field(default=None, ge=0)
    public_email: str | None = Field(default=None, max_length=320)
    language: JsonArray = Field(default=None)
    repertoire: JsonArray = Field(default=None)
    venues: JsonArray = Field(default=None)

class GroupUpdateBody(BaseModel):
    # ... existentes ...
    foundation_date: str | None = Field(default=None, max_length=32)
    dissolution_date: str | None = Field(default=None, max_length=32)
    locality: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=255)
    country_code: str | None = Field(default=None, max_length=2)
    venue: str | None = Field(default=None, max_length=500)
    formation_type: str | None = Field(default=None, max_length=64)
    member_count: int | None = Field(default=None, ge=0)
    public_email: str | None = Field(default=None, max_length=320)
    language: JsonArray = Field(default=None)
    repertoire: JsonArray = Field(default=None)
    venues: JsonArray = Field(default=None)
```

### Serialización al guardar (INSERT/UPDATE)

```python
def _dump_json(value: list | dict | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)

# En create_group y update_group:
language = _dump_json(body.language)
repertoire = _dump_json(body.repertoire)
venues = _dump_json(body.venues)

conn.execute(
    "INSERT INTO groups ... (language, repertoire, venues) VALUES (?,?,?)",
    (language, repertoire, venues),
)
```

---

## 7. Pruebas concretas y criterios de aceptación

### 7.1 Pruebas unitarias (SQLite en memoria) — `tests/test_coral_integration.py`

```python
def test_coral_fields_roundtrip(tmp_path, monkeypatch):
    """POST → GET devuelve arrays/objetos Python, no strings JSON."""
    profiles = {"token-rep": _profile("rep-1", representative=True)}
    install_fake_auth(monkeypatch, profiles)
    with TestClient(create_app(_settings(tmp_path))) as client:
        headers = {"Authorization": "Bearer token-rep"}
        # CREATE con todos los campos coral
        payload = {
            "entity_id": "ent-coral-1",
            "name": "Coral Test",
            "foundation_date": "1990-03-15",
            "dissolution_date": None,
            "locality": "Testville",
            "region": "Testonia",
            "country_code": "ES",
            "venue": "Sala Principal",
            "formation_type": "mixed",
            "member_count": 25,
            "public_email": "coral@test.org",
            "language": ["ca", "es"],
            "repertoire": [{"value": "Obra 1", "position": 0}, {"value": "Obra 2", "position": 1}],
            "venues": [{"value": "Sala A", "position": 1}, {"value": "Sala B", "position": 2}],
        }
        resp = client.post("/api/v1/groups", headers=headers, json=payload)
        assert resp.status_code == 201
        group_id = resp.json()["id"]

        # GET → verificar tipos Python
        resp = client.get(f"/api/v1/groups/{group_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["language"], list)
        assert data["language"] == ["ca", "es"]
        assert isinstance(data["repertoire"], list)
        assert data["repertoire"][0]["value"] == "Obra 1"
        assert data["repertoire"][0]["position"] == 0
        assert isinstance(data["venues"], list)
        assert data["venues"][0]["value"] == "Sala A"
        assert data["venues"][0]["position"] == 1

        # PATCH parcial → solo actualiza campos enviados
        resp = client.patch(f"/api/v1/groups/{group_id}", headers=headers, json={
            "member_count": 30,
            "language": ["es"],  # reemplaza array completo
        })
        assert resp.status_code == 200
        resp = client.get(f"/api/v1/groups/{group_id}", headers=headers)
        assert resp.json()["member_count"] == 30
        assert resp.json()["language"] == ["es"]
        assert resp.json()["repertoire"] == [{"value": "Obra 1", "position": 0}, {"value": "Obra 2", "position": 1}]  # intacto
```

### 7.2 Pruebas de validación

| Test | Entrada | Esperado |
|------|---------|----------|
| `language` no es array | `"language": "ca"` | 422 ValidationError |
| `repertoire` elemento sin `position` | `[{"value": "x"}]` | 422 |
| `venues` elemento sin `value` | `[{"position": 1}]` | 422 |
| `country_code` longitud > 2 | `"ESP"` | 422 |
| `member_count` negativo | `-5` | 422 |

### 7.3 Pruebas de migración (integración real)

**Entorno**: MariaDB 10.4.32 real + SQLite (dos ejecuciones separadas).

| Escenario | Verificación |
|-----------|--------------|
| Migración Lo Rossinyol | 12 campos poblados; `repertoire=NULL`; `venues` array con 2 objetos ordenados por position |
| Migración Turo del Vent | 12 campos poblados; `language=NULL`; `repertoire` 2 objetos; `venues` 1 objeto |
| Migración Grupo Prueba | 12 campos = `NULL` |
| Re-ejecución migración | Aborta con error de conflicto (no sobrescribe) |
| Grupo ya con datos en Chorus (simulado) | Aborta y lista campos en conflicto |

### 7.4 Criterios de aceptación globales

1. **GET `/api/v1/groups/{id}`** devuelve `language`, `repertoire`, `venues` como `list`/`None` (nunca `str`).
2. **POST/PATCH** aceptan arrays Python y strings JSON válidos; rechazan inválidos con 422.
3. **Migración Python** ejecuta sin errores en MariaDB 10.4.32 y SQLite 3.45+.
4. **Protección de datos**: ningún valor existente en Chorus se sobrescribe con `NULL` de OSAP.
5. **Orden**: arrays `repertoire` y `venues` conservan el orden `position` de OSAP.
6. **NULL semántico**: ausencia de registros en OSAP → `NULL` en Chorus (no `[]`).

---

## 8. Archivos de Chorus a modificar (identificados por inspección real)

| Archivo | Cambios requeridos |
|---------|-------------------|
| `migrations/mysql/016_coral_integration.sql` | **NUEVO** — 12 `ADD COLUMN` (ver sección 3) |
| `migrations/sqlite/016_coral_integration.sql` | **NUEVO** — 12 `ALTER TABLE ADD COLUMN` (ver sección 3) |
| `app/main.py` | 1. Añadir `"016_coral_integration.sql"` a lista SQLite en `initialise_database`<br>2. Añadir bloque MySQL para `016_coral_integration` en `initialise_database`<br>3. Extender `GroupBody` y `GroupUpdateBody` con 12 campos + validadores JSON<br>4. Añadir `_parse_json_field` y `_dump_json`<br>5. Modificar `_group_dto` para incluir 12 campos con parsing JSON<br>6. Modificar `create_group` y `update_group` para serializar JSON y guardar |
| `app/config.py` | Ninguno (no hay config nueva) |
| `app/db.py` | Ninguno (abstracción ya soporta ambos motores) |
| `scripts/migrate_coral_details.py` | **NUEVO** — Script de migración de datos (ver sección 4) |
| `tests/test_coral_integration.py` | **NUEVO** — Pruebas unitarias (ver sección 7.1) |
| `web/app.js` | Frontend: añadir campos coral en formulario de grupo, vista detalle, validación cliente |
| `web/index.html` | Frontend: inputs para los 12 campos en modal/editor de grupo |

---

## 9. Director musical — Decisión documentada

- **No se crea columna `director` ni tabla `directors`**.
- El rol de director se expresa **exclusivamente** mediante `group_members.musical_role_id = 'director'` (texto libre).
- `'director'` es una **convención provisional**, no una responsabilidad normalizada ni validada.
- `director_label` de OSAP (`Jordi Piccorelli Lopez`, `Emili Fortea`) **no se migra**; queda en OSAP como dato histórico.
- Si en el futuro se normaliza el catálogo de roles musicales, se hará en migración separada.

---

## 10. Ejecución y pruebas — Checklist de verificación

### Instalación nueva (MariaDB)
```bash
# 1. Aplicar esquema (incluye 016 via initialise_database)
CHORUS_DATABASE_URL=mysql+pymysql://osap2027:2027osapdb@127.0.0.1/osap_chorus \
python -c "from app.main import create_app; from app.config import Settings; create_app(Settings.load())"

# 2. Ejecutar migración de datos
OSAP_DATABASE_URL=mysql+pymysql://osap2027:2027osapdb@127.0.0.1/osap_api \
CHORUS_DATABASE_URL=mysql+pymysql://osap2027:2027osapdb@127.0.0.1/osap_chorus \
python scripts/migrate_coral_details.py
```

### Instalación nueva (SQLite)
```bash
# 1. Aplicar esquema (initialise_database aplica 001-016)
python -c "from app.main import create_app; from app.config import Settings; create_app(Settings.load())"

# 2. Ejecutar migración de datos (requiere OSAP_DATABASE_URL accesible)
OSAP_DATABASE_URL=mysql+pymysql://osap2027:2027osapdb@127.0.0.1/osap_api \
python scripts/migrate_coral_details.py
```

### Instalación existente
```bash
# Solo ejecutar migración de datos (el ALTER TABLE ya se aplicó al arrancar la app)
OSAP_DATABASE_URL=... CHORUS_DATABASE_URL=... python scripts/migrate_coral_details.py
```

### Tests automatizados
```bash
# SQLite (rápido, CI)
pytest tests/test_coral_integration.py -v

# MariaDB real (requiere contenedor/servidor)
pytest tests/test_coral_integration.py -v --db-url=mysql+pymysql://...
```

---

## 11. Resumen de correcciones respecto a versiones anteriores

| Punto | Versión anterior | Versión corregida (esta) |
|-------|------------------|--------------------------|
| Número de columnas | 11 / 19 | **12** (lista exacta en sección 1) |
| JSON_ARRAYAGG en MariaDB | Presentado como compatible | **Eliminado** — no existe en 10.4; migración Python |
| json_group_array en SQLite | Presentado como solución | **Eliminado** — no garantiza orden; migración Python |
| Protección sobrescritura | `WHERE EXISTS` insuficiente | **Chequeo previo + abort si conflicto** |
| Idempotencia | Confundida (SQL vs Python) | **Separada**: SQL 016 no repetible; Python idempotente por chequeo |
| NULL vs [] | `repertoire=[]` para Lo Rossinyol | **NULL** (ausencia de registros) |
| Conversión JSON API | Asumida automática | **Explícita** en `_group_dto` y Pydantic validators |
| Director musical | Columna/tabla propuesta | **Excluido**; convención en `musical_role_id` |
| Compatibilidad motores | "Versión admite JSON" | **Probado**: MariaDB 10.4.32 + SQLite JSON1 |

---

**Fin del informe corregido.**

**Próximo paso**: Esperar autorización expresa para proceder a la implementación de los archivos listados en la sección 8.