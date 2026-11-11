# Roadmap de Chorus

Chorus es una aplicación independiente de OSAP, con base de datos y almacenamiento propios. Para sus obras propias utilizará el modelo y formato V6 de osap-storage; no desarrollará un formato paralelo.

## Fase 0 — Fundamentos

El primer runtime está en la rama feature/chorus-api-runtime. Su estado es piloto: la suite ampliada debe quedar verde en CI antes de integrar la rama.

- [x] Definir propósito y principios.
- [x] Establecer la separación entre Chorus y OSAP.
- [x] Revisar el esquema actual y la documentación V6 de osap-storage; identificar que su código/DDL todavía es anterior a V6.
- [x] Fijar la cardinalidad Work → Resource → File: toda Work válida tiene Resource y todo Resource tiene File.
- [x] Crear un primer DDL piloto Work/Resource/File en SQLite, sin copiar el esquema anterior de Storage. Es una implementación de referencia, no una elección del motor definitivo.
- [x] Añadir seis tests de integridad y ejecutarlos en GitHub Actions: 6 passed.
- [x] Definir el flujo API de CreationDraft previo a la primera Work V6.
- [x] Añadir persistencia SQLite de borradores y tokens temporales del editor.
- [x] Definir el contrato API para búsqueda OSAP, selección de original, apertura de MuseEncore y carga MXL.
- [x] Añadir pruebas de integridad para borradores; 12 pruebas V6 + borradores superadas en GitHub Actions.
- [x] Implementar un primer servidor FastAPI y los endpoints de catálogo, borradores, selección OSAP, apertura MuseEncore y carga MXL.
- [x] Implementar almacenamiento local privado de ficheros para el piloto; queda pendiente sustituirlo por el backend definitivo.
- [x] Revisar contratos reales de autenticación y lectura OSAP; documentar la validación delegada en osap-auth /auth/me.
- [x] Preparar configuración propia (osap.toml.example), sin secretos.
- [x] Preparar pruebas de integridad, versiones, checksums y recuperación (endpoint `/api/v1/works/{id}/integrity`, 30 pruebas).

Criterio de salida: Chorus puede persistir obras propias con el formato/modelo V6 y consultar OSAP en modo lectura.

## Fase 1 — Escritorio y biblioteca personal

- [x] Implementar login/refresh/logout delegados a osap-auth; con validación remota de perfil y onboarding mediante /auth/me.
- [x] Crear el espacio personal en Chorus DB (`works.owner_sub`, `library_items`).
- [ ] Escritorio y biblioteca.
- [x] Implementar proxy de búsqueda y lectura de representaciones OSAP mediante API.
- [x] Guardar referencias externas OSAP sin duplicar sus contenidos (API de biblioteca).
- [x] Materializar Work/Resource/File desde una carga MXL con transacción SQLite; pendiente motor definitivo.
- [ ] Guardar ficheros con el formato V6 en la persistencia propia.
- [ ] Registrar metadatos, índices, versiones y relaciones en Chorus DB.
- [x] Colecciones personales (API y listado web).

Criterio de salida: un usuario puede consultar OSAP y, de forma independiente, crear y organizar sus propias obras en Chorus usando V6.

## Fase 2 — Herramientas musicales

- [x] Verificar la integración posible con MuseEncore: apertura mediante ?url y exportación .mxl; no dispone de callback remoto de exportación documentado.
- [x] Implementar entrega temporal a MuseEncore y recepción/validación de .mxl por API.
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
