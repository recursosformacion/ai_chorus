# Tablas nuevas del traslado OSAP → Chorus (plan AutoFree)

Documentación de los endpoints de las tablas creadas por las migraciones 029-032 y del
estado de la clasificación de `performances` (026). El plan de trabajo original está en
[PLAN.md](PLAN.md); aquí se documenta lo que está implementado y verificado.

## Permisos

Todos los endpoints exigen sesión (`current_profile`) y comprueban en servidor:

| Perfil | Cómo se identifica |
| ------ | ------------------ |
| Admin global | `roles` incluye `admin` en el perfil de osap-auth |
| Gestor de grupo | `group_members.role = 'manager'` y `status = 'active'` |
| Miembro | `group_members` activo con cualquier rol |
| Externo | sin vínculo con el grupo |

Los controles viven solo en el backend; la web no decide permisos.

## `group_roles` — cargos de grupo (`CRUD`)

Base: `/api/v1/groups/{group_id}/roles`

| Método | Ruta | Permiso | Descripción |
| ------ | ---- | ------- | ----------- |
| GET | `/roles` | Miembro+ | Lista cargos. Filtros `?scope=admin\|musical&active=true` |
| GET | `/roles/{role_id}` | Miembro+ | Detalle |
| POST | `/roles` | Gestor/Admin | Alta (`scope`, `code`, `name`, `parent_id`, `sort_order`, `active`) |
| PATCH | `/roles/{role_id}` | Gestor/Admin | Edición parcial |
| DELETE | `/roles/{role_id}` | Gestor/Admin | Borrado; `400` si tiene subcargos o está asignado a miembros |

Errores: `404` grupo/cargo inexistente, `403` sin permiso, `400` jerarquía inválida
(`parent_id` de otro grupo, auto-referencia, cargo con hijos o asignado).

## `group_social_links` — enlaces del grupo (`CRUD`)

Base: `/api/v1/groups/{group_id}/social-links`

| Método | Ruta | Permiso |
| ------ | ---- | ------- |
| GET | `/social-links` | Miembro+ |
| GET | `/social-links/{link_id}` | Miembro+ |
| POST | `/social-links` | Gestor/Admin |
| PATCH | `/social-links/{link_id}` | Gestor/Admin |
| DELETE | `/social-links/{link_id}` | Gestor/Admin |

`kind` ∈ `instagram`, `facebook`, `twitter`, `youtube`, `website`, `other`. Orden por
`position`, `id`.

## `legacy_uploads` — subidas heredadas (solo lectura)

| Método | Ruta | Permiso |
| ------ | ---- | ------- |
| GET | `/api/v1/groups/{group_id}/legacy-uploads?mime_type=&limit=&offset=` | Gestor/Admin |
| GET | `/api/v1/legacy-uploads/{upload_id}` | Gestor del grupo o Admin |

`legacy_file_id` es el `file_id` original de `amigos_uploads` (BIGINT); `chorus_file_id`
queda para cuando exista equivalencia con `files.id`. No se inventan equivalencias.

## `activity_log` — auditoría (solo lectura)

| Método | Ruta | Permiso |
| ------ | ---- | ------- |
| GET | `/api/v1/groups/{group_id}/activity-log?event_type=&actor=&article_id=&date_from=&date_to=&limit=&offset=` | Gestor/Admin |
| GET | `/api/v1/admin/activity-log?group_id=&event_type=&actor=&article_id=&date_from=&date_to=&limit=&offset=` | Admin |

Escritura: solo el sistema, desde los flujos existentes (alta de miembro, cambio de rol,
publicación y retirada de artículos). No hay endpoint de escritura.

## `performances` — actuaciones (etapa 1: lectura y participación)

`performances` viene de `amigos_actuaciones` (migración 026) y **no** forma parte de la
agenda: `events` cubre ensayos/citas internas y `performances` los conciertos y
actuaciones públicas. Clasificación aplicada: **recurso público con control editorial**.

| Método | Ruta | Permiso | Descripción |
| ------ | ---- | ------- | ----------- |
| GET | `/api/v1/performances` | Sesión | Lista visible. Filtros `group_id`, `kind`, `modality`, `date_from`, `date_to`, `q`, `limit` (1-200), `offset` |
| GET | `/api/v1/performances/{id}` | Sesión | Detalle |
| GET | `/api/v1/groups/{group_id}/performances` | Miembro+ | Actuaciones del grupo; `?include_drafts=true` solo para gestor/admin |
| GET | `/api/v1/groups/{group_id}/performances/candidates` | Gestor/Admin | Actuaciones sin vincular al grupo |
| POST | `/api/v1/groups/{group_id}/performances/{id}` | Gestor/Admin | Vincula (`role` ∈ `participant`, `organizer`, `guest`); `409` si ya está vinculada |
| DELETE | `/api/v1/groups/{group_id}/performances/{id}` | Gestor/Admin | Desvincula; `404` si no existía la participación |

Reglas de visibilidad:

- `editorial_status = 'published'`: visible para cualquier usuario con sesión.
- Cualquier otro estado: solo admin global o miembro activo de un grupo participante.
- `?group_id=` restringe el resultado a la participación de ese grupo y exige ser
  miembro (o admin); `403` si no lo es, `404` si el grupo no existe.
- El DTO no expone datos internos (`source_email`, `source_note`, `weight`, contadores
  internos).

Pendiente (etapa 2): alta/edición/borrado editorial de actuaciones, publicación y
retirada, métricas y detalle de programa. Requiere decidir si la autoría es de Chorus o
de OSAP y aplicar la regla de versionado A.B.C del ecosistema.

## Verificación

```powershell
$env:CHORUS_DATABASE_URL='mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'
python -m pytest tests -q -m "not unit"        # 71 tests (MariaDB 10.4.32 real)
python -m pytest tests/test_performances.py -q -m "not unit"
```

Estado 2026-11-20: `71 passed, 11 deselected` (248 s), incluidos
`test_group_roles`, `test_group_social_links`, `test_legacy_uploads`,
`test_activity_log` y `test_performances`.
