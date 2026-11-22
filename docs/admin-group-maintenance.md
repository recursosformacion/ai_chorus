# Mantenimiento administrativo de grupos y miembros

**Estado:** implementado y verificado sobre MariaDB 10.4.32  
**Fecha:** 2026-11-22

## 1. Autoridad sobre los datos

Chorus es la **fuente única de verdad de la pertenencia** a grupos:

- Grupos, miembros y su estado.
- Cargos administrativos (`group_roles`, `scope='admin'`).
- Roles musicales (`group_roles`, `scope='musical'`).
- Secciones (`group_sections`).
- Permisos y auditoría de las operaciones realizadas en Chorus.

La **identidad** es responsabilidad exclusiva de `osap-auth`:

- Identidad canónica (`user_id`, equivalente a `JWT.sub`).
- Nombre visible (`name`), nickname y datos de cuenta.

Chorus **no** mantiene catálogo, directorio, caché persistente ni réplica de usuarios. `group_members` representa **pertenencias**, no un registro de identidades.

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
| `user_sub` | string | Identificador canónico de `osap-auth`. **Debe existir en Auth.** |
| `display_name` | string? | **Ignorada.** El nombre se toma de Auth. |
| `admin_role_id` | string? | Cargo del **grupo**. |
| `musical_role_id` | string? | Rol musical del **grupo**. |
| `section_id` | string? | Sección del **grupo**. |

Flujo de la operación:

1. Comprueba rol de administrador y existencia del grupo.
2. **Verifica la identidad en `osap-auth`** mediante el contrato M2M (no la del actor, sino la del destinatario).
3. Si Auth no devuelve ese `user_id` → `400` y **no se crea ninguna fila**.
4. Si Auth no está disponible → `503` y **no se crea ninguna fila**.
5. Crea únicamente la relación de membresía, como `member`.
6. Registra en `activity_log` con el actor autenticado real y `identity_verified_by: "osap-auth"`.

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
| `/api/v1/admin/groups/{group_id}/members` | POST | Alta de miembro ordinario, verificando la identidad en Auth. |

**No existe** `GET /api/v1/admin/users` ni ningún directorio local de usuarios. Tampoco hay una ruta que agrupe `group_members` para simularlo: la única forma de incorporar a alguien es conocer su `user_id` canónico de `osap-auth`.

El listado ordinario `GET /api/v1/groups/{group_id}/members` **no cambia** su contrato: sigue devolviendo sólo miembros activos. La vista administrativa es la que incluye altas, bajas y estados.

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

## 7. Contrato M2M de osap-auth

Contrato real verificado en `osap-auth` (`api/routes/m2m_users.py`, `api/routes/oauth.py`, `domain/entities/service_client.py`):

### 7.1 Emisión de token de servicio

```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
client_id=<uuid del cliente de servicio>
client_secret=<secreto>
scope=auth:read_public_names
audience=osap-auth
```

Respuesta: `{access_token, token_type, expires_in, scope}` (TTL 300 s).

### 7.2 Resolución de nombres

```
GET /auth/m2m/users?ids=<uuid1,uuid2,...>
Authorization: Bearer <service token>
```

- Audiencia `osap-auth`, scope `auth:read_public_names`.
- Máximo **500** identificadores por llamada; Chorus los agrupa en lotes.
- Devuelve `[{id, name, nickname, nickname_public_consent}]`.
- Los UUID inexistentes o mal formados se **omiten** (no se inventa nombre).

### 7.3 Configuración en Chorus

| Variable | Clave `osap.toml` | Por defecto |
|----------|-------------------|-------------|
| `CHORUS_AUTH_M2M_CLIENT_ID` | `auth.m2m_client_id` | — |
| `CHORUS_AUTH_M2M_CLIENT_SECRET` | `auth.m2m_client_secret` | — |
| `CHORUS_AUTH_M2M_SCOPE` | `auth.m2m_scope` | `auth:read_public_names` |
| `CHORUS_AUTH_M2M_AUDIENCE` | `auth.m2m_audience` | `osap-auth` |

El token de servicio se cachea en memoria hasta su caducidad (margen de 30 s). **No** se utiliza el token del administrador como sustituto de la credencial M2M.

### 7.4 Nombres en los listados

`group_members` guarda `display_name` como **instantánea histórica** del nombre que Auth devolvió en el momento del alta o de la incorporación. No es una fuente de verdad:

- Los listados exponen `name` **resuelto por Auth** en lote (una sola llamada) e `identity_verified`.
- `display_name` se expone como `legacy_display_name` en la vista administrativa, marcado como no verificado.
- Si Auth no resuelve una identidad, `name` es `null` e `identity_verified` es `false`: nunca se usa la cadena local como identidad verificada.
- La columna se conserva por integridad histórica; no se ha eliminado.

## 8. Búsqueda de personas: carencia de contrato en osap-auth

Hay que distinguir dos operaciones:

| Operación | Estado |
|-----------|--------|
| Resolver el nombre público de un `user_id` conocido | **Disponible**: `GET /auth/m2m/users` (§7.2). |
| Buscar personas por correo, nickname u otro criterio | **No disponible** para M2M. |

Inspección del contrato real de `osap-auth`:

- `GET /auth/m2m/users` y `GET /auth/m2m/public-users`: sólo resolución por ids y listado de usuarios públicos con consentimiento (id + nickname). No admiten filtros de búsqueda.
- `GET /auth/admin/users`: devuelve usuarios completos, pero exige un **usuario** con rol `admin` (`require_role("admin")`), no un token de servicio, y no ofrece búsqueda ni paginación.

**Conclusión:** hoy Chorus no puede localizar a una persona por correo o nickname si no conoce ya su `user_id`. Propuesta de contrato a añadir en `osap-auth` (pendiente de autorización, no implementada aquí):

```
GET /auth/m2m/users/search?q=<texto>&limit=<n>
Authorization: Bearer <service token>   # aud=osap-auth, scope auth:read_public_names
```

- `q`: correo, nickname o parte del nombre.
- `limit`: tope (p. ej. 20) para evitar enumeración masiva.
- Respuesta: `[{id, name, nickname}]`, misma forma que el lookup actual.
- Cuestiones a decidir en Auth: si se permite buscar por email (dato sensible), si se requiere consentimiento, y si se limita por rol o por ámbito.

Esta dependencia queda **abierta**: hasta que exista, el alta administrativa exige conocer el `user_id` canónico.

## 9. Contrato con OSAP

OSAP ha retirado de la ficha global de usuarios el bloque antiguo de grupos, que consultaba catálogos locales obsoletos. La responsabilidad de la pertenencia pasa a Chorus.

Si una herramienta administrativa de OSAP necesita dar de alta, debe usar `POST /api/v1/admin/groups/{group_id}/members` con autenticación de administrador y un `user_sub` verificable por Auth. **No** debe reactivarse la implementación antigua ni escribir en tablas de grupos de OSAP.

## 10. Limitaciones conocidas

- Sin credenciales M2M configuradas, el alta administrativa responde `503` y los listados no muestran nombres (`identity_verified: false`). Es una decisión de seguridad: no se aceptan identidades sin verificar.
- `display_name` se mantiene como instantánea; el mantenimiento de grupo modifica cargo, rol musical, sección y estado.
- La búsqueda por correo/nickname depende de un contrato nuevo en `osap-auth` (§8).