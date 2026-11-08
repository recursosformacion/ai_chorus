# Roadmap de Chorus

El desarrollo se organiza por entregas verticales. La primera entrega debe resolver de verdad el uso individual antes de añadir estructuras sociales.

## Fase 0 — Fundamentos (actual)

- [x] Definir propósito y principios del producto.
- [x] Separar responsabilidades de Chorus, osap-auth, OSAP API y osap-storage.
- [x] Definir modelo lógico inicial.
- [ ] Revisar contratos reales disponibles en osap-auth, OSAP API y osap-storage.
- [ ] Decidir stack de frontend/backend a partir de los estándares ya usados en los repositorios OSAP.
- [ ] Definir configuración por entorno y estrategia de pruebas.

Criterio de salida: arquitectura contrastada con los contratos reales, sin suponer endpoints ni campos que no existan.

## Fase 1 — Escritorio personal y biblioteca

- [ ] Autenticación mediante osap-auth.
- [ ] Creación automática del UserWorkspace.
- [ ] Pantalla de inicio del escritorio.
- [ ] Biblioteca con búsqueda local, filtros y ordenación.
- [ ] Añadir y retirar referencias a Resources OSAP.
- [ ] Colecciones personales.
- [ ] Recursos privados y carga de ficheros mediante osap-storage.
- [ ] Estados de carga, error, acceso denegado y recurso no disponible.

Criterio de salida: una persona puede organizar su música sin pertenecer a ningún grupo.

## Fase 2 — Taller musical y borradores

- [ ] Integrar Muse-encore para MusicXML/MXL.
- [ ] Abrir Resource sin modificar el original.
- [ ] Crear Draft desde un Resource o desde un fichero privado.
- [ ] Guardar revisiones inmutables.
- [ ] Recuperar una revisión anterior.
- [ ] Exportar o guardar el resultado privado.
- [ ] Flujo explícito de publicación a OSAP que cree un nuevo Resource.

Criterio de salida: el usuario puede editar una partitura, conservar el original y gestionar su trabajo privado.

## Fase 3 — Exploración e integración OSAP

- [ ] Búsqueda de Works y Resources.
- [ ] Vista de detalle suficiente para elegir la edición adecuada.
- [ ] Incorporar Resource a la biblioteca personal.
- [ ] Resolver permisos y disponibilidad de File.
- [ ] Publicar nuevos Resources a través de la API oficial.
- [ ] Tratar conflictos, duplicados y errores de contrato sin crear Work por inferencia local.

La búsqueda OSAP puede comenzar como parte de la Fase 1 si los contratos están listos; la prioridad de producto sigue siendo que la biblioteca personal sea el centro.

## Fase 4 — Contactos y colaboración

- [ ] Contactos y solicitudes de relación.
- [ ] Compartir un elemento con una persona concreta.
- [ ] Aceptar, revocar y auditar accesos.
- [ ] Notificaciones esenciales.

## Fase 5 — Agrupaciones y organización

- [ ] Crear y administrar Groups.
- [ ] Membresías y responsabilidades.
- [ ] Secciones y pertenencia a varias secciones.
- [ ] Repertorio de grupo mediante referencias a Resources.
- [ ] Distribuir partituras por grupo o sección.
- [ ] Agenda de ensayos, reuniones y conciertos.
- [ ] Confirmaciones de asistencia.

## Fase 6 — Asistencia musical e IA

- [ ] Explicación contextual de una partitura.
- [ ] Análisis armónico y estructural.
- [ ] Ayuda para instrumentar y adaptar.
- [ ] Ejercicios y materiales de estudio.
- [ ] Herramientas de apoyo a composición para principiantes.

Las funciones de IA se diseñan como asistencia verificable y contextual, no como sustitución de la edición musical ni como fuente de metadatos inventados.

## Criterios transversales

- Pruebas automatizadas para reglas de dominio y permisos.
- Ningún test fallido se acepta como estado terminado.
- No se realizan escrituras en bases de datos de producción durante el desarrollo inicial.
- Las integraciones se prueban con dobles y contratos reproducibles.
- No se implementan funciones sociales antes de que el escritorio individual sea útil.
- Cada fase debe dejar una aplicación ejecutable y documentada.
