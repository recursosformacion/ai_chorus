# Roadmap de Chorus

El desarrollo se organiza por entregas verticales. Chorus es una aplicación independiente de OSAP y debe disponer de su propia base de datos y almacenamiento desde el principio.

## Fase 0 — Fundamentos

- [x] Definir propósito y principios.
- [x] Establecer la separación entre Chorus y OSAP.
- [ ] Especificar el formato versionado de ficheros musicales propio de Chorus.
- [ ] Definir el esquema inicial de Chorus DB y la relación con los ficheros.
- [ ] Revisar contratos reales de autenticación y lectura de OSAP.
- [ ] Elegir stack y preparar configuración propia (`osap.toml`).
- [ ] Preparar pruebas de persistencia, integridad y recuperación.

Criterio de salida: formato y modelo de datos definidos; aplicación conectable a osap-auth y capaz de consultar OSAP en modo lectura.

## Fase 1 — Escritorio y biblioteca personal

- [ ] Autenticación mediante osap-auth.
- [ ] Crear el espacio personal en Chorus DB.
- [ ] Escritorio y biblioteca.
- [ ] Buscar y leer Works/Resources de OSAP.
- [ ] Guardar referencias externas OSAP sin duplicar sus contenidos.
- [ ] Crear obras propias en Chorus.
- [ ] Guardar obras propias como ficheros en el nuevo formato.
- [ ] Registrar metadatos, índices, versiones y checksums en Chorus DB.
- [ ] Colecciones personales.

Criterio de salida: un usuario puede consultar OSAP y, de forma independiente, crear y organizar sus propias obras en Chorus.

## Fase 2 — Herramientas musicales

- [ ] Integrar Muse-encore con los ficheros propios de Chorus.
- [ ] Crear y recuperar revisiones sin sobrescribir versiones anteriores.
- [ ] Integrar Chorus Study Generator como módulo de Chorus.
- [ ] Adaptar la entrada del generador desde una obra propia o una partitura OSAP autorizada.
- [ ] Guardar materiales generados en Chorus File Store y sus metadatos en Chorus DB.
- [ ] Exportar/importar los formatos musicales definidos.

El generador existente se conserva y adapta; no se convierte en una aplicación separada ni se posterga como un producto de IA independiente.

Criterio de salida: el usuario puede escribir/editar música y generar materiales de estudio dentro del mismo espacio Chorus.

## Fase 3 — Compartir y publicar (posterior)

- [ ] Compartir obras propias con usuarios o grupos.
- [ ] Definir permisos y distribución.
- [ ] Diseñar, como operación explícita, la publicación de obras propias en OSAP.
- [ ] Resolver identidad Work y creación de Resource mediante los contratos oficiales OSAP.

La publicación no forma parte del flujo inicial de lectura y no sobrescribe contenido OSAP.

## Fase 4 — Agrupaciones y agenda

- [ ] Grupos, membresías, responsabilidades y secciones.
- [ ] Repertorio de grupo mediante referencias y elementos compartidos.
- [ ] Distribución de partituras.
- [ ] Ensayos, conciertos, reuniones y confirmaciones.

## Fase 5 — Asistencia musical ampliada

- [ ] Análisis armónico y estructural.
- [ ] Explicación contextual de partituras.
- [ ] Ayuda de instrumentación, adaptación y composición.
- [ ] Funciones de aprendizaje y práctica.

## Criterios transversales

- Ningún test fallido se acepta como estado terminado.
- No escribir en bases de datos de producción OSAP durante esta etapa.
- Pruebas de contrato para los servicios externos.
- Pruebas de integridad entre registros de Chorus DB y ficheros.
- Cada fase debe dejar una aplicación ejecutable y documentada.
