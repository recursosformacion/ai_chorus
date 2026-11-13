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

### 4.1 Identidad y permisos

- `groups`: `id`, `entity_id` (osap-auth), `name`, `timezone`, `created_by`, `settings`.
- `group_members`: `group_id`, `user_id`, `role` (`manager`/`member`), `status`,
  `joined_at`.
- El representante de la entidad es `manager` por defecto; puede nombrar más managers.
- El admin de OSAP puede administrar cualquier grupo (auditado).

### 4.2 Agenda de ensayos y actuaciones

- `events`: tipo (`rehearsal`/`concert`/`other`), título, inicio/fin, lugar, notas,
  recurrencia (RRULE), cancelación, visibilidad.
- `event_rsvps`: `yes`/`no`/`maybe` + comentario.
- Vista mes/semana/lista; feed ICS por grupo y por usuario
  (`/api/v1/groups/{id}/calendar.ics?token=…`).
- Zona horaria por grupo; recordatorios (email/push) 24 h y 2 h antes.

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

## 5. Fases

| Fase | Alcance | Criterio de salida |
| --- | --- | --- |
| 1 | Grupos/miembros, agenda + RSVP + ICS, repertorio | Un grupo crea un ensayo, los miembros confirman y lo ven en su calendario |
| 2 | Anuncios, noticias, notificaciones, asistencia | Aviso publicado y asistencia registrada por evento |
| 3 | Documentos/actas, tareas/turnos, directorio | Acta adjunta a evento y tareas asignadas |
| 4 | Mensajería, push móvil, analítica de grupo | Chat por grupo y notificaciones push |

## 6. Orden inmediato propuesto

1. Puente MuseEncore (guardar/cerrar) y prueba en Android.
2. Duración de sesión y dispositivos activos.
3. Fase 1 de grupos (modelo + agenda + RSVP + ICS + repertorio).

Decisiones pendientes: ¿la agenda y el repertorio son por **entidad** o por **grupo**
independiente dentro de la entidad? ¿Quién puede crear grupos: solo el representante o
cualquier miembro? ¿Email transaccional con el proveedor actual o solo in-app al principio?
