# Chorus — Auditoría de la cadena de migraciones 016–042 y procedimiento de actualización

**Fecha:** 2026-11-23
**Ámbito:** base de datos de desarrollo `osap_chorus` (MariaDB 10.4.32)
**Estado:** auditoría completada; actualización **no ejecutada**

---

## 1. Resumen ejecutivo

Se ha auditado la cadena de migraciones pendientes y el estado real de la BD de desarrollo. La actualización es **viable y de bajo riesgo**, pero **no se aplica al reiniciar Chorus**: hace falta ejecutarla explícitamente.

| Aspecto | Resultado |
|---|---|
| Migraciones pendientes | **27** (`017`, `016`, `018`–`042`) |
| Volumen de datos | 3 grupos, 2 membresías, 12 secciones, 17 artículos, 16 audiovisuales |
| Filas huérfanas | **0** en todas las comprobaciones |
| Columnas de `groups` que añade 016 | **ninguna preexistente** → aplica limpio |
| Tablas que crearían 016–042 | **ninguna existe todavía** |
| Migraciones destructivas sobre datos | **ninguna** |
| Pérdida de datos esperada | **ninguna** |
| Riesgo residual | Bajo (ver §5) |

**Corrección importante respecto a lo indicado en fases anteriores:** Chorus **no** aplica las migraciones pendientes al arrancar. `initialise_database()` sólo contempla `001` y `004`–`007` (más el reconocimiento del baseline histórico). Las migraciones `016`–`042` no tienen runner automático: hay que aplicarlas con `scripts/upgrade_dev_db.py`.

---

## 2. Estado real de `osap_chorus`

### 2.1 Migraciones registradas (7)

```
001_schema.sql, 004_material_library.sql, 005_material_groups.sql,
006_group_articles_tables.sql, 007_events_series_index.sql,
009_legacy_baseline, mysql_schema_v1
```

### 2.2 Comparación con lo que espera la migración 016

`016_coral_group_fields.sql` añade 12 columnas a `groups` con `ALTER TABLE ... ADD COLUMN` **sin condiciones**.

| Columna que añade 016 | ¿Existe en `osap_chorus`? |
|---|---|
| `foundation_date`, `dissolution_date`, `locality`, `region`, `country_code` | No |
| `venue`, `formation_type`, `member_count`, `public_email` | No |
| `language`, `repertoire`, `venues` | No |

**Conclusión:** 016 aplica sin conflicto sobre este esquema. Las columnas que sí existen en `groups` (`slug`, `kind`, `description`, `image_url`, `website`, `email`, `logo_url`, `status`, `editorial_mode`, `technical_description`) proceden del baseline y de migraciones anteriores; **ninguna** es tocada por 016.

### 2.3 Volumen de datos

| Tabla | Filas |
|---|---|
| `groups` | 3 |
| `group_members` | 2 (1 activo, 1 revocado) |
| `group_sections` | 12 (pertenecen a 1 grupo) |
| `group_articles` | 17 |
| `group_article_media` | 16 |
| `creation_drafts` | 6 |
| `library_items` | 1 |
| `messages` / `message_recipients` | 1 / 1 |
| `works` / `resources` / `files` | **0 / 0 / 0** |

### 2.4 Integridad referencial previa

| Comprobación | Huérfanos |
|---|---|
| `group_members` con grupo inexistente | 0 |
| `group_sections` con grupo inexistente | 0 |
| `group_articles` con grupo inexistente | 0 |
| `group_article_media` con artículo inexistente | 0 |

---

## 3. Auditoría de la cadena 016–042

Se ha revisado cada migración buscando DDL destructivo, transformaciones de datos, dependencias y condicionalidad.

### 3.1 Clasificación

| Tipo | Migraciones | Observaciones |
|---|---|---|
| **Sólo `CREATE TABLE` / índices** | 021, 023, 024, 025, 026, 029, 030, 031, 032, 035, 037, 038, 039 | Sin impacto sobre datos existentes |
| **`ADD COLUMN` condicional** | 019, 020, 022, 036 | Comprueban `information_schema` antes de añadir |
| **`ADD COLUMN` incondicional** | **016**, **033** | Aplican una sola vez; no reejecutables |
| **FKs condicionales** | 017, 018, 027, 034 | Comprueban `REFERENTIAL_CONSTRAINTS` antes de crear/retirar |
| **Modificación no destructiva** | 028 (`group_id` a NULL) | Ya está NULL en dev → inocuo |
| **Migración de datos** | **040**, **041** | Ver §3.3 |
| **DDL destructivo (esquema)** | **034**, **040**, **041**, **042** | Ver §3.4 |
| **DDL destructivo (datos)** | **ninguna** | No hay `DELETE`/`TRUNCATE`/`DROP` de datos |

### 3.2 Puntos que **no** son idempotentes

| Migración | Motivo | Riesgo |
|---|---|---|
| **016** | `ADD COLUMN` sin comprobar existencia | Si falla a medias, la reejecución falla con *Duplicate column* |
| **033** | `ADD COLUMN` + FK + índices sin comprobar | Ídem; además añade columnas que `034` retira inmediatamente |

En una BD limpia ambas aplican bien. El riesgo aparece **sólo** si la migración falla a mitad y se reintenta sin restaurar.

### 3.3 Transformaciones de datos

**040 — `preparation_works.group_id` → `space_id`** (la más delicada):

1. Añade `space_id` NULL si no existe.
2. Crea un `space` por grupo (`INSERT IGNORE ... SELECT g.id, 'group', g.created_by, ...`).
3. `UPDATE preparation_works ... SET space_id = s.id`.
4. **Aborta** si queda algún `space_id IS NULL` (tabla inexistente forzada → error 1146).
5. FK `space_id → spaces(id) ON DELETE RESTRICT`.
6. `space_id NOT NULL`.
7. Elimina FK, índice y columna `group_id`.

En `osap_chorus`: `preparation_works` **no existe** todavía (la crea `035` en la misma cadena, sobre tabla vacía). Por tanto los pasos 2–4 operan sobre **0 filas** y no hay riesgo de pérdida ni de aborto.

**041 — consolidación**: hace `spaces.owner_sub` NULLABLE, lo normaliza a NULL en espacios no personales, resuelve duplicados del espacio general (conserva el más antiguo y reasigna trabajos), añade columna generada e índice único.

**042 — proyectos personales**: preflight que **aborta** si alguna fila no encaja en el nuevo modelo de ownership, y luego sustituye `chk_space_group` por `chk_space_ownership`.

### 3.4 DDL destructivo (sólo esquema)

| Migración | Operación | Impacto en datos |
|---|---|---|
| 034 | `DROP COLUMN group_admin_role_id`, `group_musical_role_id` | **Ninguno**: esas columnas no existen en dev (sólo estaban en instalaciones que pasaron por 033). Además son columnas duplicadas que la API no usa |
| 040 | `DROP COLUMN preparation_works.group_id` | **Ninguno**: los datos ya están migrados a `space_id` |
| 041 | `MODIFY owner_sub NULL`, `ADD COLUMN` generada | Ninguno |
| 042 | `DROP CONSTRAINT chk_space_group`, `ADD chk_space_ownership` | Ninguno: sólo validación |

### 3.5 Dependencias

| Migración | Depende de | Motivo |
|---|---|---|
| 016 | — | Sólo `groups` |
| 017 | 006 | `group_articles` |
| 018 | — | Crea `group_types` |
| 019 | **018** | FK `groups.type_code → group_types(code)` |
| 020 | — | `group_members` |
| 021 | — | FK a `groups` |
| 022 | 006 | `group_articles` |
| 023 | 018 | FK a `group_types` |
| 024 | 018 | FK a `group_types` |
| 025–028 | 001/006 | Tablas base |
| 029 | — | Crea `group_roles` |
| 030–032 | grupos | FKs a `groups` |
| **033** | **029** | FK a `group_roles` |
| 034 | 033 | Retira sus columnas duplicadas |
| 035 | 001 | `works/resources/files` |
| 036 | — | `group_members` |
| 037 | grupos | FK `spaces.group_id` |
| 038 | 001 | FK compuesta `resources(work_id, id)` |
| 039 | 001 | `files` |
| 040 | 035, 037 | Migra y elimina `group_id` |
| 041 | 037, 040 | Consolidación |
| 042 | 037, 041 | Restricción de ownership |

El orden del actualizador (`scripts/upgrade_dev_db.py`) es el mismo que usa `rebuild_test_db.py`: `017` antes que `016` y `007`, y `018` después de `016`. Es el orden ya validado contra `osap_chorus_test`.

---

## 4. Conservación de datos

| Dato | Tras la actualización |
|---|---|
| 3 grupos | Se conservan; cada uno obtiene su espacio general en `spaces` |
| 2 membresías | Se conservan; `033` añade columnas que `034` retira sin tocar `role`, `status`, `section_id`, `admin_role_id`, `musical_role_id` |
| 12 secciones | Se conservan |
| 17 artículos + 16 audiovisuales | Se conservan; `022` añade `scope` con default `'group'` |
| 6 borradores, 1 biblioteca, 1 mensaje | Se conservan |
| Works/Resources/Files | Están vacíos; sin riesgo |

**No hay ninguna migración con `DELETE`, `TRUNCATE` o `UPDATE` destructivo sobre datos existentes.**

---

## 5. Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| 016/033 no idempotentes y fallo a mitad | Baja | Copia previa + restauración documentada; el actualizador aborta sin registrar |
| FK de 034 falla por valores no nulos sin `group_roles` | Baja | Verificado: las 2 filas tienen `admin_role_id` y `musical_role_id` NULL |
| FK compuesta de 038 falla | Baja | `uq_resources_work (work_id, id)` existe desde 001 |
| `group_types` queda vacío | **Alta (funcional)** | Ninguna migración siembra la taxonomía; `groups.type_code` no podrá usarse hasta cargarla (§7) |
| 040 aborta por filas sin migrar | Nula | `preparation_works` se crea vacío |
| 042 aborta por ownership inválido | Nula | 040/041 dejan `owner_sub` NULL y `group_id` NOT NULL en espacios de grupo |

---

## 6. Procedimiento de actualización

### 6.1 Orden de ejecución

```powershell
# 0. Comprobar el estado actual (no modifica nada)
$env:CHORUS_DATABASE_URL="mysql+pymysql://osap2027:2027osapdb@127.0.0.1:3306/osap_chorus"
python scripts/upgrade_dev_db.py --env dev --verify-only

# 1. Simulación (no modifica nada)
python scripts/upgrade_dev_db.py --env dev

# 2. Aplicar (copia de seguridad automática + aplicación + verificación)
python scripts/upgrade_dev_db.py --env dev --apply

# 3. Reiniciar el servicio
.\recompile-chorus.bat
```

### 6.2 Entornos

El actualizador distingue tres destinos y **comprueba la conexión efectiva** (base, usuario y versión del servidor), no el texto de la URL. Si no coincide con el entorno elegido, aborta sin tocar nada.

| Entorno | `--env` | Base | Usuario | Uso |
|---|---|---|---|---|
| Desarrollo | `dev` | `osap_chorus` | `osap2027` | Probar la migración en real |
| Pruebas / CI | `test` | `osap_chorus_test` | `osap2027_test` | Dejar la BD de test con el esquema nuevo |
| Producción | `prod` | a indicar | a indicar | Despliegue, con confirmación expresa |

**Producción** exige, además:

- `--database-url` con la cadena real (no se acepta `CHORUS_DATABASE_URL` por seguridad).
- `--confirm-production`.
- Copia de seguridad obligatoria (no se puede usar `--no-backup`).

```powershell
python scripts/upgrade_dev_db.py --env prod `
    --database-url "mysql+pymysql://USUARIO:CLAVE@HOST:3306/BASE" `
    --backup-to "D:\backups" `
    --apply --confirm-production
```

Orden recomendado de propagación: **dev → test → prod**, validando en cada una antes de pasar a la siguiente.

### 6.3 Qué hace `--apply`

1. **Protección de conexión** sobre la conexión efectiva: base, usuario y MariaDB 10.4 según el entorno; impide cruzar entornos (p. ej. `--env test` contra `osap_chorus`).
2. **Copia de seguridad** con `mysqldump` (`--single-transaction --routines --triggers --events`): esquema + datos. En `prod` es obligatoria.
3. **Preflight**: tablas base, columnas exigidas, volumen de datos y huérfanos. Si hay problemas, **aborta antes de tocar la BD**.
4. **Aplicación** migración a migración, registrando cada una en `chorus_schema_migrations` sólo tras completarse.
5. **Verificación posterior**: esquema final, esquema de spaces/preparación, migraciones registradas y destino real.

Si una migración falla: se revierte la transacción, **no se registra** y el proceso termina indicando que se restaure la copia (el DDL de MariaDB no es transaccional).

### 6.4 Restauración

```powershell
python scripts/upgrade_dev_db.py --env dev --restore "C:\Users\migarcia\AppData\Local\osap-dev\backups\osap_chorus-20261123-120000.sql"
```

En producción, `--restore` también exige `--confirm-production`.

### 6.4 Verificación posterior

```sql
-- Migraciones registradas (deben ser 34)
SELECT COUNT(*) FROM chorus_schema_migrations;

-- Un espacio general por grupo
SELECT s.id, s.space_type, s.owner_sub, s.group_id, g.name
FROM spaces s LEFT JOIN groups g ON g.id = s.group_id
WHERE s.space_type = 'group';

-- Ningún trabajo sin espacio
SELECT COUNT(*) FROM preparation_works pw
LEFT JOIN spaces s ON s.id = pw.space_id WHERE s.id IS NULL;

-- Datos históricos intactos
SELECT (SELECT COUNT(*) FROM groups) AS groups,
       (SELECT COUNT(*) FROM group_members) AS members,
       (SELECT COUNT(*) FROM group_sections) AS sections,
       (SELECT COUNT(*) FROM group_articles) AS articles,
       (SELECT COUNT(*) FROM group_article_media) AS media;
```

---

## 7. Cuestiones pendientes

| # | Cuestión | Impacto |
|---|---|---|
| **Q-01** | **Ninguna migración siembra `group_types`** (018 crea la tabla vacía). La taxonomía de 48 tipos de OSAP no se carga | `groups.type_code` no puede usarse; el selector de tipo quedaría vacío. Requiere decidir la carga (script aparte o seed) |
| **Q-02** | No existe runner genérico de migraciones en la aplicación | Cada actualización futura dependerá de `upgrade_dev_db.py`; conviene valorar integrarlo en `initialise_database` |
| **Q-03** | 016 y 033 no son idempotentes | Si alguna falla a medias, hay que restaurar la copia antes de reintentar |
| **Q-04** | El vhost `chorus` apunta a `127.0.0.1:8123`, sin proceso escuchando | El acceso real es `http://chorus-app`; el vhost `chorus` está obsoleto |

---

## 8. Conclusión

La cadena 016–042 es **segura sobre el esquema actual de `osap_chorus`**: no hay pérdida de datos, no hay huérfanos y las únicas eliminaciones de columnas son duplicados no usados o columnas ya migradas. El punto de atención funcional es la siembra de `group_types` (Q-01), que no bloquea la actualización pero deja la taxonomía vacía.

**La actualización no se ha ejecutado.** El procedimiento está preparado y validado en modo simulación sobre la BD real.