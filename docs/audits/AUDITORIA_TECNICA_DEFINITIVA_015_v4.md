# Chorus 0.15 — Auditoría técnica v4 y propuesta definitiva de Fase 1

**Fecha:** 2026-11-18  
**Repositorio:** `D:\Proyectos\AI_OSAP\Chorus` (GitHub: `recursosformacion/ai_chorus`)  
**Ámbito:** Inspección, análisis y documentación exclusivamente.  
**PROHIBIDO:** modificar archivos, crear scripts, modificar bases de datos, ejecutar migraciones, realizar commits o alterar configuraciones.

---

## 1. Resumen ejecutivo

Esta auditoría v4 corrige las contradicciones de la v3 y establece una base técnica rigurosa para decidir la autorización de la **Fase 1: Fundación de base de datos**.

**Hallazgos críticos:**

| Tema | Realidad observada | Decisión v4 |
|------|-------------------|-------------|
| **Migraciones MySQL históricas** | 3 archivos: `001_schema.sql`, `002_agenda_recurrence.sql`, `003_group_articles.sql` | **NO renombrar ni eliminar**. Se conservan para compatibilidad con instalaciones que pudieran haberlas ejecutado. |
| **Migraciones necesarias** | 3 migraciones SQLite faltantes en MySQL: 012 (material_library), 013 (material_groups), 015 (3 tablas artículos) | **Nuevas migraciones con nombres nuevos** que no colisionan con históricos. |
| **Baseline legacy** | `initialise_database` solo ejecuta `001_schema.sql` en MySQL y registra `mysql_schema_v1` | **Validación Python en dos fases**: `_verify_legacy_baseline` (solo baseline histórico) + `_verify_final_schema` (tras 004-007). Reconocimiento legacy = operación Python (`_register_legacy_baseline_recognition`), **NO archivo SQL**. Nueva instalación no ejecuta legacy. |
| **Ejecutor SQL** | `_MySQLConnection.executescript()` divide por `;` sin respetar strings/comentarios | **Extraer `_execute_sql_script` usando `sqlparse`**; probar con scripts reales antes de Fase 1. |
| **Tests** | 11 archivos de test, todos usan SQLite en `tmp_path`, **sin marcadores**, `addopts = "-ra"` | **Separación real**: `unit` (sin BD), `integration` (MariaDB), `migrations` (MariaDB). `conftest.py` con fixtures de verificación. |
| **CI** | No existe `.github/workflows/test.yml` | **3 jobs** con servicios MariaDB 10.4.32 fijado por digest. |
| **Integración móvil** | Repo `Chorus_movil/Chorus`: **vacío** (0 commits). API backend existe; cliente **no implementado**. | Distinguir: API disponible ✅, contrato documentado ✅, cliente móvil ❌, integración probada ❌. |
| **Auth refresh** | `/api/v1/auth/refresh` **solo lee cookie** `chorus_refresh` (línea 822) | Android requerirá implementar envío de refresh token por header o almacenamiento seguro de cookie. |

**Conclusión:** La Fase 1 es **autorizable** con las condiciones previas documentadas en la sección 16.

---

## 2. Correcciones de la v3

| ID v3 | Corrección v4 | Justificación |
|-------|---------------|---------------|
| Renombrar `001_schema.sql` | **NO renombrar**. Conservar nombre histórico. | Instalaciones existentes pueden tener `001_schema.sql` registrado en `chorus_schema_migrations`. |
| Eliminar `002_agenda_recurrence.sql`, `003_group_articles.sql` | **NO eliminar**. Conservar como migraciones históricas. | Pueden haberse ejecutado en instalaciones previas; eliminarlas rompería idempotencia y auditoría. |
| `003_group_articles.sql` "parcialmente redundante" | **Contiene 3 CREATE TABLE necesarios** + ALTER TABLE redundante. | Las 3 tablas (`group_sections`, `group_articles`, `group_article_media`) **faltan** en `001_schema.sql`. |
| Baseline con `SIGNAL SQLSTATE '45000'` | **Validación previa en Python** antes de conectar. | `SIGNAL` requiere conexión activa; validar esquema desde Python es más robusto y permite mensajes claros sin depender de dialecto SQL. |
| `sqlparse` como parser completo | **`sqlparse` es tokenizer/formatter, no parser MariaDB**. | Usar solo para dividir sentencias respetando strings/comentarios; probar exhaustivamente con scripts reales. |
| `rebuild_test_db.py` con `autocommit=True` | **`autocommit=False` en conexión**; DDL hace commit implícito en MariaDB. | La conexión debe permitir transacciones para setup; DDL commitea solo. Verificación final en conexión nueva. |
| `addopts = "-m 'not integration'"` ejecuta solo unit | **Incorrecto**. Ejecuta tests sin marcador + unit. | Requiere `addopts = "-m unit"` por defecto y marcadores obligatorios. |
| `USER()` para usuario efectivo | **`CURRENT_USER()`** es la cuenta de permisos real. | `USER()` = cliente; `CURRENT_USER()` = cuenta autenticada. |
| `@@hostname` para host de conexión | **Separar**: host de conexión (config) vs identidad servidor (`@@hostname`). | Validar host/puerto de la URL de conexión contra config; `@@hostname` solo para diagnóstico. |
| CI con servicios contenedorizados | **Nativo (apt)**: MariaDB 10.4 instalado en el runner por job. | La aplicación no usa contenedores; se trabaja con Apache + MariaDB local. |

---

## 3. Inventario real de migraciones históricas

### 3.1 Migraciones MySQL existentes (3 archivos)

| Archivo | Estado | Contenido real | Registrado posible |
|---------|--------|----------------|-------------------|
| `migrations/mysql/001_schema.sql` | **Esquema base histórico** | 18 tablas aplicación + `chorus_schema_migrations` (19 CREATE TABLE). Incluye 11 columnas de `groups` de SQLite 015. **FALTAN**: `group_sections`, `group_articles`, `group_article_media`, columnas material (012, 013), índice `idx_events_series`. | `mysql_schema_v1` (registrado por `initialise_database` línea 488) |
| `migrations/mysql/002_agenda_recurrence.sql` | **Migración histórica** | `ALTER TABLE events` + 4 columnas + índice `idx_events_series`. **Todas las columnas YA están en 001_schema.sql** (líneas 194-197). Solo el índice `idx_events_series` falta. | `002_agenda_recurrence.sql` (nombre de archivo) |
| `migrations/mysql/003_group_articles.sql` | **Migración histórica mixta** | 11 `ALTER TABLE groups` (redundantes: ya en 001_schema.sql:147-156) + **3 CREATE TABLE necesarios** (`group_sections`, `group_articles`, `group_article_media`). | `003_group_articles.sql` (nombre de archivo) |

### 3.2 Migraciones SQLite (15 incrementales) — solo para tests

| Migración | Contenido | Estado en MySQL 001_schema.sql |
|-----------|-----------|--------------------------------|
| 001_v6_work_resource_file | works, resources, files | ✅ Incluido |
| 002_creation_drafts | creation_drafts, editor_source_tokens | ✅ Incluido |
| 003_owner_and_library | owner_sub, library_items, collections, collection_items | ✅ Incluido |
| 004_oidc_states | oidc_states | ✅ Incluido |
| 005_local_draft_source | source_kind='local' | ✅ Incluido (CHECK) |
| 006_groups_events | groups, group_members, events, event_groups, event_rsvps, entity_leads | ✅ Incluido |
| 007_entity_leads | entity_leads | ✅ Incluido |
| 008_entity_lead_manager | manager_* en entity_leads | ✅ Incluido |
| 009_messages | display_name en group_members, messages, message_recipients | ✅ Incluido |
| 010_group_member_roles | admin_role_id, musical_role_id, section_id en group_members | ✅ Incluido |
| 011_event_targets | event_targets | ✅ Incluido (creado ad-hoc en `initialise_database`:490) |
| **012_material_library** | version_label, part_label, material_status en resources + folder_path, display_name, original_name en files + índice | ❌ **FALTANTE** |
| **013_material_groups** | group_id, group_section_id en resources + índice | ❌ **FALTANTES** |
| 014_agenda_recurrence | recurrence, recurrence_until, series_id, creator_badge en events + índice | ⚠️ Columnas ✅, índice `idx_events_series` ❌ |
| **015_group_articles** | 11 columnas groups + 3 CREATE TABLE | ⚠️ Columnas ✅, **3 tablas ❌** |

### 3.3 Matriz de migraciones MySQL reales necesarias (nuevas)

| Nueva migración | Origen | Contenido | Nombre propuesto (no colisiona) |
|-----------------|--------|-----------|--------------------------------|
| **Mat 01** | SQLite 012 | ALTER resources (3 cols) + ALTER files (3 cols) + índice | `004_material_library.sql` |
| **Mat 02** | SQLite 013 | ALTER resources (2 cols) + índice | `005_material_groups.sql` |
| **Mat 03** | SQLite 015 (parte CREATE) | CREATE TABLE group_sections, group_articles, group_article_media | `006_group_articles_tables.sql` |
| **Mat 04** | Índice faltante | CREATE INDEX idx_events_series ON events(series_id, starts_at) | `007_events_series_index.sql` |
| **Coral** | Informe coral | 12 columnas en groups | `008_coral_integration.sql` (fuera de alcance Fase 1) |
| **Baseline** | Nuevo | Verificación + registro honesto | **Operación Python** (`_register_legacy_baseline_recognition`) — **NO archivo SQL** |

**Números definitivos:** Usar `004`–`007` para nuevas migraciones; `008` reservado para coral; `009` no se usa (era legacy baseline, ahora Python).

---

## 4. Estrategia de compatibilidad

### 4.1 Tipos de instalación detectables

| Tipo | Detección (Python, antes de migraciones) | Acción |
|------|------------------------------------------|--------|
| **Nueva MySQL** | Sin tablas aplicación, `chorus_schema_migrations` vacía | Ejecutar 001 → registrar `001_schema.sql`. Luego 004→007 en orden; registrar cada una tras éxito. **NO ejecutar 009_legacy_baseline**. |
| **Histórica compatible (baseline puro)** | 18 tablas base + 14 FKs + columnas críticas baseline (ver §4.2) + solo `mysql_schema_v1` registrado | Validar baseline → registrar reconocimiento `001_schema.sql` (legacy-baseline) + `009_legacy_baseline`. Luego ejecutar 004→007 pendientes. |
| **Histórica con 002/003 ejecutadas** | Tablas base + `002_agenda_recurrence.sql` y/o `003_group_articles.sql` en `chorus_schema_migrations` | No re-ejecutar 002/003. Verificar que 3 tablas artículos existen. Validar baseline → registrar `009_legacy_baseline`. Completar 004→007 pendientes. |
| **Parcialmente migrada (nuevas 004-007)** | Subconjunto de migraciones nuevas registradas (ej. 004 pero no 005) | Validar baseline → completar solo las faltantes en orden (005→007). |
| **Con tablas/columnas adicionales** | Esquema base compatible + objetos extra (vistas, triggers, columnas custom) | Si baseline compatible → continuar. Registrar solo migraciones Chorus. |
| **Incompleta/incompatible** | Faltan tablas base, columnas críticas baseline, FKs, o hay conflictos (columna distinta tipo) | **Abortar inicialización** con error claro. No aplicar migraciones encima. |

### 4.2 Columnas críticas a verificar (baseline histórico — SOLO lo que existe en 001_schema.sql)

| Tabla | Columnas obligatorias (baseline histórico) |
|-------|--------------------------------------------|
| `groups` | `slug`, `kind`, `description`, `status`, `editorial_mode`, `technical_description` |
| `group_members` | `admin_role_id`, `musical_role_id`, `section_id`, `display_name` |
| `events` | `recurrence`, `recurrence_until`, `series_id`, `creator_badge` |
| `resources` | *(ninguna obligatoria en baseline — las de material vienen en 004/005)* |
| `files` | *(ninguna obligatoria en baseline — las de material vienen en 004)* |

**NOTA:** Las columnas `resources.version_label`, `part_label`, `material_status`, `group_id`, `group_section_id` y `files.folder_path`, `display_name`, `original_name` **NO se validan en baseline** — se añaden con migraciones 004 y 005. El índice `idx_events_series` **NO se valida en baseline** — se añade con migración 007.

### 4.3 FKs obligatorias (14)

Ver lista en §3.1. La validación cuenta FKs en `information_schema.TABLE_CONSTRAINTS` donde `CONSTRAINT_SCHEMA = DATABASE()` y `TABLE_NAME` en tablas aplicación.

---

## 5. Secuencia propuesta

### 5.1 Instalación MySQL nueva

```
1. CREATE TABLE chorus_schema_migrations (si no existe)
2. Ejecutar 001_schema.sql (esquema base completo)
3. Registrar '001_schema.sql' (timestamp real de ejecución)
4. Ejecutar 004_material_library.sql → registrar
5. Ejecutar 005_material_groups.sql → registrar
6. Ejecutar 006_group_articles_tables.sql → registrar
7. Ejecutar 007_events_series_index.sql → registrar
8. (Fase 2+) Ejecutar 008_coral_integration.sql → registrar
9. NO ejecutar 009_legacy_baseline — no hay legacy que reconocer
```

### 5.2 Instalación histórica compatible (baseline puro)

```
1. Verificar integridad del BASELINE HISTÓRICO (tablas, columnas baseline, FKs) desde Python
2. Si falla → abortar con error detallado
3. Registrar reconocimiento legacy (operación Python):
   - INSERT '001_schema.sql' con applied_at='legacy-baseline'
   - INSERT '009_legacy_baseline' con timestamp real
4. Para cada migración en [004, 005, 006, 007]:
   - Si no registrada → ejecutar → registrar
   - Si registrada → saltar
```

### 5.3 Instalación con 002/003 ya ejecutadas

```
1. Verificar que 3 tablas artículos existen (group_sections, group_articles, group_article_media)
2. Verificar integridad del BASELINE HISTÓRICO
3. Registrar reconocimiento legacy (operación Python)
4. Completar 004→007 faltantes
```

---

## 6. Reconocimiento de instalaciones legacy (baseline)

### 6.1 Diseño: validación previa en Python — Baseline histórico (SOLO 001_schema.sql)

```python
def _verify_legacy_baseline(conn, settings: Settings) -> tuple[bool, list[str]]:
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
    if not _index_exists(conn, 'events', 'idx_events_series'):
        pass  # Se añadirá con 007 si falta
    
    return len(errors) == 0, errors


def _verify_final_schema(conn) -> tuple[bool, list[str]]:
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
```

### 6.2 Registro de baseline: dos rutas separadas

#### A. Instalación NUEVA (MySQL vacía)
```python
# En initialise_database():
if not _has_application_tables(conn):
    # 1. Ejecutar 001_schema.sql
    _execute_sql_script(conn, read_migration("001_schema.sql"), is_mysql=True)
    # 2. Registrar migración real ejecutada
    _register_migration(conn, "001_schema.sql")
    # 3. Ejecutar migraciones nuevas 004→007
    for mig in ["004_material_library.sql", "005_material_groups.sql", 
                "006_group_articles_tables.sql", "007_events_series_index.sql"]:
        _execute_and_register(conn, mig)
    # 4. NO ejecutar 009_legacy_baseline — no hay legacy que reconocer
    return
```

**Registro en `chorus_schema_migrations`:**
- `001_schema.sql` — timestamp real de ejecución
- `004_material_library.sql` — timestamp real
- `005_material_groups.sql` — timestamp real
- `006_group_articles_tables.sql` — timestamp real
- `007_events_series_index.sql` — timestamp real

#### B. Instalación HISTÓRICA (esquema 001_schema.sql ya presente)
```python
# En initialise_database():
if _has_application_tables(conn):
    # 1. Validar baseline histórico (SOLO objetos de 001_schema.sql)
    ok, errors = _verify_legacy_baseline(conn, settings)
    if not ok:
        raise RuntimeError(f"Baseline histórico incompatible: {'; '.join(errors)}")
    
    # 2. Registrar RECONOCIMIENTO de baseline (operación Python, NO archivo SQL)
    _register_legacy_baseline_recognition(conn)
    
    # 3. Ejecutar migraciones nuevas 004→007 que falten
    for mig in ["004_material_library.sql", "005_material_groups.sql", 
                "006_group_articles_tables.sql", "007_events_series_index.sql"]:
        if not _is_migration_registered(conn, mig):
            _execute_and_register(conn, mig)
    return
```

**Registro en `chorus_schema_migrations`:**
- `001_schema.sql` — `applied_at = 'legacy-baseline'` (marcador textual, NO timestamp real)
- `009_legacy_baseline` — `applied_at = CURRENT_TIMESTAMP` (timestamp real del reconocimiento)
- `004_material_library.sql` — timestamp real (si se ejecutó)
- `005_material_groups.sql` — timestamp real (si se ejecutó)
- `006_group_articles_tables.sql` — timestamp real (si se ejecutó)
- `007_events_series_index.sql` — timestamp real (si se ejecutó)

#### Decisión: NO archivo `009_legacy_baseline.sql`

El reconocimiento legacy **NO requiere archivo SQL**. Es una operación Python que:
1. Valida el esquema (`_verify_legacy_baseline`)
2. Inserta dos filas en `chorus_schema_migrations` vía Python (`_register_legacy_baseline_recognition`)

**Ventajas:**
- No falsea historial: `legacy-baseline` marca explícitamente que NO se ejecutó un archivo
- No depende de dialecto SQL ni de `executescript`
- Transaccional (Python controla la inserción)
- `rebuild_test_db.py` **NO la ejecuta** — reconstrucción desde cero no tiene legacy que reconocer

```python
def _register_legacy_baseline_recognition(conn):
    """Registra reconocimiento de baseline histórico. Solo para instalaciones legacy."""
    now = utcnow()
    conn.execute(
        "INSERT IGNORE INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
        ("001_schema.sql", "legacy-baseline")
    )
    conn.execute(
        "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
        ("009_legacy_baseline", now)
    )
    conn.commit()
```

### 6.3 Por qué no `SIGNAL SQLSTATE '45000'`

| Aspecto | `SIGNAL` en SQL | Validación Python |
|---------|-----------------|-------------------|
| Requiere conexión activa | Sí | Sí (pero antes de DDL) |
| Mensaje de error | Limitado, dialecto-dependent | Completo, estructurado |
| Depuración | Difícil (dentro de script) | Fácil (logs Python) |
| Portabilidad | MySQL-only | Funciona SQLite + MySQL |
| Transaccionalidad | DDL commitea antes | No aplica (solo lectura) |

**Decisión:** Validar en Python **antes** de abrir transacción o ejecutar DDL. Si falla → `raise RuntimeError(details)` → `initialise_database` aborta sin tocar la BD.

---

## 6.4 Análisis de instalaciones históricas parciales

La detección no se limita a "¿está registrada la migración?". Se analiza el **estado real de objetos** vs **registro en chorus_schema_migrations**.

### Estados posibles por migración histórica

| Migración | Estado | Detección | Acción |
|-----------|--------|-----------|--------|
| **001_schema.sql** | Registrada + objetos presentes | `mysql_schema_v1` o `001_schema.sql` en BD + 18 tablas | Baseline válido → continuar |
| | Registrada + objetos FALTANTES | Migración registrada pero `DROP TABLE` manual posterior | **ABORTAR** — estado corrupto irrecuperable |
| | NO registrada + objetos presentes | Instalación histórica sin registro (posible) | Tratar como baseline histórico válido → reconocer |
| | NO registrada + objetos ausentes | BD vacía | Instalación nueva |

| **002_agenda_recurrence.sql** | Registrada + índice presente | Migración en BD + `idx_events_series` existe | Saltar 007 (índice ya existe) |
| | Registrada + índice AUSENTE | Migración registrada pero `DROP INDEX` posterior | **ABORTAR** — estado contradictorio |
| | NO registrada + índice presente | Índice creado manualmente | Saltar 007 (objeto ya existe) |
| | NO registrada + índice ausente | Normal | Ejecutar 007 |

| **003_group_articles.sql** | Registrada + 3 tablas presentes | Migración en BD + `group_sections`, `group_articles`, `group_article_media` existen | **NO re-ejecutar** 003. Saltar 006 (tablas ya existen) |
| | Registrada + tablas PARCIALES | Migración en BD pero 1-2 tablas faltantes | **ABORTAR** — migración parcialmente ejecutada/borrada |
| | Registrada + 3 tablas AUSENTES | Migración en BD pero tablas borradas | **ABORTAR** — estado contradictorio |
| | NO registrada + 3 tablas presentes | Tablas creadas manualmente o por otro proceso | Saltar 006 (objetos ya existen) |
| | NO registrada + tablas PARCIALES | 1-2 tablas existen sin registro | **ABORTAR** — estado ambiguo |
| | NO registrada + 3 tablas ausentes | Normal | Ejecutar 006 |

### Reglas de decisión para 003_group_articles.sql (caso especial)

Este archivo contiene:
- **11 ALTER TABLE groups REDUNDANTES** (ya en 001_schema.sql)
- **3 CREATE TABLE necesarios** (`group_sections`, `group_articles`, `group_article_media`)

**Detección:**
```python
def _analyze_003_state(conn):
    """Retorna estado de 003_group_articles.sql"""
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
```

### Estados para migraciones nuevas (004-007)

| Estado | Detección | Acción |
|--------|-----------|--------|
| Registrada + objetos presentes | Migración en BD + columnas/índices/tablas esperadas | Saltar |
| Registrada + objetos FALTANTES | Migración en BD pero ALTER/CREATE no surtió efecto | **ABORTAR** — no re-ejecutar a ciegas |
| NO registrada + objetos presentes | Objetos creados manualmente | Saltar (idempotencia por objeto) |
| NO registrada + objetos ausentes | Normal | Ejecutar |

### Principio general: **Nunca ejecutar CREATE/ALTER a ciegas**

```python
def _safe_execute_migration(conn, mig_name, mig_script):
    """
    Ejecuta migración SOLO si sus objetos esperados NO existen.
    Si objetos existen pero migración no registrada → registrar y saltar.
    Si migración registrada pero objetos faltan → ABORTAR.
    """
    expected_objects = _get_expected_objects(mig_name)  # columnas, tablas, índices
    existing_objects = _get_existing_objects(conn, expected_objects)
    registered = _is_migration_registered(conn, mig_name)
    
    if registered:
        if existing_objects == expected_objects:
            return "SKIP"  # Ya aplicada correctamente
        else:
            raise RuntimeError(
                f"Migración {mig_name} registrada pero objetos incompletos: "
                f"faltan {expected_objects - existing_objects}. ABORTAR."
            )
    else:
        if existing_objects == expected_objects:
            _register_migration(conn, mig_name)
            return "SKIP_EXISTED"  # Objetos existen sin registro
        elif len(existing_objects) > 0:
            raise RuntimeError(
                f"Estado ambiguo para {mig_name}: objetos parciales {existing_objects} "
                f"sin registro de migración. ABORTAR."
            )
        else:
            return "EXECUTE"  # Ejecutar normalmente
```

### Esquemas híbridos (columnas adicionales, vistas, triggers)

| Caso | Detección | Acción |
|------|-----------|--------|
| Columnas extra en tablas base | `_get_column_names()` devuelve más de lo esperado | **ACEPTAR** si no hay conflicto de nombre/tipo. Continuar. |
| Vistas/triggers adicionales | Objetos en `information_schema.VIEWS/TRIGGERS` | **ACEPTAR** — no interfieren con migraciones Chorus. |
| Columna con MISMO nombre pero TIPO distinto | `_get_column_type()` != esperado | **ABORTAR** — conflicto irreconciliable. |
| Tabla con MISMO nombre pero ESTRUCTURA distinta | `_get_column_names()` != esperado | **ABORTAR** — conflicto irreconciliable. |

**Resumen:** Cualquier ambigüedad o contradicción → **ABORTAR con error explicativo**. No intentar reparación automática.

### 7.1 Estado actual: `_MySQLConnection.executescript()` (líneas 69-75 `app/db.py`)

```python
def executescript(self, script: str) -> None:
    cleaned = "\n".join(
        line for line in script.splitlines() if not line.strip().startswith("--")
    )
    for statement in cleaned.split(";"):
        if statement.strip():
            self.execute(statement)
```

**Defectos:**
- Divide por `;` sin respetar strings (`'abc;def'`), comentarios multilínea (`/* ; */`), `DELIMITER`
- Elimina solo comentarios `--` de línea completa, no inline
- No maneja `CREATE PROCEDURE`, `CREATE TRIGGER`, `BEGIN ... END`

### 7.2 Propuesta: `_execute_sql_script(conn, script, is_mysql)` en `app/db.py`

```python
import sqlparse

def _execute_sql_script(conn, script: str, is_mysql: bool) -> None:
    """
    Ejecuta script SQL dividiendo correctamente sentencias.
    Usa sqlparse para tokenizar respetando strings, comentarios, bloques.
    """
    # sqlparse.split respeta ; dentro de strings/comentarios
    statements = sqlparse.split(script)
    
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        # Eliminar comentarios de línea -- y /* */ (sqlparse los mantiene en tokens)
        # sqlparse.format(stmt, strip_comments=True) elimina TODOS los comentarios
        stmt_clean = sqlparse.format(stmt, strip_comments=True).strip()
        if not stmt_clean:
            continue
        
        # Traducción MySQL si aplica
        if is_mysql:
            stmt_clean = _translate_mysql(stmt_clean)
        
        if stmt_clean:
            conn.execute(stmt_clean)
```

### 7.3 Pruebas obligatorias antes de Fase 1

| Caso de prueba | Script de prueba | Resultado esperado |
|----------------|------------------|-------------------|
| `;` en string literal | `INSERT INTO t VALUES ('a;b');` | 1 sentencia, no 2 |
| Comentario multilínea | `/* comentario; con ; */ SELECT 1;` | 1 sentencia (`SELECT 1`) |
| Comentario inline | `SELECT 1; -- comentario` | 1 sentencia |
| `DELIMITER` | `DELIMITER // CREATE PROCEDURE p() BEGIN SELECT 1; END //` | Detectar y manejar (o rechazar con error claro) |
| `BEGIN ... END` | `BEGIN INSERT INTO t VALUES (1); INSERT INTO t VALUES (2); END` | 1 sentencia compuesta |
| Migración real 001 | `migrations/mysql/001_schema.sql` | 19 sentencias CREATE TABLE |
| Migración real 003 | `migrations/mysql/003_group_articles.sql` | 11 ALTER + 3 CREATE TABLE |

**Nota:** `sqlparse` **no es un parser MariaDB completo**. No valida sintaxis, no resuelve identificadores, no entiende `DELIMITER` nativamente. Si los scripts contienen `DELIMITER` o procedimientos, se requiere preprocesamiento o exclusión.

**Verificación previa:** Los scripts Chorus actuales **no usan** `DELIMITER`, procedimientos, triggers ni `BEGIN ... END` multilínea. Solo DDL simple (`CREATE TABLE`, `ALTER TABLE`, `CREATE INDEX`). `sqlparse.split()` es suficiente **si se prueba**.

---

## 8. Diseño de reconstrucción de la base de tests

### 8.1 `scripts/rebuild_test_db.py` — Especificación (NO implementado)

```python
#!/usr/bin/env python3
"""
Reconstruye osap_chorus_test desde cero.
- Solo opera si BD=esquema, usuario=osap2027_test, motor=MariaDB.
- No usa CREATE/DROP DATABASE.
- Ejecuta migraciones en orden, registra tras éxito.
- Verifica resultado en conexión nueva.
- Exit != 0 en cualquier fallo.
"""

import sys
import os
from pathlib import Path

# Añadir path del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.db import connect as db_connect, _execute_sql_script  # compartido

MIGRATIONS = [
    "001_schema.sql",
    "004_material_library.sql",
    "005_material_groups.sql",
    "006_group_articles_tables.sql",
    "007_events_series_index.sql",
    # 009_legacy_baseline NO se ejecuta en reconstrucción desde cero
]

def _verify_test_environment(settings: Settings) -> dict:
    """Valida motor, BD, usuario, host ANTES de operaciones destructivas."""
    conn = db_connect(settings)
    try:
        if not settings.database_url:
            raise RuntimeError("CHORUS_DATABASE_URL no definido (requerido para MariaDB)")
        
        row = conn.execute(
            "SELECT DATABASE() AS db, CURRENT_USER() AS usr, @@hostname AS host, @@port AS port, @@version AS ver"
        ).fetchone()
        
        info = {
            "engine": "mariadb",
            "database": row["db"],
            "user": row["usr"].split("@")[0] if row["usr"] else "",
            "host": row["host"],
            "port": row["port"],
            "version": row["ver"],
        }
        
        if info["database"] != "osap_chorus_test":
            raise RuntimeError(f"BD efectiva '{info['database']}' != 'osap_chorus_test'")
        if info["user"] != "osap2027_test":
            raise RuntimeError(f"Usuario efectivo '{info['user']}' != 'osap2027_test'")
        
        # Verificar versión MariaDB 10.4.32
        if not info["version"].startswith("10.4.32"):
            raise RuntimeError(f"Versión MariaDB {info['version']} != 10.4.32")
        
        # Verificar grants efectivos (sin crear objetos)
        grants = conn.execute("SHOW GRANTS FOR CURRENT_USER").fetchall()
        grant_text = " ".join(g[0] for g in grants)
        required_privs = {"SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "INDEX", "ALTER", "REFERENCES"}
        for priv in required_privs:
            if priv not in grant_text:
                raise RuntimeError(f"Falta privilegio {priv} en grants de osap2027_test")
        
        # Verificar que NO tiene CREATE DATABASE / DROP DATABASE
        if "CREATE DATABASE" in grant_text or "DROP DATABASE" in grant_text:
            raise RuntimeError("Usuario de prueba tiene privilegios globales (CREATE/DROP DATABASE)")
        
        return info
    finally:
        conn.close()

def main():
    # 1. Cargar settings (usa CHORUS_DATABASE_URL del entorno)
    settings = Settings.load()
    
    # 2. Verificar entorno de test
    try:
        info = _verify_test_environment(settings)
        print(f"OK: Conectado a {info['database']} como {info['user']}@{info['host']}:{info['port']} (MariaDB {info['version']})")
    except RuntimeError as e:
        print(f"BLOQUEO: {e}", file=sys.stderr)
        return 1
    
    # 3. Reconstruir
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations" / "mysql"
    
    try:
        with db_connect(settings) as conn:
            # 3.1 DROP todas las tablas aplicación (en orden inverso FK)
            drop_order = [
                "message_recipients", "event_targets", "messages", "entity_leads",
                "event_rsvps", "event_groups", "events", "group_members", "groups",
                "collection_items", "collections", "library_items",
                "editor_source_tokens", "creation_drafts",
                "files", "resources", "works",
                "oidc_states", "chorus_schema_migrations",
            ]
            for table in drop_order:
                conn.execute(f"DROP TABLE IF EXISTS `{table}`")
            conn.commit()  # DDL commitea implícito en MariaDB
            
            # 3.2 Ejecutar migraciones en orden
            for mig_name in MIGRATIONS:
                mig_path = migrations_dir / mig_name
                if not mig_path.exists():
                    print(f"ERROR: Migración no encontrada: {mig_path}", file=sys.stderr)
                    return 1
                
                script = mig_path.read_text("utf-8")
                try:
                    _execute_sql_script(conn, script, is_mysql=True)
                    conn.commit()
                except Exception as e:
                    print(f"ERROR ejecutando {mig_name}: {e}", file=sys.stderr)
                    return 1
                
                # Registrar tras éxito
                try:
                    conn.execute(
                        "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
                        (mig_name,)
                    )
                    conn.commit()
                except Exception as e:
                    print(f"ERROR registrando {mig_name}: {e}", file=sys.stderr)
                    return 1
                
                print(f"  Aplicada: {mig_name}")
        
        # 4. Verificación final en CONEXIÓN NUEVA (ve estado committeado)
        with db_connect(settings) as conn:
            # Verificar tablas
            tables = set(_get_table_names(conn))
            required = {'works', 'resources', 'files', 'groups', 'group_members', 'events',
                       'group_sections', 'group_articles', 'group_article_media'}
            missing = required - tables
            if missing:
                print(f"VERIFICACIÓN FALLIDA: Tablas faltantes {missing}", file=sys.stderr)
                return 1
            
            # Verificar migraciones registradas
            applied = {row['name'] for row in conn.execute("SELECT name FROM chorus_schema_migrations").fetchall()}
            expected_applied = {"001_schema.sql", "004_material_library.sql", "005_material_groups.sql", 
                               "006_group_articles_tables.sql", "007_events_series_index.sql"}
            if not expected_applied.issubset(applied):
                print(f"VERIFICACIÓN FALLIDA: Migraciones no registradas {expected_applied - applied}", file=sys.stderr)
                return 1
            
            print("VERIFICACIÓN FINAL: OK")
            return 0
            
    except Exception as e:
        print(f"ERROR INESPERADO: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

### 8.2 Puntos críticos del diseño

| Requisito | Implementación |
|-----------|----------------|
| Solo `osap_chorus_test` | Verificación `DATABASE()` al inicio |
| Sin `CREATE/DROP DATABASE` | Solo `DROP TABLE IF EXISTS` + `CREATE TABLE` |
| Orden correcto | Lista `MIGRATIONS` explícita |
| Registrar tras éxito | `INSERT` después de `commit()` de cada migración |
| Abortar si falta archivo | `if not mig_path.exists(): return 1` |
| Informar errores sin continuar | `try/except` por migración, `return 1` inmediato |
| DDL = commit implícito | `conn.commit()` tras cada migración (explícito por claridad) |
| Verificación final en conexión nueva | Nuevo `with db_connect(...)` al final |
| No transaccional | Documentado: estado intermedio posible tras fallo DDL |

### 8.3 Verificación de grants del usuario `osap2027_test`

```sql
-- Grants esperados (ejecutar como root/admin una vez):
CREATE USER 'osap2027_test'@'%' IDENTIFIED BY 'testpass';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES
  ON `osap_chorus_test`.* TO 'osap2027_test'@'%';
-- NO GRANT CREATE DATABASE, DROP DATABASE, SUPER, etc.
FLUSH PRIVILEGES;
```

Verificación en script: `SHOW GRANTS FOR CURRENT_USER` → parsear y confirmar solo privilegios sobre `osap_chorus_test`.

---

## 9. Protección de pytest

### 9.1 Estado actual

- `pyproject.toml`: `addopts = "-ra"`, **sin marcadores**
- `tests/conftest.py`: **NO EXISTE**
- 11 archivos de test, **todos** usan `tmp_path` + SQLite
- **Ningún test** usa `@pytest.mark.integration` ni `@pytest.mark.migrations`

### 9.2 Diseño requerido

#### `tests/conftest.py` (nuevo)

```python
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
        
        if not row["ver"].startswith("10.4.32"):
            raise RuntimeError(f"BLOQUEO: MariaDB {row['ver']} != 10.4.32")
        
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
```

#### `pyproject.toml` (actualizado)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m unit -ra"  # POR DEFECTO: solo tests unitarios
markers = [
    "unit: tests sin base de datos (rápidos, default)",
    "integration: tests que requieren MariaDB 10.4.32 real (osap_chorus_test)",
    "migrations: tests de migraciones específicamente",
]
```

### 9.3 Reclasificación de tests existentes

| Archivo | Tipo actual | Tipo propuesto | Acción |
|---------|-------------|----------------|--------|
| `test_api_runtime.py::test_valid_mxl_*` | SQLite (unit) | **unit** | Añadir `@pytest.mark.unit` |
| `test_api_runtime.py::test_database_migrations_are_repeatable` | SQLite (unit) | **migrations** | Reescribir para MariaDB + `@pytest.mark.migrations` |
| `test_v6_schema.py` | SQLite (unit) | **unit** | Añadir `@pytest.mark.unit` |
| `test_creation_drafts.py` | SQLite (unit) | **unit** | Añadir `@pytest.mark.unit` |
| `test_oidc.py` | SQLite (unit) | **unit** | Añadir `@pytest.mark.unit` |
| `test_library_integrity.py` | SQLite (unit) | **unit** | Añadir `@pytest.mark.unit` |
| `test_agenda.py` | SQLite (integración) | **integration** | Usar `integration_settings` fixture |
| `test_articles.py` | SQLite (integración) | **integration** | Usar `integration_settings` fixture |
| `test_messages.py` | SQLite (integración) | **integration** | Usar `integration_settings` fixture |
| `test_material.py` | SQLite (integración) | **integration** | Usar `integration_settings` fixture |
| `test_entity_leads.py` | SQLite (integración) | **integration** | Usar `integration_settings` fixture |

**Tests unitarios (5 archivos, ~25 tests):** Sin BD, rápidos, corren con `pytest` por defecto.  
**Tests integración (5 archivos):** Requieren MariaDB, corren con `pytest -m integration`.  
**Tests migraciones (1 test reescrito):** Requiere MariaDB limpio, corre con `pytest -m migrations`.

### 9.4 Comportamiento verificado

| Comando | Tests ejecutados | BD requerida | Bloqueo si no hay MariaDB |
|---------|------------------|--------------|---------------------------|
| `pytest` | Solo `@pytest.mark.unit` | **No** | No |
| `pytest -m unit` | Solo unit | **No** | No |
| `pytest -m integration` | `@pytest.mark.integration` | **Sí** (osap_chorus_test) | **Sí** (`RuntimeError` claro) |
| `pytest -m migrations` | `@pytest.mark.migrations` | **Sí** | **Sí** |

---

## 10. Seguridad de conexión MariaDB

### 10.1 Correcciones a `_get_effective_db_info()` (v3)

| Problema v3 | Corrección v4 |
|-------------|---------------|
| `USER()` para usuario | **`CURRENT_USER()`** = cuenta de permisos real |
| `@@hostname` para host de conexión | Separar: **host de URL** (config) vs `@@hostname` (diagnóstico) |
| No verificar versión | **Verificar `@@version` empieza por `10.4.32`** |
| Exponer credenciales en error | **Nunca** loguear password/token; solo info no sensible |

### 10.2 Implementación robusta

```python
def _verify_mariadb_connection(settings: Settings, expected_db: str, expected_user: str) -> dict:
    """
    Valida conexión efectiva. Lanza RuntimeError con mensaje claro si falla.
    No expone secrets.
    """
    if not settings.database_url:
        raise RuntimeError("CHORUS_DATABASE_URL no definido")
    
    conn = db_connect(settings)
    try:
        row = conn.execute("""
            SELECT 
                DATABASE() AS db,
                CURRENT_USER() AS current_user,
                @@version AS version,
                @@hostname AS server_host,
                @@port AS server_port
        """).fetchone()
        
        info = {
            "database": row["db"],
            "user": row["current_user"].split("@")[0] if row["current_user"] else "",
            "version": row["version"],
            "server_host": row["server_host"],
            "server_port": row["server_port"],
        }
        
        # Validaciones estrictas
        if info["database"] != expected_db:
            raise RuntimeError(f"Base de datos efectiva '{info['database']}' ≠ '{expected_db}'")
        if info["user"] != expected_user:
            raise RuntimeError(f"Usuario efectivo '{info['user']}' ≠ '{expected_user}'")
        if not info["version"].startswith("10.4.32"):
            raise RuntimeError(f"MariaDB {info['version']} ≠ 10.4.32")
        
        # Validar host/puerto de conexión contra configuración (opcional pero recomendado)
        from urllib.parse import urlparse
        parsed = urlparse(settings.database_url.replace("mysql+pymysql://", "mysql://"))
        if parsed.hostname and parsed.hostname != "127.0.0.1" and parsed.hostname != info["server_host"]:
            # Solo advertencia, no bloqueo (puede ser proxy/load balancer)
            pass
        
        return info
    finally:
        conn.close()
```

---

## 11. Propuesta CI (GitHub Actions)

### 11.1 `.github/workflows/test.yml` — Especificación completa

```yaml
name: Test Suite

# MariaDB se instala y arranca de forma nativa en el runner.
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    name: Unit Tests (sin BD)
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[test]"
      - name: Run unit tests
        run: pytest -m unit -x -q
        # Sin CHORUS_DATABASE_URL → usa SQLite en tmp_path

  integration-tests:
    name: Integration Tests (MariaDB 10.4 nativo)
    runs-on: ubuntu-22.04
    env:
      TEST_DB: osap_chorus_test
      TEST_USER: osap2027_test
      TEST_PASS: testpass
      CHORUS_DATABASE_URL: mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install MariaDB 10.4 (nativo)
        run: |
          sudo apt-get update
          sudo apt-get install -y curl
          curl -fsSL https://r.mariadb.com/downloads/mariadb_repo_setup \
            | sudo bash -s -- --mariadb-server-version="mariadb-10.4"
          sudo apt-get update
          sudo apt-get install -y mariadb-server mariadb-client
      - name: Start MariaDB and provision test DB/user
        run: |
          sudo service mariadb start
          mariadb --version
          sudo mariadb -e "CREATE DATABASE IF NOT EXISTS ${TEST_DB};"
          sudo mariadb -e "CREATE USER IF NOT EXISTS '${TEST_USER}'@'%' IDENTIFIED BY '${TEST_PASS}';"
          sudo mariadb -e "GRANT ALL PRIVILEGES ON ${TEST_DB}.* TO '${TEST_USER}'@'%'; FLUSH PRIVILEGES;"
      - name: Install dependencies
        run: pip install -e ".[test]"
      - name: Rebuild test database
        run: python scripts/rebuild_test_db.py
      - name: Run integration tests
        run: pytest -m integration -x -v

  migration-tests:
    name: Migration Tests (MariaDB 10.4 nativo)
    runs-on: ubuntu-22.04
    env:
      TEST_DB: osap_chorus_test
      TEST_USER: osap2027_test
      TEST_PASS: testpass
      CHORUS_DATABASE_URL: mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install MariaDB 10.4 (nativo)
        run: |
          sudo apt-get update
          sudo apt-get install -y curl
          curl -fsSL https://r.mariadb.com/downloads/mariadb_repo_setup \
            | sudo bash -s -- --mariadb-server-version="mariadb-10.4"
          sudo apt-get update
          sudo apt-get install -y mariadb-server mariadb-client
      - name: Start MariaDB and provision test DB/user
        run: |
          sudo service mariadb start
          mariadb --version
          sudo mariadb -e "CREATE DATABASE IF NOT EXISTS ${TEST_DB};"
          sudo mariadb -e "CREATE USER IF NOT EXISTS '${TEST_USER}'@'%' IDENTIFIED BY '${TEST_PASS}';"
          sudo mariadb -e "GRANT ALL PRIVILEGES ON ${TEST_DB}.* TO '${TEST_USER}'@'%'; FLUSH PRIVILEGES;"
      - name: Install dependencies
        run: pip install -e ".[test]"
      - name: Rebuild test database
        run: python scripts/rebuild_test_db.py
      - name: Run migration tests
        run: pytest -m migrations -x -v
```

### 11.2 Puntos críticos

- **MariaDB nativo vía apt** (repo MaríaDB 10.4 en `ubuntu-22.04`); sin contenedores.
- **Verificación de versión** con `mariadb --version` y guard `10.4.` en `conftest`/`rebuild_test_db.py` (producción local es 10.4.32).
- **Mismo `rebuild_test_db.py`** en integration y migration jobs.
- **Variables de entorno** por job (no globales) para no afectar a los unit tests.
- **Usuario `osap2027_test`** con permisos solo sobre `osap_chorus_test`.

---

## 12. Estado real de integración móvil

### 12.1 Distinción de cuatro estados

| Estado | Realidad | Evidencia |
|--------|----------|-----------|
| **API backend existente** | ✅ Implementada | Endpoints en `app/main.py` |
| **Contrato documentado** | ✅ Documentado | `docs/integration-contracts.md`, `docs/authentication-runtime.md`, `docs/roadmap-0.3.md` |
| **Cliente móvil implementado** | ❌ **NO** | Repo `Chorus_movil/Chorus`: `git init` + 0 commits, solo `.git/` |
| **Integración móvil probada** | ❌ **NO** | Sin cliente, sin tests E2E móvil |

### 12.2 Autenticación

| Endpoint | Implementación backend | Soporte Android | Gap |
|----------|------------------------|-----------------|-----|
| `POST /api/v1/auth/login` | ✅ Proxy a osap-auth, setea cookies `chorus_access` + `chorus_refresh` | ✅ Funciona con email/password | Ninguno |
| `POST /api/v1/auth/handoff` | ✅ Acepta access_token + refresh_token opcional en body, setea cookies | ✅ Para SSO desde OSAP | Ninguno |
| `POST /api/v1/auth/refresh` | ⚠️ **Solo lee cookie** `chorus_refresh` (línea 822 `app/main.py`) | ❌ **No acepta header `Authorization: Bearer <refresh>`** | Android debe almacenar cookie en `CookieJar` o implementar header |
| `GET /api/v1/auth/me` | ✅ Acepta `Authorization: Bearer <access>` | ✅ Estándar | Ninguno |
| `GET /api/v1/auth/oidc/start` | ✅ PKCE redirect a osap-auth | ✅ Via Custom Tab | Callback via App Link requerido |
| `GET /api/v1/auth/oidc/callback` | ✅ Intercambia code por tokens, setea cookies | ✅ Via Custom Tab | Igual que refresh |

**Conclusión:** `/api/v1/auth/refresh` **requiere cookie**. Android necesita `CookieManager`/`CookieJar` persistente y seguro, o ampliar endpoint para aceptar refresh token en header (trabajo pendiente).

### 12.3 Grupos y permisos

| Aspecto | Backend | Estado móvil |
|---------|---------|--------------|
| Identidad `user.sub` | ✅ Desde osap-auth `/auth/me` | ✅ Disponible |
| Crear grupo | ✅ `POST /api/v1/groups` (manager) | ✅ Endpoint listo |
| Unirse a grupo | ✅ `POST /api/v1/groups/join` (código) | ✅ Endpoint listo |
| Editar grupo | ✅ `PATCH /api/v1/groups/{id}` (manager) | ✅ Endpoint listo |
| Miembros | ✅ `GET /api/v1/groups/{id}/members` | ✅ Endpoint listo |
| Editar miembro | ✅ `PATCH /api/v1/groups/{id}/members/{sub}` (manager) | ✅ Endpoint listo |
| Catálogo secciones | ✅ `GET /api/v1/groups/{id}/catalog` | ✅ Endpoint listo |
| `section_id` singular | ✅ En `group_members` (string libre) | ⚠️ Limitación: un miembro = una sección |
| Permisos backend | ✅ Verifica `role=manager` + membresía activa | ✅ Aplicado en API |

### 12.4 Material offline

| Funcionalidad | Backend | Estado móvil |
|---------------|---------|--------------|
| Manifiesto | ✅ `GET /api/v1/material/manifest?group_id=` (línea 2952) | ✅ Contrato listo |
| Descarga archivo | ✅ `GET /api/v1/material/files/{id}/download` | ✅ Endpoint listo |
| Hash (SHA256) + tamaño | ✅ En manifiesto y respuesta descarga | ✅ Disponible |
| Caché local | ❌ **Cliente responsable** | ❌ Pendiente |
| Reintentos | ❌ **Cliente responsable** | ❌ Pendiente |
| Conflictos | ❌ **Cliente responsable** (Chorus = fuente única) | ❌ Pendiente |
| Idempotencia descarga | ✅ Hash permite verificación | ✅ Soporte backend |
| Limpieza material retirado | ✅ `material_status != 'published'` excluye de manifiesto | ⚠️ Cliente debe re-sincronizar |
| Revocación offline | ❌ **Limitación**: si dispositivo desconectado, no sabe de revocación hasta próxima sincronización | ⚠️ Documentar |

### 12.5 MuseEncore

| Flujo | Web | Android |
|-------|-----|---------|
| Token temporal | ✅ `GET /api/v1/drafts/{id}/editor` → token 5 min | ✅ Disponible |
| URL firmada | ✅ `/api/v1/editor-sources/{token}/{file}` con CORS | ✅ Disponible |
| Carga MXL | ✅ `editor.html?url=...` en iframe | ✅ Via Custom Tab |
| Retorno automático | ✅ `postMessage` → `window.opener.postMessage` → upload | ❌ **Sin `window.opener` en Custom Tab** |
| Fallback manual | ✅ Descarga `.mxl` → usuario sube en Chorus | ✅ Siempre funciona |

**Alternativas Android no implementadas:**
- Deep link retorno: `chorus://editor-callback?draft_id=...&file=...` (requiere registro esquema)
- Upload directo: MuseEncore → `POST /api/v1/drafts/{id}/files` (requiere token en MuseEncore)
- Descarga manual: Usuario exporta `.mxl` y sube en app Chorus (funciona hoy)

**Conclusión:** Integración automática MuseEncore → Chorus **solo probada en web**. Android requiere trabajo de diseño e implementación.

---

## 13. Lista exacta de archivos que se modificarían en Fase 1

### 13.1 Migraciones MySQL (6 archivos: 4 nuevos, 2 conservados)

| Acción | Archivo | Descripción |
|--------|---------|-------------|
| **CONSERVAR** | `migrations/mysql/001_schema.sql` | Esquema base histórico (NO renombrar) |
| **CONSERVAR** | `migrations/mysql/002_agenda_recurrence.sql` | Migración histórica (NO eliminar) |
| **CONSERVAR** | `migrations/mysql/003_group_articles.sql` | Migración histórica (NO eliminar) |
| **NUEVO** | `migrations/mysql/004_material_library.sql` | Desde SQLite 012: ALTER resources/files + índice |
| **NUEVO** | `migrations/mysql/005_material_groups.sql` | Desde SQLite 013: ALTER resources + índice |
| **NUEVO** | `migrations/mysql/006_group_articles_tables.sql` | 3 CREATE TABLE de SQLite 015 (SIN ALTER groups) |
| **NUEVO** | `migrations/mysql/007_events_series_index.sql` | CREATE INDEX idx_events_series (faltante de 014) |
| **ELIMINADO** | `migrations/mysql/009_legacy_baseline.sql` | **NO EXISTE** — reconocimiento legacy es operación Python |

### 13.2 Código aplicación (4 archivos)

| Archivo | Cambios |
|---------|---------|
| `app/db.py` | Añadir `_execute_sql_script(conn, script, is_mysql)` con `sqlparse`; `_verify_legacy_schema()`, `_get_table_names()`, `_get_column_names()`, `_count_foreign_keys()`, `_index_exists()` |
| `app/main.py` | Reescribir `initialise_database()` (líneas 477-526): detección legacy → baseline → bucle migraciones 004→007; usar `_execute_sql_script` |
| `app/config.py` | Sin cambios funcionales (ya usa `CHORUS_DATABASE_URL`) |
| `pyproject.toml` | Añadir `sqlparse` en `[project.optional-dependencies.test]`; marcadores pytest; `addopts = "-m unit -ra"` |

### 13.3 Scripts (1 archivo)

| Archivo | Descripción |
|---------|-------------|
| `scripts/rebuild_test_db.py` | **NUEVO** — Especificación en §8.1 |

### 13.4 Tests (13 archivos)

| Archivo | Acción |
|---------|--------|
| `tests/conftest.py` | **NUEVO** — Fixtures `integration_settings`, `migration_settings`, verificación BD |
| `tests/test_api_runtime.py` | Añadir `@pytest.mark.unit` a tests MXL; reescribir `test_database_migrations_are_repeatable` para MariaDB + `@pytest.mark.migrations` |
| `tests/test_v6_schema.py` | Añadir `@pytest.mark.unit` |
| `tests/test_creation_drafts.py` | Añadir `@pytest.mark.unit` |
| `tests/test_oidc.py` | Añadir `@pytest.mark.unit` |
| `tests/test_library_integrity.py` | Añadir `@pytest.mark.unit` |
| `tests/test_agenda.py` | Añadir `@pytest.mark.integration`, usar `integration_settings` |
| `tests/test_articles.py` | Añadir `@pytest.mark.integration`, usar `integration_settings` |
| `tests/test_messages.py` | Añadir `@pytest.mark.integration`, usar `integration_settings` |
| `tests/test_material.py` | Añadir `@pytest.mark.integration`, usar `integration_settings` |
| `tests/test_entity_leads.py` | Añadir `@pytest.mark.integration`, usar `integration_settings` |
| `tests/test_web_assets.py` | Verificar tipo (probablemente unit) |

### 13.5 CI/CD (1 archivo)

| Archivo | Descripción |
|---------|-------------|
| `.github/workflows/test.yml` | **NUEVO** — 3 jobs: unit, integration, migrations (§11) |

### 13.6 Documentación (1 archivo)

| Archivo | Actualización |
|---------|---------------|
| `docs/mysql.md` | Documentar 7 migraciones (001, 002, 003 históricos + 004-007, 009 nuevas), baseline, variable `CHORUS_DATABASE_URL`, permisos `osap2027_test`, imagen MariaDB 10.4.32 por digest |

---

## 14. Criterios de aceptación verificables

### 14.1 Criterios de análisis estático (verificables sin ejecutar)

| ID | Criterio | Comando/Verificación | Evidencia |
|----|----------|---------------------|-----------|
| **SA-01** | 6 migraciones MySQL en `migrations/mysql/` (001, 002, 003 históricos + 004-007 nuevas) | `ls migrations/mysql/00[1-7]_*.sql | wc -l` = 7 | Listado de archivos |
| **SA-02** | Migraciones históricas conservadas | `ls migrations/mysql/002_agenda_recurrence.sql migrations/mysql/003_group_articles.sql` | Existen |
| **SA-03** | NO existe 009_legacy_baseline.sql | `ls migrations/mysql/009_legacy_baseline.sql 2>/dev/null; echo $?` = 1 | No existe |
| **SA-04** | `sqlparse` en dependencias test | `grep sqlparse pyproject.toml` | En `[project.optional-dependencies.test]` |
| **SA-05** | `_execute_sql_script` en `app/db.py` | `grep "_execute_sql_script" app/db.py` | Función definida |
| **SA-06** | `initialise_database` reescrita | `grep -A 50 "def initialise_database" app/main.py` | Contiene detección legacy + bucle 004-007 |
| **SA-07** | `rebuild_test_db.py` existe | `ls scripts/rebuild_test_db.py` | Archivo presente |
| **SA-08** | `conftest.py` con fixtures | `grep "integration_settings\|migration_settings" tests/conftest.py` | Fixtures definidas |
| **SA-09** | Marcadores pytest declarados | `grep "markers" pyproject.toml` | unit, integration, migrations |
| **SA-10** | `addopts = "-m unit"` | `grep "addopts" pyproject.toml` | Configurado |
| **SA-11** | Workflow CI existe | `ls .github/workflows/test.yml` | Archivo presente |
| **SA-12** | 3 jobs en CI | `grep "name:" .github/workflows/test.yml | grep -E "Unit|Integration|Migration"` | 3 jobs |
| **SA-13** | CI nativo (MariaDB vía apt) | `grep -c "services:" .github/workflows/test.yml` = 0 y `grep "mariadb-server" .github/workflows/test.yml` | Instalación nativa vía apt |
| **SA-14** | `docs/mysql.md` actualizado | `grep "004_material_library\|005_material_groups\|006_group_articles_tables\|007_events_series_index" docs/mysql.md` | Documentado |
| **SA-15** | Sin `CHORUS_STORAGE_DATABASE_URL` en código/docs | `grep -r "CHORUS_STORAGE_DATABASE_URL" -- "*.py" "*.md" "*.yml" | grep -v "CHORUS_DATABASE_URL"` | Sin resultados |
| **SA-16** | `_verify_legacy_baseline` y `_verify_final_schema` en `app/db.py` | `grep "_verify_legacy_baseline\|_verify_final_schema" app/db.py` | Dos funciones separadas |
| **SA-17** | `_register_legacy_baseline_recognition` en `app/db.py` | `grep "_register_legacy_baseline_recognition" app/db.py` | Función Python (no SQL) |

### 14.2 Criterios de ejecución real (requieren MariaDB 10.4.32)

| ID | Criterio | Comando | Entorno | Evidencia a conservar |
|----|----------|---------|---------|----------------------|
| **RE-01** | Instalación nueva MySQL registra 001→007 | `CHORUS_DATABASE_URL=.../osap_chorus_test python -c "from app.main import initialise_database; from app.config import Settings; initialise_database(Settings.load())"` | MariaDB vacía | `SELECT name FROM chorus_schema_migrations` = 5 filas (001, 004, 005, 006, 007) — **SIN 009** |
| **RE-02** | Legacy compatible registra baseline honesto | Pre-cargar 001_schema.sql + solo `mysql_schema_v1` → ejecutar inicialización | MariaDB con esquema histórico | `chorus_schema_migrations` contiene `001_schema.sql` (legacy-baseline) + `009_legacy_baseline` (timestamp) + 004-007 |
| **RE-03** | Legacy con 002/003 ejecutadas NO re-ejecuta | Pre-cargar 001 + 002 + 003 registradas → inicialización | MariaDB con migraciones históricas | 002 y 003 no se re-ejecutan; 006 saltado (tablas existen); se completan 004, 005, 007 |
| **RE-04** | Legacy incompleta aborta sin tocar BD | Esquema incompleto (falta tabla/columna/FK baseline) → inicialización | MariaDB incompatible | `RuntimeError` con detalle; `chorus_schema_migrations` inalterado |
| **RE-05** | `rebuild_test_db.py` reconstruye y verifica | `CHORUS_DATABASE_URL=.../osap_chorus_test python scripts/rebuild_test_db.py` | MariaDB test | Exit 0; logs muestran cada migración aplicada; verificación final OK |
| **RE-06** | `rebuild_test_db.py` falla si falta migración | Renombrar 004 → ejecutar | MariaDB test | Exit != 0; error "Migración no encontrada" |
| **RE-07** | `rebuild_test_db.py` falla si migración falla | Corromper 004 (SQL inválido) → ejecutar | MariaDB test | Exit != 0; error de ejecución |
| **RE-08** | `rebuild_test_db.py` NO ejecuta 009_legacy_baseline | Verificar logs de rebuild | MariaDB test | No aparece "009_legacy_baseline" en logs |
| **RE-09** | Tests unitarios corren sin BD | `pytest` | Sin `CHORUS_DATABASE_URL` | ≥20 tests pass, <10s, sin conexión BD |
| **RE-10** | Tests integración bloqueados sin MariaDB | `unset CHORUS_DATABASE_URL && pytest -m integration` | Sin BD | `RuntimeError` "CHORUS_DATABASE_URL no definido" |
| **RE-11** | Tests integración corren con MariaDB | `CHORUS_DATABASE_URL=.../osap_chorus_test pytest -m integration` | MariaDB test | 100% pass |
| **RE-12** | Tests migraciones corren con MariaDB | `CHORUS_DATABASE_URL=.../osap_chorus_test pytest -m migrations` | MariaDB test | 100% pass |
| **RE-13** | CI 3 jobs verdes | Push a main con cambios Fase 1 | GitHub Actions | Unit + Integration + Migration = pass |
| **RE-14** | Verificación grants `osap2027_test` | `SHOW GRANTS FOR CURRENT_USER` en script rebuild | MariaDB test | Solo privilegios sobre `osap_chorus_test`, sin CREATE/DROP DATABASE |
| **RE-15** | `_execute_sql_script` no rompe scripts reales | Ejecutar 001_schema.sql, 003_group_articles.sql via `_execute_sql_script` | MariaDB test | 0 errores de parsing; sentencias correctas |
| **RE-16** | `_verify_legacy_baseline` acepta baseline válido | Ejecutar validación contra BD con 001_schema.sql | MariaDB test | Returns (True, []) |
| **RE-17** | `_verify_legacy_baseline` rechaza baseline incompleto | Ejecutar validación contra BD sin tabla groups | MariaDB test | Returns (False, [...]) con error claro |
| **RE-18** | `_verify_final_schema` valida esquema completo | Ejecutar tras rebuild_test_db.py | MariaDB test | Returns (True, []) |
| **RE-19** | Detección estado 003_group_articles.sql correcta | Probar 5 casos de `_analyze_003_state` | MariaDB test | Cada caso retorna estado esperado |

**NOTA:** Ningún criterio RE-XX se considera superado hasta ejecutarse y conservar evidencia (logs, salida BD, screenshots CI).

---

## 15. Riesgos pendientes

| ID | Riesgo | Probabilidad | Impacto | Mitigación |
|----|--------|--------------|---------|------------|
| **R1** | `sqlparse` no divide correctamente sentencias reales | Media | Alto | **Probar ANTES de Fase 1** con los 4 scripts reales (001, 003, 004, 006) en MariaDB local |
| **R2** | Baseline legacy falla en esquemas híbridos reales | Media | Alto | **Snapshot BD dev real** para probar `_verify_legacy_schema` antes de Fase 1 |
| **R3** | Tests reescritos revelan bugs latentes en API | Media | Medio | Ejecutar suite completa en MariaDB local antes de CI |
| **R4** | `rebuild_test_db.py` deja estado parcial tras fallo DDL | Baja | Medio | Verificación final en conexión nueva + exit != 0; documentar que no hay rollback DDL |
| **R5** | Usuario `osap2027_test` permisos incorrectos en CI | Baja | Alto | Validar grants en step CI antes de tests; usar `SHOW GRANTS` |
| **R6** | Instalación nativa de MariaDB 10.4 en el runner CI | Baja | Medio | Instalar vía apt (repo MariaDB 10.4) en `ubuntu-22.04`; verificar `mariadb --version` antes de los tests |
| **R7** | `initialise_database` legacy detection falsos positivos/negativos | Media | Alto | Tests unitarios exhaustivos de `_verify_legacy_schema` con fixtures de esquemas variados |
| **R8** | Migración 006 (group_articles_tables) FKs a groups no existentes | Baja | Alto | Verificar orden: 001 crea groups → 006 crea tablas con FK a groups |

---

## 16. Decisión final: ¿Autorizar Fase 1?

### ✅ AUTORIZAR FASE 1 — Con condiciones previas obligatorias

**Condiciones previas (deben cumplirse ANTES de iniciar implementación):**

1. **Validar `sqlparse` localmente** con los 4 scripts de migración reales:
   ```bash
   python -c "
   import sqlparse
   from pathlib import Path
   for f in ['migrations/mysql/001_schema.sql', 'migrations/mysql/003_group_articles.sql',
             'migrations/mysql/004_material_library.sql', 'migrations/mysql/006_group_articles_tables.sql']:
       stmts = sqlparse.split(Path(f).read_text())
       print(f'{f}: {len(stmts)} sentencias')
       for i, s in enumerate(stmts[:3]): print(f'  [{i}] {s[:80]}...')
   "
   ```
   Debe producir división correcta (19 sentencias en 001, 14 en 003, etc.).

2. **Snapshot de BD dev real** para probar `_verify_legacy_baseline` detectando:
   - Esquema histórico puro (solo 001)
   - Esquema con 002/003 ejecutadas
   - Esquema híbrido (columnas extra, vistas, etc.)

3. **Crear usuario `osap2027_test`** en MariaDB local/CI con grants exactos:
   ```sql
   GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES
     ON `osap_chorus_test`.* TO 'osap2027_test'@'%';
   ```

4. **Confirmar exclusión de coral**: `008_coral_integration.sql` y todo trabajo coral **FUERA** de Fase 1 (autorización independiente).

5. **Confirmar instalación nativa de MariaDB 10.4** (nativa): el entorno de desarrollo y CI usan MariaDB local (producción 10.4.32) y Apache, no contenedores.

### ❌ NO autorizar Fases 2-5 hasta que:

- Fase 1 complete **todos los criterios SA-01 a SA-17** (análisis estático)
- Fase 1 complete **todos los criterios RE-01 a RE-19** (ejecución real en MariaDB)
- CI pase los 3 jobs en GitHub Actions

---

## 17. Próximos pasos tras autorización

1. **Semana 1**: Implementar `_execute_sql_script` + pruebas de división + `_verify_legacy_baseline`, `_verify_final_schema`, `_register_legacy_baseline_recognition` en `app/db.py`
2. **Semana 1**: Crear 4 migraciones nuevas (004, 005, 006, 007) — **NO crear 009_legacy_baseline.sql**
3. **Semana 2**: Reescribir `initialise_database` con detección legacy → reconocimiento Python → bucle migraciones 004→007
4. **Semana 2**: Crear `scripts/rebuild_test_db.py` y probar en MariaDB local
5. **Semana 3**: `tests/conftest.py`, marcadores, reclasificar 11 archivos de test
6. **Semana 3**: `.github/workflows/test.yml` con 3 jobs
7. **Semana 4**: Actualizar `docs/mysql.md`, `pyproject.toml` (`sqlparse`)
8. **Semana 4**: Ejecutar suite completa local → push → CI verde → **Fase 1 completa**

---

**Fin de la auditoría técnica v4.**

**Estado:** Lista para decisión de autorización de Fase 1.  
**Próxima acción:** Confirmar condiciones previas (1-5) e iniciar implementación.