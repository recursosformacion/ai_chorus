# Chorus 0.15 — Fase 3: Inventario OSAP → Chorus y Plan de Transferencia

**Fecha:** 2026-11-19  
**Estado:** Análisis (antes de implementar)  
**Bases de datos:** OSAP (`osap_api`) → Chorus (`osap_chorus_test`)

---

## 1. Resumen del Inventario

### OSAP (`osap_api`): 18 tablas `amigos_*`

| Tabla | Dominio | Registros aprox. (estimado) |
|-------|---------|----------------------------|
| `amigos_groups` | Core grupos | ~100s |
| `amigos_members` | Membresía + roles + voz + sección | ~1000s |
| `amigos_groups_history` | Historial de membresía | ~1000s |
| `amigos_coral_details` | Datos corales (12 campos) | ~100s |
| `amigos_coral_attributes` | EAV: language/repertoire/place | ~1000s |
| `amigos_group_catalog` | Secciones/catálogo por grupo | ~1000s |
| `amigos_group_catalog` | Catálogo/secciones | ~1000s |
| `amigos_group_links` | Enlaces externos por grupo | ~100s |
| `amigos_group_links` | Enlaces de grupo | ~100s |
| `amigos_group_types` | Taxonomía tipos de grupo | ~10s |
| `amigos_group_links` | Enlaces | ~100s |
| `amigos_media` | Media de artículos | ~100s |
| `amigos_articles` | Artículos/noticias | ~100s |
| `amigos_media` | Media adjunta | ~100s |
| `amigos_articles` | Artículos/noticias | ~100s |
| `amigos_uploads` | Subidas de archivos | ~100s |
| `amigos_group_links` | Enlaces externos | ~100s |
| `amigos_group_history` | Historial membresía | ~1000s |
| `amigos_events` | Log de eventos/auditoría | ~1000s |
| `amigos_actuaciones` | Actuaciones/conciertos | ~100s |
| `amigos_actuacion_groups` | M:N actuaciones ↔ grupos | ~100s |
| `amigos_articles` | Artículos/noticias | ~100s |
| `amigos_media` | Media de artículos | ~100s |
| `amigos_authorizations` | Permisos de usuario | ~100s |
| `amigos_role_templates` | Plantillas de roles | ~10s |
| `amigos_section_templates` | Plantillas de secciones | ~10s |
| `amigos_uploads` | Subidas de archivos | ~100s |
| `amigos_actuaciones` | Actuaciones/conciertos | ~100s |
| `amigos_actuacion_groups` | M:N actuaciones ↔ grupos | ~100s |

**Total: 18 tablas `amigos_*`**

---

### Chorus (`osap_chorus_test`): 21 tablas

| Tabla | Dominio | Equivalente OSAP |
|-------|---------|------------------|
| `groups` | Grupos | `amigos_groups` (parcial) + coral details |
| `group_members` | Membresía | `amigos_members` (parcial) |
| `group_sections` | Secciones | `amigos_group_catalog` |
| `group_articles` | Artículos | `amigos_articles` |
| `group_article_media` | Media | `amigos_media` |
| `group_sections` | Secciones | `amigos_group_catalog` |
| `events` | Eventos/agenda | `amigos_actuaciones` / `amigos_events` |
| `event_groups` | M:N eventos-grupos | `amigos_actuacion_groups` |
| `event_rsvps` | RSVP | — |
| `event_targets` | Targets de evento | — |
| `event_groups` | Eventos-grupos | `amigos_actuacion_groups` |
| `messages` | Mensajes | — |
| `message_recipients` | Destinatarios | — |
| `entity_leads` | Solicitudes de alta | — |
| `entity_leads` | Solicitudes alta | — |
| `messages` | Mensajes | — |
| `oidc_states` | Auth OIDC | — |
| `works` | Obras | — |
| `resources` | Recursos/versiones | — |
| `files` | Archivos | `amigos_uploads` / `amigos_media` |
| `works` | Obras | — |
| `resources` | Recursos | — |
| `library_items` | Biblioteca personal | — |
| `collections` | Colecciones | — |
| `collection_items` | Items de colección | — |
| `creation_drafts` | Borradores editor | — |
| `editor_source_tokens` | Tokens editor | — |
| `library_items` | Biblioteca | — |
| `collections` | Colecciones | — |
| `collection_items` | Items colección | — |
| `creation_drafts` | Borradores | — |
| `editor_source_tokens` | Tokens editor | — |
| `oidc_states` | Auth OIDC | — |

---

## 2. Análisis de Brechas (Gap Analysis)

### 2.1 Grupos (`groups`) — **Parcial**

| Campo OSAP | En Chorus | Estado |
|------------|-----------|--------|
| `id` | `id` | ✅ |
| `slug` | `slug` | ✅ |
| `name` | `name` | ✅ |
| `kind` | `kind` | ✅ |
| `description` | `description` | ✅ |
| `image_url` | `image_url` | ✅ |
| `website` | `website` | ✅ |
| `email` | `email` | ✅ |
| `logo_url` | `logo_url` | ✅ |
| `status` | `status` | ✅ |
| `editorial_mode` | `editorial_mode` | ✅ |
| `technical_description` | `technical_description` | ✅ |
| `admin_roles_json` | — | ❌ |
| `musical_roles_json` | — | ❌ |
| `join_code` | `join_code` | ✅ |
| `join_code_expires_at` | — | ❌ |
| **Coral details (12 campos Phase 2)** | **12 campos Phase 2** | ✅ **Phase 2** |
| `admin_roles_json` | — | ❌ |
| `musical_roles_json` | — | ❌ |

**Faltante:** `admin_roles_json`, `musical_roles_json`, `join_code_expires_at`

### 2.2 Miembros (`group_members` vs `amigos_members`) — **Parcial**

| Campo OSAP | En Chorus | Estado |
|------------|-----------|--------|
| `group_id` | `group_id` | ✅ |
| `user_id` | `user_sub` | ✅ |
| `role` | `role` | ✅ |
| `status` | `status` | ✅ |
| `granted_by` | — | ❌ |
| `admin_role_id` | `admin_role_id` | ✅ |
| `musical_role_id` | `musical_role_id` | ✅ |
| `section_id` | `section_id` | ✅ |
| `voice_code` | `voice_code` | ✅ |
| `voice_label` | `voice_label` | ✅ |
| `section` (string) | `section` | ✅ |
| `display_name` | `display_name` | ✅ |
| `section_id` (FK) | `section_id` | ✅ |

**Faltante:** `granted_by`, `created_at`, `updated_at` (en Chorus son `joined_at`, `updated_at`)

### 2.3 Historial de Membresía (`amigos_group_history`) — **FALTA**

Tabla completa ausente en Chorus. Contiene:
- `event_type` (joined, left, role_change, etc.)
- `member_user_id`, `person_name`, `role`
- `start_date`, `end_date`
- `notes`

### 2.4 Secciones / Catálogo (`group_sections` vs `amigos_group_catalog`) — **Parcial**

| Campo OSAP | En Chorus | Estado |
|------------|-----------|--------|
| `id` | `id` | ✅ |
| `group_id` | `group_id` | ✅ |
| `code` | `code` | ✅ |
| `name` | `name` | ✅ |
| `scope` | `scope` | ✅ |
| `parent_id` | `parent_id` | ✅ |
| `sort_order` | `sort_order` | ✅ |
| `active` | `active` | ✅ |
| `created_at` | `created_at` | ✅ |
| `updated_at` | `updated_at` | ✅ |
| `parent_code` | — | ❌ |
| `sort_order` (template) | `sort_order` | ✅ |

**Faltante:** `amigos_section_templates` (plantillas de secciones) — tabla completa ausente

### 2.5 Artículos (`group_articles` vs `amigos_articles`) — **Parcial**

| Campo OSAP | En Chorus | Estado |
|------------|-----------|--------|
| `id` | `id` | ✅ |
| `group_id` | `group_id` | ✅ |
| `title` | `title` | ✅ |
| `slug` | `slug` | ✅ |
| `event_date` | `event_date` | ✅ |
| `summary` | `summary` | ✅ |
| `body` | `body` | ✅ |
| `cover_url` | `cover_url` | ✅ |
| `author_user_id` | `author_user_id` | ✅ |
| `status` | `status` | ✅ |
| `published_at` | `published_at` | ✅ |
| `reviewed_by` | `reviewed_by` | ✅ |
| `reviewed_at` | `reviewed_at` | ✅ |
| `review_note` | `review_note` | ✅ |
| `scope` | — | ❌ |
| `publisher_user_id` | `publisher_user_id` | ✅ |
| `reviewed_at` | `reviewed_at` | ✅ |

**Faltante:** `scope` (group/entity/public)

### 2.6 Media (`group_article_media` vs `amigos_media`) — **Parcial**

| Campo OSAP | En Chorus | Estado |
|------------|-----------|--------|
| `id` | `id` | ✅ |
| `article_id` | `article_id` | ✅ |
| `kind` | `kind` | ✅ |
| `url` | `url` | ✅ |
| `provider` | `provider` | ✅ |
| `video_id` | `video_id` | ✅ |
| `caption` | `caption` | ✅ |
| `credit` | `credit` | ✅ |
| `position` | `position` | ✅ |

✅ **Completo** (excepto `legacy_id` que es histórico)

### 2.6 Actuaciones / Eventos — **Parcial**

| Tabla OSAP | En Chorus | Estado |
|------------|-----------|--------|
| `amigos_actuaciones` | `events` | Parcial |
| `amigos_actuacion_groups` | `event_groups` | ✅ |
| `amigos_events` (auditoría) | `event_targets` / `event_rsvps` | Parcial |

**Brechas principales en `events` vs `amigos_actuaciones`:**
- `kind` (concert, rehearsal, etc.) ✅
- `modality` (onsite/online) ❌
- `venue_address`, `latitude`, `longitude`, `map_url` ❌
- `organizer_name`, `organizer_website` ❌
- `event_url`, `tickets_url` ❌
- `price`, `access_info` ❌
- `public_contact` ❌
- `registration_deadline` ❌
- `editorial_status` (draft/published) ❌
- `weight`, `views`, `expands`, `buys` ❌
- `source_email`, `source_note` ❌

### 2.7 Autorizaciones / Roles — **FALTA**

| Tabla OSAP | En Chorus | Estado |
|------------|-----------|--------|
| `amigos_authorizations` | — | ❌ |
| `amigos_role_templates` | — | ❌ |
| `amigos_section_templates` | — | ❌ |

### 2.7 Subidas / Archivos (`files` vs `amigos_uploads` / `amigos_media`) — **Parcial**

| Campo OSAP | En Chorus | Estado |
|------------|-----------|--------|
| `file_id` | `id` | ✅ |
| `group_id` | (en `resources`) | Parcial |
| `mime_type` | `mime_type` | ✅ |
| `size_bytes` | `size_bytes` | ✅ |
| `created_by` | (en `resources`) | Parcial |

### 2.8 Solicitudes de Alta (`entity_leads`) — **NUEVO en Chorus**

Chorus tiene `entity_leads` que no existe en OSAP (nuevo flujo de alta).

---

## 3. Plan de Transferencia Priorizado

### Prioridad 1: Completar Grupos y Miembros (Base)
1. **Añadir a `groups`**: `admin_roles_json`, `musical_roles_json`, `join_code_expires_at`
2. **Añadir a `group_members`**: `granted_by`, renombrar `joined_at`→`created_at` (o añadir `created_at`)
3. **Crear `group_history`** (de `amigos_group_history`)

### Prioridad 2: Completar Secciones y Artículos
4. **Crear `section_templates`** (de `amigos_section_templates`)
5. **Añadir `scope` a `group_articles`**
6. **Completar `group_sections`** con `parent_code` (ya existe `parent_id`)

### Prioridad 3: Eventos/Actuaciones
8. **Ampliar `events`** con campos de `amigos_actuaciones`:
   - `modality`, `venue_address`, `latitude`, `longitude`, `map_url`
   - `organizer_name`, `organizer_website`, `event_url`, `tickets_url`
   - `price`, `access_info`, `public_contact`
   - `registration_deadline`, `editorial_status`
   - `organizer_group_id` (FK a groups)
   - `last_verified_on`, `internal_notes`
   - `weight`, `views`, `expands`, `buys`
   - `source_email`, `source_note`
9. **Crear `actuaciones`** si se mantiene separada de `events` (revisar arquitectura)

### Prioridad 4: Autorizaciones y Plantillas
10. **Crear `authorizations`** (de `amigos_authorizations`)
11. **Crear `role_templates`** (de `amigos_role_templates`)
12. **Crear `section_templates`** (de `amigos_section_templates`)

### Prioridad 5: Historial y Auditoría
13. **Crear `group_history`** (de `amigos_group_history`)
14. **Mapear `amigos_events`** → auditoría unificada

### Prioridad 6: Archivos y Media
15. **Unificar `files` / `resources`** con `amigos_uploads` / `amigos_media`
16. **Migrar `amigos_media`** → `group_article_media`

### Prioridad 7: Datos Corales (ya en Phase 2)
16. ✅ 12 campos corales en `groups` (Phase 2)
14. ✅ Migración `amigos_coral_details` + `amigos_coral_attributes` → `groups` (12 campos + JSON)

---

## 4. Estrategia de Migración

### Enfoque: "Expandir sin romper"
- **No eliminar** tablas OSAP (fuente de verdad histórica)
- **Expandir** Chorus con campos/tablas faltantes
- **Migrar datos** con scripts idempotentes (solo llenar NULLs, no sobrescribir)
- **Mantener IDs** (`char(32)` / `char(36)`) para trazabilidad

### Orden de Migración Sugerido
1. **DDL**: Tablas nuevas + columnas nuevas (migraciones 017-030)
2. **Datos**: Scripts de migración por dominio (grupos → miembros → secciones → eventos → historial → autorizaciones → plantillas)
3. **Validación**: Tests de integridad + tests de API
13. **Limpieza**: Deprecar campos duplicados si procede

---

## 5. Próximos Pasos Inmediatos

**Antes de implementar:** Confirmar con usuario:
1. ¿Mantener `events` unificado o separar `actuaciones`?
2. ¿Migrar `amigos_authorizations` → nuevo sistema de permisos en Chorus?
3. ¿Unificar `resources`/`files` con `amigos_uploads`/`amigos_media`?
4. ¿Crear tabla `group_history` o reutilizar `amigos_events` (auditoría)?
5. ¿Migrar `amigos_role_templates` + `amigos_section_templates` como configuración o como tablas editables?

**Próximo paso recomendado:** Implementar Prioridad 1 (completar grupos y miembros) + crear `group_history`.

---

*Documento de análisis — listo para revisión antes de implementar.*