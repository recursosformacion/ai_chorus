# Grupos y artículos propios

Chorus es la autoridad sobre los grupos y sus artículos. No sincroniza grupos
con OSAP.

## Modelo

- `groups`: grupo, estado, tipo, descripción y datos públicos.
- `group_members`: pertenencia, rol (`manager`, `collaborator`, `member`) y
  responsabilidades (`admin_role_id`, `musical_role_id`, `section_id`).
- `group_sections`: catálogo local de secciones y responsabilidades.
- `group_articles`: artículo editorial del grupo.
- `group_article_media`: fotos, vídeos y documentos enlazados.
- `group_roles`: roles de administración y musicales específicos del grupo (scope `admin`/`musical`).
- `group_social_links`: enlaces a redes sociales y web del grupo.
- `legacy_uploads`: subidas heredadas de OSAP (solo lectura).
- `activity_log`: registro de actividad operativa (solo lectura).

## Permisos editoriales

- Lectura: miembro activo.
- Creación/edición: `manager`, `collaborator` o autor.
- Publicación: `manager`.
- Retirada: autor, `collaborator` o `manager`.
- Borrado: solo en borrador; un artículo publicado debe retirarse primero.

Autoría (`author_user_id`) y publicación (`publisher_user_id`) son campos
distintos.

## Endpoints

### Group Roles (`/api/v1/groups/{group_id}/roles`)

| Method | Path | Description | Permissions |
|--------|------|-------------|-------------|
| GET | `/roles` | List roles (filter by scope, active) | Member |
| GET | `/roles/{role_id}` | Get single role | Member |
| POST | `/roles` | Create role (scope, code, name, parent_id, sort_order) | Manager |
| PATCH | `/roles/{role_id}` | Update role | Manager |
| DELETE | `/roles/{role_id}` | Delete role (not if referenced by members or has children) | Manager |

### Group Social Links (`/api/v1/groups/{group_id}/social-links`)

| Method | Path | Description | Permissions |
|--------|------|-------------|-------------|
| GET | `/social-links` | List social links | Member |
| GET | `/social-links/{link_id}` | Get single social link | Member |
| POST | `/social-links` | Create link (kind, label, url, position) | Manager |
| PATCH | `/social-links/{link_id}` | Update link | Manager |
| DELETE | `/social-links/{link_id}` | Delete link | Manager |

Link kinds: `instagram`, `facebook`, `twitter`, `youtube`, `website`, `other`.

### Legacy Uploads (`/api/v1/groups/{group_id}/legacy-uploads`)

| Method | Path | Description | Permissions |
|--------|------|-------------|-------------|
| GET | `/legacy-uploads` | List legacy uploads (filter by mime_type) | Manager, Admin |

Read-only endpoint for migrated OSAP uploads.

### Activity Log (`/api/v1/groups/{group_id}/activity-log`, `/api/v1/admin/activity-log`)

| Method | Path | Description | Permissions |
|--------|------|-------------|-------------|
| GET | `/groups/{group_id}/activity-log` | Group-scoped activity log | Member |
| GET | `/admin/activity-log` | Global activity log (filter by group_id, event_type, actor) | Admin |

Event types: `article_publish`, `article_withdraw`, `member_role_change`, etc.

Automatic triggers:
- Publishing an article → `article_publish` entry
- Withdrawing an article → `article_withdraw` entry
- Changing member role → `member_role_change` entry

## Migración

Los artículos de grupo de OSAP se migran con
`scripts/migrate_osap_groups_articles.py`. El identificador original se conserva
en `id` y `legacy_id`. Los artículos generales no se migran.
