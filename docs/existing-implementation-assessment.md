# Auditoría del desarrollo Chorus preexistente

## 1. Hallazgo

El repositorio `ai_chorus` se creó vacío. Sin embargo, Chorus ya tenía una implementación parcial dentro de `recursosformacion/AI_GAMEPC2`, en `src/chorus/`, junto con pruebas en `tests/chorus/` y documentación de producto en `docs/chorus-*.md`.

Referencias:
- Código: https://github.com/recursosformacion/AI_GAMEPC2/tree/main/src/chorus
- Tests: https://github.com/recursosformacion/AI_GAMEPC2/tree/main/tests/chorus
- Visión anterior: https://github.com/recursosformacion/AI_GAMEPC2/blob/main/docs/chorus-vision.md
- Producto anterior: https://github.com/recursosformacion/AI_GAMEPC2/blob/main/docs/chorus-product.md
- Separación anterior: https://github.com/recursosformacion/AI_GAMEPC2/blob/main/docs/chorus-separation.md
- Web anterior: https://github.com/recursosformacion/AI_GAMEPC2/blob/main/docs/chorus-web.md

## 2. Qué existe según la documentación y el árbol del repositorio

La implementación previa incluye:
- Paquete Python `src/chorus/` organizado en `domain`, `application`, `ports`, `infrastructure`, `bootstrap`, `contract` y `web`.
- Contrato serializable `ScoreContract`, con versión de esquema.
- Adaptadores para convertir entre el contrato y el objeto `Score` del dominio OSAP.
- Caso de uso `GenerateMaterialsUseCase`.
- Generador `ExerciseGenerator` para producir un material de estudio.
- Aplicación web FastAPI mínima, con endpoints documentados `/generate`, `/from-osap` y entrada provisional `/generate-file`.
- Tests de dominio, generación, contrato y web.

La documentación del repositorio afirma que el flujo de generación y el contrato se encuentran probados. Esta auditoría no ha ejecutado esos tests; el estado de pruebas debe verificarse localmente antes de reutilizar o extraer código.

## 3. Diferencia de alcance

El producto anterior se definía como Chorus Study Generator: aplicación especializada que recibe un Score validado por OSAP y genera materiales de estudio coral.

El producto ahora acordado es más amplio: un espacio de trabajo musical personal, útil para un músico individual y ampliable a colaboración. Incluye:
- escritorio y biblioteca personal;
- colecciones y repertorios;
- recursos privados;
- borradores y revisiones;
- edición MusicXML/MXL con Muse-encore;
- búsqueda e incorporación de Resources de OSAP;
- contactos, agrupaciones, secciones, distribuciones y agenda;
- asistencia musical e IA.

El generador de materiales anterior puede convertirse en una capacidad o módulo de Chorus, pero no define por sí solo el producto completo.

## 4. Estrategia de reutilización

No se debe copiar `src/chorus` sin revisar ni reescribirlo desde cero.

Revisión requerida:
1. Inspeccionar todos los módulos y sus dependencias reales.
2. Revisar el contrato `ScoreContract` y su relación con el modelo V6 Work → Resource → File.
3. Verificar los endpoints OSAP usados por el adaptador y confirmar su vigencia.
4. Revisar los tests y ejecutarlos en el entorno del repositorio original.
5. Identificar el código de generación de materiales que puede mantenerse como módulo.
6. Separar ese módulo de las responsabilidades nuevas de biblioteca, borradores y colaboración.
7. Definir la extracción física al repositorio `ai_chorus` sin romper el producto OSAP ni su circuito actual.

## 5. Decisión provisional sobre repositorios

- `AI_GAMEPC2` conserva el código existente hasta completar la auditoría y preparar una extracción segura.
- `ai_chorus` es el destino del producto Chorus independiente y de su nueva arquitectura.
- No se modifica ni elimina código del repositorio OSAP durante esta fase de documentación.
- No se mantiene una segunda implementación del generador en paralelo.
- La extracción se hará mediante una secuencia revisable y pruebas de equivalencia, no mediante copia manual sin trazabilidad.

## 6. Pendientes inmediatos

- [ ] Inventariar ficheros de `src/chorus` y dependencias.
- [ ] Leer los módulos de dominio, aplicación, contrato, infraestructura y web.
- [ ] Contrastar `ScoreContract` con la API actual de OSAP y el modelo V6.
- [ ] Revisar configuración, packaging y ejecución local.
- [ ] Ejecutar tests y registrar resultados reales.
- [ ] Proponer el límite del módulo reutilizable de generación de materiales.
- [ ] Diseñar la extracción y el primer esqueleto funcional del escritorio personal.
