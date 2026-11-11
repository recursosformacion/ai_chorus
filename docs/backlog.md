# Backlog de Chorus

Lista priorizada acordada el 2026-11-11. El detalle de cada entrega se añade al
cerrarla.

## 1. Identidad y acceso (en curso)

- [x] Login OIDC con osap-auth (PKCE) desde Chorus: Google, GitHub, correo y alta
  de cuenta nueva en la pantalla de Auth.
- [x] Cliente OIDC `chorus-web` y callback `http://chorus-app/api/v1/auth/oidc/callback`.
- [ ] Probar el flujo completo con una cuenta real y onboarding.
- [ ] Cliente OIDC de producción y audiencia propia `chorus-api` (endurecimiento).

## 2. Editor y archivos locales

- [ ] “Abrir en MuseScore”: descarga `.mscz` y asociación de archivos; subida del
  resultado al volver.
- [ ] Recordar el `FileSystemFileHandle` (Chromium) y releer el archivo al volver
  (“Traer cambios”).
- [ ] Companion opcional con protocolo `chorus://` para abrir MuseScore en un clic.

## 3. Partituras en PDF

- [ ] Subir PDF como referencia y ejecutar OMR (Audiveris u oemer) en servidor.
- [ ] Devolver un `.mxl` provisional, abrirlo en MuseEncore y permitir corrección.
- [ ] Conservar el PDF original y marcar la procedencia en los metadatos.

## 4. Grupo y entidades

- [ ] Convocatorias y reuniones: orden del día, RSVP y actas.
- [ ] Agenda compartida con exportación ICS.
- [ ] Repertorio del grupo, asignación de voces/instrumentos y estado de preparación.
- [ ] Distribución de partituras y confirmación de recepción.
- [ ] Asistencia, estadísticas y justificaciones.
- [ ] Documentos, votaciones y avisos por correo al grupo.
- [ ] Permisos por rol (representante/director/miembro) y separación personal/grupo.

## 5. Plataforma

- [ ] Motor de base de datos definitivo y almacenamiento de producción.
- [ ] Despliegue con Apache/uvicorn y cabeceras de seguridad.
- [ ] Copias, restauración y verificación periódica de integridad (extender la
  comprobación SHA-256 ya disponible).
