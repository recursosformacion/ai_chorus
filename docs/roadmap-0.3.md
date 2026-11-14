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
  entidad. **Solo un gestor de la entidad (o el admin) crea grupos**; los managers gestionan los
  grupos existentes (miembros, voces, agenda) y el admin web puede crear/gestionar
  cualquiera. Un miembro no crea grupos.

### 4.2 Agenda de ensayos y actuaciones

- `events`: tipo (`rehearsal`/`concert`/`other`/`note`), título, inicio/fin, lugar, notas,
  recurrencia (RRULE), cancelación, visibilidad.
- **Alcance de la nota**: `scope` = `global` o `groups`, con `event_groups` para los
  grupos afectados. El responsable puede marcar **Global y/o grupos**; así una nota
  global llega a todos y una de grupo solo a sus miembros.
- `event_rsvps`: **binario** `yes`/`no` (Asisto / No asisto) + comentario. Ensayos y
  actuaciones/citas deben mostrar siempre esos dos botones; las notas no llevan RSVP.
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

- Cada usuario elige **cómo recibe los comunicados**: WhatsApp, correo electrónico,
  mensajería OSAP (in-app) y **SMS**, con casillas independientes y opt-in explícito.
- `user_contact_preferences`: `user_id`, `channel` (`whatsapp`/`email`/`inapp`),
  `enabled`, `verified_at`, `updated_at`. El teléfono y el email viven en el perfil.
- Por grupo se podrá afinar más adelante (`group_notification_preferences`), empezando por
  la preferencia global.
- **Noticias globales** (fase posterior): el usuario elegirá qué categorías desea recibir
  (`news_categories` + `user_news_preferences`). De momento solo se modela la preferencia
  de canales; el catálogo de noticias globales se añadirá cuando exista el feed.
- WhatsApp requiere proveedor (Meta Cloud API/Twilio) y plantillas aprobadas; el primer
  corte puede limitarse a enlaces `wa.me`/recordatorios manuales.

### 4.9 WhatsApp: qué es gratis y qué no

| Opción | Coste | ¿Automatiza envíos? | Notas |
| --- | --- | --- | --- |
| Enlace `wa.me` / `api.whatsapp.com` | Gratis | No: abre WhatsApp con el texto; el usuario pulsa enviar | Sirve para recordatorios manuales; sin confirmación ni métricas |
| Meta WhatsApp Cloud API (directo) | Sin cuota de plataforma; ~1.000 conversaciones de servicio/mes gratis; las iniciadas por la empresa (plantillas) se pagan | Sí | Oficial; número dedicado, opt-in y plantillas aprobadas |
| Twilio WhatsApp Sandbox | Gratis para pruebas (limitado) | Sí, en sandbox | Producción de pago; útil para validar el flujo |
| BSP (360dialog, Gupshup, Vonage…) | Prueba y luego tarifa | Sí | Añaden capa comercial y soporte |
| Librerías no oficiales (Baileys, whatsapp-web.js, CallMeBot…) | “Gratis” | Sí | **No recomendado**: va contra los términos de WhatsApp y expone a bloqueos |

Datos importantes:

- La API oficial **no publica en grupos de WhatsApp**; solo envía mensajes 1:1. Para un
  grupo habría que enviar a cada miembro (con opt-in) o compartir un enlace de invitación.
- Los mensajes iniciados por la empresa requieren **plantilla aprobada** y una ventana de
  servicio de 24 h; fuera de ella se cobra.
- El teléfono debe ser un número dedicado a la API, no el WhatsApp personal del grupo.

Recomendación: fase 2 con **in-app + email**; WhatsApp mediante `wa.me` para lo manual y,
si se quiere automatizar, **Meta Cloud API directo** con presupuesto pequeño y plantillas
de utilidad. No usar librerías no oficiales en producción.

### 4.10 SMS: coste y uso recomendado

No hay SMS gratuitos para producción; solo créditos de prueba. Coste orientativo en
España: **0,04–0,09 € por SMS** según proveedor y volumen.

| Opción | Coste | Notas |
| --- | --- | --- |
| OVH SMS | ~0,04–0,06 €/SMS | UE, emisor alfanumérico, API sencilla |
| Twilio | ~0,07–0,09 €/SMS + tarifas | Crédito de prueba; global; buena API |
| Vonage / MessageBird / Telnyx / Plivo | similar | Prueba y luego tarifa; sender ID según país |
| AWS SNS | pago por SMS | Sin capa gratuita útil para producción |
| Email-to-SMS (puertas de operador) | “gratis” | **No fiable**: muchas retiradas, formato y entrega irregulares |
| Gateway con móvil Android | coste del SIM | Necesita un teléfono encendido; no es producción |

Límites: 160 caracteres GSM-7 (70 en Unicode), los mensajes largos se parten y se cobran
por segmento; hace falta remitente alfanumérico o número dedicado; consentimiento
explícito y baja fácil (GDPR). No sirve para contenido rico ni adjuntos.

Recomendación: SMS solo como **canal urgente** (cancelación de ensayo/concierto, cambio de
última hora), desactivado por defecto, con opt-in y límite de frecuencia. Para lo rutinario,
in-app y email (coste casi nulo). Si se aprueba, empezar con OVH SMS por cercanía y coste,
o Twilio si se quiere una API única para WhatsApp + SMS.

### 4.11 Planes, pagos opcionales y canales de pago

Modelo vigente, acordado con el equipo que ya gestiona suscripciones y donaciones:

- **Gratis**: área de trabajo de la entidad (grupos, agenda, repertorio, tablón,
  biblioteca) y comunicación in-app/email. Sin coste por miembro.
- **Descargas**: 10/día sin cuenta y 100/día con cuenta registrada, con las limitaciones
  del servicio y uso razonable. No se promete un número distinto sin revisar la cuota.
- **Suscripción de apoyo de 30 €/mes**: **opcional**. No bloquea funciones ni miembros;
  la gestiona el equipo actual de suscripciones/donaciones. Chorus no cobra ni pide datos
  de pago en el formulario de alta.
- **WhatsApp y SMS**: no incluidos. Se contratan aparte y se pagan por consumo
  (Meta Cloud API, OVH o Twilio). Preferencia: `wa.me` manual primero y Meta Cloud API
  después; nunca librerías no oficiales.
- **Donaciones**: mismo canal actual; no se duplica una pasarela en Chorus.
- **No se construye PayPal/facturación propia en esta fase.** Si se integra más adelante,
  será un add-on separado, siempre opcional y coordinado con el sistema existente.

Reglas de comunicación:

- Las casillas de canales se muestran siempre; WhatsApp/SMS quedan deshabilitados si la
  entidad no los ha contratado.
- El usuario decide sus canales; la entidad solo paga los canales de pago.
- `/alta.html` recoge datos de la entidad, interés en la suscripción voluntaria, WhatsApp
  y SMS, con consentimiento; no cobra nada.
- `/planes.html` explica en público qué es gratis, qué es opcional, los límites de
  descarga y el coste aparte de WhatsApp/SMS.

Pendiente: enlazar con el sistema actual de suscripciones (sin duplicarlo), IVA/factura
si se formaliza y política de uso razonable.

### 4.12 Entidades y gestores (rediseño)

Reglas acordadas:

- La **entidad la crea el admin web**, no el usuario. Se acaba el alta libre de entidades.
- Al crearla, el admin asigna uno o varios **gestores** entre usuarios ya registrados.
- El **gestor** puede editar los datos de la entidad, asignar/quitar otros gestores y crear
  grupos en Chorus. No puede dejar la entidad sin ningún gestor.
- La **pertenencia** (miembro de una entidad) es independiente de la gestión: un usuario
  puede pertenecer a varias entidades y gestionar otras.
- El admin conserva acceso total y todo queda auditado.

Modelo:

- `entity_managers` (`entity_id`, `user_id`, `assigned_by`, `created_at`; PK compuesta).
- `entity_memberships` sigue existiendo para “pertenece a”.
- `is_representative` se sustituye por `is_manager` derivado de `entity_managers`; se
  mantiene el alias antiguo durante la migración.
- Migración: cada `entities.created_by` actual pasa a ser manager; las pertenencias no
  cambian; los creadores de entidades existentes conservan su capacidad de gestión.

Onboarding:

- “Crear entidad” se convierte en **solicitar entidad** (pendiente) o se elimina del alta.
  Recomendación: solicitud + aprobación del gestor de la entidad (o del admin si aún no hay gestor), para no romper el flujo actual.

Chorus:

- `GET /api/v1/entities` (entidades que gestiona o a las que pertenece).
- `PATCH /api/v1/entities/{id}` (gestor): nombre, tipo, correo, zona horaria, descripción.
- `POST/DELETE /api/v1/entities/{id}/managers` (gestor/admin; no dejar la entidad sin
  gestores).
- `GET/POST /api/v1/entities/{id}/groups` (los grupos siguen viviendo en Chorus).
- Página **Entidades** para gestores: datos, gestores y grupos de cada entidad.

Admin web:

- Mantenimiento de entidades: crear, editar y asignar gestores.
- Ficha de usuario: “Pertenece a” (selector múltiple + añadir/quitar) y “Gestiona”
  (entidades que administra, con acceso a sus datos y gestores).

Fases:

| Fase | Alcance |
| --- | --- |
| 1 | `entity_managers`, migración de `created_by`, Alta de entidad por admin, asignación de gestores, página Entidades en Chorus |
| 2 | Solicitud/aprobación desde onboarding, traspaso de gestores, auditoría fina y permisos por grupo |

Criterio de salida: el admin crea una entidad, asigna a dos gestores; uno de ellos edita
el correo, añade un tercer gestor y crea un grupo; un miembro no gestor no puede editar.

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
  event_id TEXT NOT NULL, user_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('yes', 'no')),
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
| 1 | Grupos/miembros con voz/instrumento, agenda global+grupos con RSVP/ICS, repertorio | Un grupo crea un ensayo y una actuación; cada miembro responde Asisto / No asisto y lo ve en su calendario |
| 2 | Anuncios, noticias, notificaciones, asistencia, preferencias de canal | Aviso publicado y asistencia registrada; cada usuario recibe por sus canales |
| 3 | Documentos/actas, tareas/turnos, directorio, planes/pagos opcionales, WhatsApp verificado y SMS urgente | Acta adjunta, tareas asignadas, suscripción opcional coordinada con el equipo actual, WhatsApp con plantilla y SMS de urgencia con opt-in |
| 4 | Mensajería, push móvil, noticias globales por categoría, analítica | Chat por grupo, push y suscripción a noticias globales |

## 7. Orden inmediato propuesto

1. Puente MuseEncore (guardar/cerrar) y prueba en Android.
2. Duración de sesión y dispositivos activos.
3. Fase 1: modelo de grupos/miembros (voz/instrumento), agenda global+grupos, RSVP/ICS y
   repertorio.

Decisiones pendientes: quién del equipo actual gestiona las altas de suscripción/donación,
proveedor de WhatsApp (recomendado: `wa.me` primero y Meta Cloud API después),
proveedor/presupuesto de SMS (recomendado: solo urgentes y OVH SMS o Twilio) y si el primer
corte de comunicaciones sale solo in-app/email antes de integrar WhatsApp y SMS. La creación
de grupos queda cerrada: solo un gestor de entidad y el admin web.




