# Chorus 0.3 — hoja de ruta: grupos, agenda y comunicación

Estado: propuesta para revisar. No implementado todavía.

## 1. Correcciones y hallazgos de esta revisión

- **Licencias**: la búsqueda volvió a mostrar «Licencia no indicada» por dos causas:
  `osap_api` había perdido el `GRANT SELECT` sobre `osap_storage` (restaurado) y un
  candidato con `source_url` pero sin licencia reconocible provocaba un `KeyError` que
  abortaba la búsqueda del índice. Corregido en osap-api 5.12.1 (`license_info.get`).
- **Usar**: ya no hace scroll; abre el modal de borrador con las acciones (MuseEncore,
  descargar, subir). Desplegado en Chorus 0.2.3.
- **Recogida al salir de MuseEncore**: no está implementada. El wrapper `editor.html`
  solo embebe el editor; el usuario debe exportar y subir el `.mxl` a mano.
- **Sesión**: el refresh token usa un TTL global; no hay elección de duración ni
  «recordarme» explícito.
- **Reproductor**: Chorus usa el editor/reproductor de MuseEncore. Es web (canvas/Web
  Audio), no una app nativa; debería funcionar en Chrome Android, pero la UI del editor
  no está adaptada a móvil y falta una prueba real en dispositivo.

## 2. Puente MuseEncore → Chorus (guardar y cerrar)

Objetivo: al pulsar «Volver a Chorus» o cerrar el editor, la pieza se guarda en el
borrador de Chorus y la ventana se cierra, sin abrir un OSAP nuevo.

Diseño:

1. Chorus añade `draft_id` a la URL del editor:
   `/editor.html?src=…&title=…&draft_id=…`.
2. `editor.html` escucha `message` del iframe:
   - `{type:"chorus:request-export"}` → el editor exporta el estado actual a `.mxl`.
   - `{type:"chorus:score", data: ArrayBuffer, filename}` → Chorus hace
     `POST /api/v1/drafts/{draft_id}/files` (multipart) y muestra el resultado.
3. Botón «Volver a Chorus» y `beforeunload`:
   - pide exportación, espera la respuesta, sube el fichero y `window.close()`.
   - si el navegador bloquea el cierre, redirige a `/` de Chorus (no a OSAP).
4. MuseEncore: añadir un listener en `editor/` que use
   `createExportDialogModel(score, settings().export, baseName)` y
   `model.exportScores()` para generar el `.mxl` en memoria, sin abrir el diálogo.
5. Si el usuario no ha modificado nada, no se sube nada (hash del `.mxl` frente al
   original); el borrador conserva la referencia.

Riesgos: el iframe es cross-origin; validar `event.origin` contra el origen del editor.
El cierre de ventanas abiertas por `window.open` solo lo permite el navegador si la
ventana fue abierta por script (es el caso).

## 3. Duración de sesión

- Añadir en login: «Sesión de este dispositivo» (por defecto, 12 h), «Recordarme 7 días»,
  «Recordarme 30 días» (trabajo).
- El backend acepta `remember_days` (0 = sesión de navegador) y aplica el TTL al refresh
  token; el access token sigue corto (15 min) y se renueva.
- No recordar credenciales de Google: `prompt=select_account` ya está activo.
- Mostrar en la cuenta los dispositivos/sesiones activos y permitir revocarlos.

## 4. Funciones de grupo

### 4.1 Identidad, permisos y datos de miembro

- `groups`: `id`, `entity_id` (osap-auth), `name`, `timezone`, `created_by`, `settings`.
- `group_members`: `group_id`, `user_id`, `role` (`manager`/`member`), `status`,
  `joined_at`, **`voice`/`instrument`** (código canónico cuando exista + etiqueta),
  `section` (cuerda, cuerda alta, percusión…), notas.
- La voz/instrumento es **por grupo**: una persona puede cantar en un coro y tocar en una
  banda. El código se valida contra los vocabularios de osap-storage (`instruments`,
  voces); la etiqueta libre queda para lo que no encaje.
- Mantenimiento:
  - **Responsable del grupo** (manager) puede editar voces/instrumentos de sus miembros.
  - **Cada usuario** puede editar su propia voz/instrumento y sus datos de contacto.
  - **Admin web de OSAP** (`role=admin` en osap-auth) puede editar cualquier grupo y
    miembro; toda acción queda auditada.
- El grupo se enlaza con la entidad de osap-auth, pero puede haber varios grupos por
  entidad; el representante de la entidad es manager por defecto.

### 4.2 Agenda de ensayos y actuaciones

- `events`: tipo (`rehearsal`/`concert`/`other`/`note`), título, inicio/fin, lugar, notas,
  recurrencia (RRULE), cancelación, visibilidad.
- **Alcance de la nota**: `scope` = `global` o `groups`, con `event_groups` para los
  grupos afectados. El responsable puede marcar **Global y/o grupos**; así una nota
  global llega a todos y una de grupo solo a sus miembros.
- `event_rsvps`: `yes`/`no`/`maybe` + comentario.
- Vista mes/semana/lista; feed ICS por grupo y por usuario
  (`/api/v1/groups/{id}/calendar.ics?token=…`).
- Zona horaria por grupo; recordatorios 24 h y 2 h antes, por los canales elegidos.

### 4.3 Repertorio

- `setlists`: nombre, evento opcional, estado (`draft`/`confirmed`).
- `setlist_items`: posición, obra (`work_id`), recurso de biblioteca, notas, estado de
  preparación (`new`/`learning`/`ready`), responsable.
- Enlaza con `library_items` de Chorus; el director ve el conjunto y cada miembro su
  parte.

### 4.4 Comunicaciones y noticias

- `announcements` (tablón): título, cuerpo, fijado, autor, visibilidad, adjuntos.
- `comments` sobre anuncios y eventos.
- `notifications` in-app (campana) + resumen por email; preferencias por usuario.
- Fase posterior: mensajería 1:1 o hilos por grupo, con mención y moderación.

### 4.5 Asistencia y actas

- `attendance`: estado por evento (`present`/`absent`/`late`/`excused`), quién lo anota.
- Estadísticas por miembro y por obra.
- `documents`: actas, partituras de trabajo, programas; permisos por grupo/evento.

### 4.6 Tareas y turnos

- `tasks`: título, descripción, asignado, fecha límite, estado, evento relacionado.
- Turnos de concierto (montaje, transporte, taquilla) con cupos y confirmación.

### 4.7 Directorio

- Miembros con voz/instrumento, disponibilidad y contacto (opt-in).
- Privacidad: por defecto solo nombre y rol; el email/teléfono lo decide cada miembro.

### 4.8 Preferencias de comunicación y noticias globales

- Cada usuario elige **cómo recibe los comunicados**: WhatsApp, correo electrónico y
  mensajería OSAP (in-app), con casillas independientes y opt-in explícito.
- `user_contact_preferences`: `user_id`, `channel` (`whatsapp`/`email`/`inapp`),
  `enabled`, `verified_at`, `updated_at`. El teléfono y el email viven en el perfil.
- Por grupo se podrá afinar más adelante (`group_notification_preferences`), empezando por
  la preferencia global.
- **Noticias globales** (fase posterior): el usuario elegirá qué categorías desea recibir
  (`news_categories` + `user_news_preferences`). De momento solo se modela la preferencia
  de canales; el catálogo de noticias globales se añadirá cuando exista el feed.
- WhatsApp requiere proveedor (Meta Cloud API/Twilio) y plantillas aprobadas; el primer
  corte puede limitarse a enlaces `wa.me`/recordatorios manuales.

## 5. Modelo de datos propuesto (SQLite, migraciones 006+)

```sql
CREATE TABLE groups (
  id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, name TEXT NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'Europe/Madrid', created_by TEXT NOT NULL,
  settings TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE group_members (
  id TEXT PRIMARY KEY, group_id TEXT NOT NULL, user_id TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member', status TEXT NOT NULL DEFAULT 'active',
  voice_code TEXT, voice_label TEXT, section TEXT, notes TEXT,
  joined_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(group_id, user_id)
);
CREATE TABLE events (
  id TEXT PRIMARY KEY, group_id TEXT, scope TEXT NOT NULL DEFAULT 'groups',
  kind TEXT NOT NULL, title TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT,
  location TEXT, notes TEXT, recurrence TEXT, created_by TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, cancelled_at TEXT
);
CREATE TABLE event_groups (
  event_id TEXT NOT NULL, group_id TEXT NOT NULL, PRIMARY KEY(event_id, group_id)
);
CREATE TABLE event_rsvps (
  event_id TEXT NOT NULL, user_id TEXT NOT NULL, status TEXT NOT NULL,
  comment TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(event_id, user_id)
);
CREATE TABLE announcements (
  id TEXT PRIMARY KEY, group_id TEXT, scope TEXT NOT NULL DEFAULT 'groups',
  title TEXT NOT NULL, body TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0,
  author_id TEXT NOT NULL, published_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE attendance (
  event_id TEXT NOT NULL, user_id TEXT NOT NULL, status TEXT NOT NULL,
  recorded_by TEXT NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(event_id, user_id)
);
```

Las tablas de repertorio, documentos, tareas y noticias globales se añaden en fases
posteriores, siguiendo el mismo patrón de `group_id` + permisos.

## 6. Fases

| Fase | Alcance | Criterio de salida |
| --- | --- | --- |
| 1 | Grupos/miembros con voz/instrumento, agenda global+grupos con RSVP/ICS, repertorio | Un grupo crea un ensayo, asigna voces y los miembros confirman y lo ven en su calendario |
| 2 | Anuncios, noticias, notificaciones, asistencia, preferencias de canal | Aviso publicado y asistencia registrada; cada usuario recibe por sus canales |
| 3 | Documentos/actas, tareas/turnos, directorio, WhatsApp verificado | Acta adjunta a evento, tareas asignadas y WhatsApp con plantilla aprobada |
| 4 | Mensajería, push móvil, noticias globales por categoría, analítica | Chat por grupo, push y suscripción a noticias globales |

## 7. Orden inmediato propuesto

1. Puente MuseEncore (guardar/cerrar) y prueba en Android.
2. Duración de sesión y dispositivos activos.
3. Fase 1: modelo de grupos/miembros (voz/instrumento), agenda global+grupos, RSVP/ICS y
   repertorio.

Decisiones pendientes: quién puede crear grupos (responsable de entidad, managers o
cualquier miembro), proveedor de WhatsApp y si el primer corte de comunicaciones sale
solo in-app/email antes de integrar WhatsApp.
