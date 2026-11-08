# Decisiones de diseño de Chorus

## CH-001 — Chorus es una aplicación independiente

**Estado:** Aceptada.

Chorus tiene interfaz, API, repositorio, configuración, base de datos y almacenamiento propios. No es una sección de la aplicación OSAP. Se conecta a servicios externos mediante APIs.

## CH-002 — La biblioteca personal es el núcleo

**Estado:** Aceptada.

Chorus debe ser útil para un músico individual. La colaboración no es requisito para usarlo.

## CH-003 — Un espacio personal por usuario

**Estado:** Aceptada.

Cada identidad de osap-auth se vincula a un único espacio personal permanente en Chorus.

## CH-004 — Capacidades contextuales

**Estado:** Aceptada.

No hay perfiles globales excluyentes de músico, director o compositor. Las responsabilidades dependen del grupo y del contexto.

## CH-005 — OSAP es catálogo externo; Chorus no lo duplica

**Estado:** Aceptada.

En la primera etapa Chorus puede buscar, consultar y leer Works y Resources OSAP. Conserva referencias externas y no modifica el catálogo ni escribe en su base de datos.

## CH-006 — Obras propias en almacenamiento y base de datos Chorus

**Estado:** Aceptada.

Las obras propias del usuario tienen identidad local en Chorus. Su contenido se guarda como ficheros en el nuevo formato versionado de Chorus; la base de datos propia registra metadatos, índices, relaciones, versiones, checksums y referencias a esos ficheros. No necesitan existir en OSAP.

## CH-007 — Editar no sobrescribe

**Estado:** Aceptada.

Cada modificación de una obra propia produce una nueva revisión y sus ficheros correspondientes. Una partitura consultada en OSAP nunca se modifica desde Chorus.

## CH-008 — Modelo conceptual OSAP V6 para referencias externas

**Estado:** Aceptada.

Chorus respeta Work → Resource → File al leer el catálogo OSAP. No confunde esos objetos externos con las entidades propias de Chorus.

## CH-009 — Herramientas con biblioteca común

**Estado:** Aceptada.

Muse-encore y Chorus Study son herramientas dentro de la aplicación Chorus. Comparten identidad, biblioteca, autorización, base de datos y almacenamiento. Chorus Study no tiene usuarios ni biblioteca propios.

## CH-010 — Publicación OSAP posterior y explícita

**Estado:** Aceptada.

La primera etapa es de lectura de OSAP. La publicación de obras propias se diseñará posteriormente como una operación explícita que use los contratos oficiales OSAP; nunca sobrescribirá obras o Resources existentes.

## Decisiones técnicas pendientes

- Formato exacto y esquema versionado de ficheros propios.
- Motor de base de datos y estrategia de migraciones.
- Tecnología y política de respaldo del almacenamiento de ficheros.
- Contratos reales de osap-auth y lectura OSAP.
- Integración de Muse-encore.
- Contrato de entrada/salida del módulo Chorus Study.
- Compartición, permisos y publicación futura.
