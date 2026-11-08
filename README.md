# Chorus

Chorus es una aplicación musical independiente de OSAP, con interfaz, API, base de datos y almacenamiento propios. Se conecta a OSAP para consultar y leer obras y recursos del catálogo compartido, pero no es una sección de su aplicación ni depende de su interfaz.

Su núcleo es el espacio personal del músico: biblioteca, obras propias, ficheros musicales, colecciones, borradores y herramientas de trabajo. La colaboración se incorpora cuando el usuario participa en grupos o decide compartir su trabajo.

## Dos procedencias de contenido

- **Catálogo OSAP:** Chorus puede buscar, consultar y leer Works y Resources publicados en OSAP. En esta primera etapa los mantiene como referencias externas; no necesita importar ni duplicar el catálogo.
- **Obras y trabajos personales:** se almacenan en el espacio propio de Chorus, como ficheros en el nuevo formato musical de Chorus, con sus metadatos, relaciones e índices en la base de datos propia. No necesitan existir previamente en OSAP.

La base de datos de Chorus es la autoridad sobre la organización personal y los trabajos privados. Los ficheros son el contenido musical; la base de datos registra su identidad, metadatos, versiones y relaciones.

## Principios

- **La persona y su biblioteca son el centro.** Una cuenta y una biblioteca personal, aunque el usuario participe en varios grupos.
- **Aplicación independiente.** Chorus tiene repositorio, configuración, API, base de datos y almacenamiento propios.
- **OSAP es el catálogo compartido, no la biblioteca privada.** Chorus consulta OSAP mediante APIs y conserva referencias externas.
- **Lo privado permanece en Chorus.** Las obras propias, borradores y versiones se guardan en su propio sistema de ficheros y base de datos.
- **Editar no sobrescribe.** Las modificaciones generan nuevas versiones o ficheros.
- **Las capacidades nacen de las relaciones.** No hay perfiles rígidos de músico, director o compositor.
- **La colaboración es opcional.** Chorus debe ser útil a una persona que solo quiere organizar, estudiar o escribir música.

## Herramientas

Chorus integra herramientas sobre la misma cuenta, biblioteca y modelo de datos. El generador de materiales de estudio coral existente se conserva como una herramienta/módulo de Chorus, no como una aplicación con usuarios o biblioteca independientes. Muse-encore se integra para editar partituras y trabajos personales.

## Primera entrega

1. Aplicación y autenticación propias, conectadas a osap-auth.
2. Base de datos y almacenamiento propios.
3. Escritorio y biblioteca personal.
4. Lectura y consulta de obras y Resources de OSAP.
5. Alta y gestión de obras propias en el nuevo formato de ficheros.
6. Integración de Muse-encore y del módulo Chorus Study Generator.

Los grupos, distribución y agenda se desarrollarán sobre esta base personal.

## Documentación

- [Arquitectura](docs/architecture.md)
- [Modelo de dominio](docs/domain-model.md)
- [Roadmap](docs/roadmap.md)
- [Decisiones de diseño](docs/decisions.md)
- [Módulo de estudio coral](docs/study-module.md)
- [Auditoría de la implementación anterior](docs/existing-implementation-assessment.md)
- [Revisión técnica del ScoreContract](docs/score-contract-review.md)
- [Contratos de integración](docs/integration-contracts.md)

## Estado

Proyecto en fase de definición y construcción de fundamentos. Los contratos reales de integración y el formato de ficheros propio deben concretarse antes de implementar persistencia definitiva.
