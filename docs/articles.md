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

## Permisos editoriales

- Lectura: miembro activo.
- Creación/edición: `manager`, `collaborator` o autor.
- Publicación: `manager`.
- Retirada: autor, `collaborator` o `manager`.
- Borrado: solo en borrador; un artículo publicado debe retirarse primero.

Autoría (`author_user_id`) y publicación (`publisher_user_id`) son campos
distintos.

## Migración

Los artículos de grupo de OSAP se migran con
`scripts/migrate_osap_groups_articles.py`. El identificador original se conserva
en `id` y `legacy_id`. Los artículos generales no se migran.
