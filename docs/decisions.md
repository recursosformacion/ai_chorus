# Decisiones de diseño de Chorus

Registro inicial de decisiones acordadas. Las decisiones técnicas pendientes no se presentan como cerradas.

## CH-001 — Chorus es una aplicación independiente

**Estado:** Aceptada.

Chorus tendrá interfaz, API, configuración y despliegue propios. OSAP proporciona servicios de catálogo, identidad y almacenamiento mediante APIs.

## CH-002 — La biblioteca personal es el núcleo

**Estado:** Aceptada.

El producto debe ser útil para un músico individual que solo desea ordenar, consultar, estudiar y editar su música. La colaboración no es requisito para usar Chorus.

## CH-003 — Un espacio personal por usuario

**Estado:** Aceptada.

Cada identidad de osap-auth tiene un único espacio personal, que permanece aunque el usuario abandone cualquier coro, orquesta o grupo.

## CH-004 — No existen perfiles globales rígidos

**Estado:** Aceptada.

No se fuerza al usuario a ser exclusivamente músico, director o compositor. Las responsabilidades se asignan en el contexto de cada grupo y recurso.

## CH-005 — OSAP es la autoridad del catálogo

**Estado:** Aceptada.

Chorus referencia Works y Resources OSAP. No duplica el catálogo ni decide de forma autónoma la identidad canónica de una Work.

## CH-006 — Editar no sobrescribe

**Estado:** Aceptada.

Muse-encore edita una copia de trabajo. Los guardados crean borradores/revisiones privadas. La publicación en OSAP crea un nuevo Resource; el original se conserva.

## CH-007 — Compatibilidad con el modelo OSAP V6

**Estado:** Aceptada.

Chorus utiliza los conceptos:
- Work: obra canónica.
- Resource: interpretación, arreglo o edición concreta.
- File: fichero físico.

La autoría pertenece a Work. Procedencia y derechos pertenecen al Resource. Uploader, composer y license-owner permanecen separados.

## CH-008 — Servicios de soporte no son requisito del núcleo

**Estado:** Aceptada.

Chorus puede integrarse con osap-support si una función lo necesita, pero el escritorio, biblioteca y edición no deben depender de una membresía o donación.

## CH-009 — Primero escritorio, después colaboración

**Estado:** Aceptada.

La secuencia prioriza biblioteca personal, editor y borradores, integración OSAP, contactos, grupos y agenda, y finalmente asistencia musical/IA.

## Decisiones técnicas pendientes

- Framework frontend y backend.
- Base de datos y estrategia de migraciones.
- Contratos y versiones de API reales de osap-auth, OSAP API y osap-storage.
- Modelo de permisos de archivos privados y compartidos.
- Mecanismo de integración y persistencia de Muse-encore.
- Estrategia de notificaciones.
- Política de retención, exportación y eliminación de datos personales.

Estas decisiones se resolverán inspeccionando primero los repositorios y contratos existentes. No se inventarán endpoints ni se duplicará lógica ya disponible en OSAP.
