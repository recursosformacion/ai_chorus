# Mensajes de grupo (Chorus 0.9)

## Alcance

Cualquier miembro activo de un grupo puede escribir a:

- **Todo el grupo** (`scope=group`).
- **Administración del grupo** (`scope=managers`).
- **Una o varias personas** del grupo (`scope=users` + `recipient_subs`).

Los gestores ven en el dashboard “Mis grupos” y el botón **Gestionar** para entrar en los
comunicados de cada grupo. Los mensajes se leen en la tarjeta “Comunicados”; el contador
muestra los no leídos.

## API

- `GET /api/v1/groups/{group_id}/members`
- `GET /api/v1/groups/{group_id}/messages`
- `POST /api/v1/groups/{group_id}/messages`
- `POST /api/v1/messages/{message_id}/read`

Solo los miembros activos (o un admin global) acceden a miembros y mensajes. Los mensajes
de administración solo los ven gestores y el remitente; los directos solo remitente y
destinatarios.

## Límites conocidos

- No hay envío por email ni notificaciones push: es mensajería in-app.
- No hay edición/borrado ni moderación de mensajes.
- No hay todavía gestión de altas/bajas de miembros desde la UI; se hace por código de
  invitación.
- Un usuario que no pertenece al grupo no puede escribirle; falta decidir si se abre un
  canal de contacto para no miembros.
