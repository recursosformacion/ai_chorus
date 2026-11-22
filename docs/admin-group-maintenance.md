# Mantenimiento administrativo de grupos y miembros

**Estado:** implementado y verificado sobre MariaDB 10.4.32  
**Fecha:** 2026-11-22

## 1. Autoridad sobre los datos

Chorus es la **fuente única de verdad** de la pertenencia a grupos:

- Grupos, miembros y su estado.
- Cargos administrativos (`group_roles`, `scope='admin'`).
- Roles musicales (`group_roles`, `scope='musical'`).
- Secciones (`group_sections`).
- Permisos y responsabilidades dentro de cada grupo.

La **identidad** de los usuarios sigue procediendo de `osap-auth` (`user_id` de `GET /auth/me`). Chorus no mantiene un catálogo de usuarios ni escribe en tablas de grupos de OSAP.

## 2. Modelo de roles de pertenencia

`group_members.role` admite **exactamente dos valores**, sin tercer modelo:

| Valor | Significado |
|-------|-------------|
| `member` | **Miembro ordinario.** Rol por defecto de cualquier alta. |
| `manager` | Gestor del grupo. Único rol que puede conceder o retirar la responsabilidad de gestor. |

Los cargos administrativos y los roles musicales **no** son roles de pertenencia: son catálogos del grupo y no confieren privilegios de gestión por sí mismos.

Las referencias históricas al rol `collaborator` eran código muerto (el esquema unificado de la migración 034 no lo contiene) y se han eliminado para dejar una correspondencia inequívoca.

## 3. Incorporación de usuarios existentes

### 3.1 Contrato administrativo (para herramientas externas)

```
POST /api/v1/admin/groups/{group_id}/members
```

Cuerpo:

| Campo | Tipo | Notas |
|-------|------|-------|
| `user_sub` | string | Identificador de `osap-auth`. |
| `display_name` | string? | Nombre visible. |
| `admin_role_id` | string? | Cargo del **grupo**. |
| `musical_role_id` | string? | Rol musical del **grupo**. |
| `section_id` | string? | Sección del **grupo**. |

**El cuerpo no expone `role`**: el alta administrativa siempre crea un `member`. Aunque se envíe `role: "manager"`, se ignora.

### 3.2 Catálogos dinámicos

```
GET /api/v1/admin/groups/{group_id}/catalog
```

Devuelve `{group_id, sections[], admin_roles[], musical_roles[]}`. Los tres selectores se alimentan de aquí y guardan **estos** identificadores en la membresía. No hay listas fijas ni plantillas locales.

Cualquier identificador que no pertenezca al grupo se rechaza con `400`:

- `Section not found in this group`
- `Admin role not found in this group`
- `Musical role not found in this group`

## 4. Mantenimiento de grupos

| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/api/v1/admin/groups` | GET | Lista grupos de Chorus con recuentos (miembros, gestores, secciones, roles). |
| `/api/v1/admin/groups/{group_id}` | GET | Detalle y recuentos de catálogo. |
| `/api/v1/admin/groups/{group_id}/catalog` | GET | Cargos, roles musicales y secciones. |
| `/api/v1/admin/groups/{group_id}/members` | GET | Membresías con estado (`active`/`removed`); filtro `?status=`. |
| `/api/v1/admin/groups/{group_id}/members` | POST | Alta de miembro ordinario. |
| `/api/v1/admin/users` | GET | Directorio local de usuarios conocidos (`?q=`). |

El listado ordinario `GET /api/v1/groups/{group_id}/members` **no cambia**: sigue devolviendo sólo miembros activos y conserva su contrato. La vista administrativa es la que incluye altas, bajas y estados.

## 5. Seguridad y autorización

| Operación | Admin global | Gestor del grupo | Miembro |
|-----------|--------------|------------------|---------|
| Incorporar miembro ordinario | Sí | Sí | No |
| Modificar cargo / rol musical / sección | Sí | Sí | No |
| **Conceder o retirar `manager`** | **No** | **Sí** | No |
| Consultar mantenimiento | Sí | Vía su grupo | No |

Reglas aplicadas en backend (no sólo ocultando controles):

- `_may_grant_manager()` exige ser **gestor activo del grupo**. Un administrador global que no sea gestor recibe `403` al intentar cambiar `role`, tanto al dar de alta (`POST /groups/{id}/members` con `role: "manager"`) como al modificar (`PATCH /groups/{id}/members/{user_sub}`).
- El alta administrativa no admite `role`, por lo que no puede conceder permisos de gestión ni estructuralmente.
- Los catálogos se validan contra el grupo en **cada** operación (`_validate_group_catalog_refs`), incluida la sección, que antes no se comprobaba en la modificación.
- La autorización se resuelve siempre con la identidad real de `osap-auth` (`profile["user_id"]`), nunca con un parámetro de la petición.

## 6. Auditoría

Todas las operaciones relevantes quedan en `activity_log`:

| Evento | Origen |
|--------|--------|
| `member_added` (`source: admin_onboarding`) | Alta administrativa |
| `member_added` | Alta desde el mantenimiento del grupo |
| `member_role_change` | Cambio de rol, cargo, rol musical, sección o estado |
| `member_self_update` | Actualización del propio perfil de pertenencia |

Se registra `actor` (identidad de osap-auth), `from_status`, `to_status` y `detail_json` con los valores anteriores y nuevos.

Los identificadores de `activity_log.legacy_id` se generan con un fragmento UUID (antes se usaba el timestamp en segundos, que colisionaba al registrar dos operaciones del mismo usuario en el mismo segundo y hacía fallar la inserción).

## 7. Contrato con OSAP

OSAP ha retirado de la ficha global de usuarios el bloque antiguo de grupos, que consultaba catálogos locales obsoletos. La responsabilidad de la pertenencia pasa a Chorus.

Si una herramienta administrativa de OSAP necesita dar de alta, debe usar `POST /api/v1/admin/groups/{group_id}/members` con autenticación de administrador. **No** debe reactivarse la implementación antigua ni escribir en tablas de grupos de OSAP.

## 8. Limitaciones conocidas

- `GET /api/v1/admin/users` es un **directorio local**: sólo localiza usuarios que ya tienen alguna membresía en Chorus. `osap-auth` no expone (hasta donde Chorus tiene documentado) una búsqueda de usuarios; el contrato de identidad cubre `/auth/login`, `/auth/refresh` y `/auth/me`. Dar de alta por correo sin membresía previa no es posible sin un contrato adicional de `osap-auth`.
- `display_name` se fija en el alta y en la actualización que hace el propio usuario; el mantenimiento de grupo modifica cargo, rol musical, sección y estado.