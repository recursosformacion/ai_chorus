# Roadmap de Chorus

Chorus es una aplicación independiente de OSAP, con base de datos y almacenamiento propios. Para sus obras propias utilizará el modelo y formato V6 de osap-storage; no desarrollará un formato paralelo.

## Fase 0 — Fundamentos

- [x] Definir propósito y principios.
- [x] Establecer la separación entre Chorus y OSAP.
- [x] Revisar el esquema actual y la documentación V6 de osap-storage; identificar que su código/DDL todavía es anterior a V6.
- [x] Fijar la cardinalidad Work → Resource → File: toda Work válida tiene Resource y todo Resource tiene File.
- [x] Crear un primer DDL piloto Work/Resource/File en SQLite, sin copiar el esquema anterior de Storage. Es una implementación de referencia, no una elección del motor definitivo.
- [x] Añadir seis tests de integridad y ejecutarlos en GitHub Actions: 6 passed.
- [ ] Elegir el motor definitivo y traducir/probar las restricciones en ese motor.
- [ ] Definir la persistencia de ficheros V6 en el almacenamiento propio de Chorus.
- [ ] Revisar contratos reales de autenticación y lectura de OSAP.
- [ ] Preparar configuración propia (osap.toml).
- [ ] Preparar pruebas de integridad, versiones, checksums y recuperación.

Criterio de salida: Chorus puede persistir obras propias con el formato/modelo V6 y consultar OSAP en modo lectura.

## Fase 1 — Escritorio y biblioteca personal

- [ ] Autenticación mediante osap-auth.
- [ ] Crear el espacio personal en Chorus DB.
- [ ] Escritorio y biblioteca.
- [ ] Buscar y leer Works/Resources de OSAP.
- [ ] Guardar referencias externas OSAP sin duplicar sus contenidos.
- [ ] Crear obras propias usando Work/Resource/File V6.
- [ ] Guardar ficheros con el formato V6 en la persistencia propia.
- [ ] Registrar metadatos, índices, versiones y relaciones en Chorus DB.
- [ ] Colecciones personales.

Criterio de salida: un usuario puede consultar OSAP y, de forma independiente, crear y organizar sus propias obras en Chorus usando V6.

## Fase 2 — Herramientas musicales

- [ ] Integrar Muse-encore con los ficheros V6 propios de Chorus.
- [ ] Crear y recuperar revisiones sin sobrescribir versiones anteriores.
- [ ] Integrar Chorus Study Generator como módulo de Chorus.
- [ ] Adaptar la entrada del generador desde una obra propia o una partitura OSAP autorizada.
- [ ] Guardar materiales generados en la persistencia propia de Chorus, respetando V6.
- [ ] Importar y exportar los formatos admitidos por V6.

El generador existente se conserva y adapta; no se convierte en una aplicación separada ni se posterga como un producto independiente.

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
- Pruebas de integridad entre registros y ficheros.
- Cada fase debe dejar una aplicación ejecutable y documentada.
