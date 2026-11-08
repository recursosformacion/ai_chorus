# Revisión técnica inicial de Chorus preexistente

## 1. Paquete localizado

Inventario de `src/chorus` en `recursosformacion/AI_GAMEPC2`:

- `domain/material_type.py`
- `domain/study_material.py`
- `application/use_cases/generate_materials.py`
- `ports/study_material_generator.py`
- `infrastructure/generators/exercise_generator.py`
- `infrastructure/generators/pdf_generator.py`
- `infrastructure/generators/audio_generator.py`
- `infrastructure/exporters/pdf_exporter.py`
- `contract/model.py`
- `contract/bridge.py`
- `bootstrap/*`
- `web/app.py`

Pruebas localizadas:
- `tests/chorus/test_domain.py`
- `tests/chorus/test_generate_materials.py`
- `tests/chorus/test_score_contract.py`
- `tests/chorus/test_web.py`

## 2. Valor reutilizable

El módulo de generación es pequeño y tiene límites reconocibles:
- `StudyMaterial` y `MaterialType` expresan el resultado.
- `GenerateMaterialsUseCase` delega en generadores registrados.
- `ExerciseGenerator` produce un resumen estructural sin inventar datos.
- El contrato JSON desacopla el transporte de las clases Python de OSAP.

Esto permite conservar la generación de materiales como una capacidad del nuevo Chorus, sin convertirla en el centro de la biblioteca personal.

## 3. Límites del contrato actual

El `ScoreContract` actual es un contrato de entrada específico para generar materiales a partir de un Score ya validado. Incluye título, compositor, estructura resumida, calidad y diagnósticos.

No representa:
- una Work canónica con identidad estable;
- un Resource concreto del catálogo;
- el File físico que pertenece al Resource;
- derechos, licencia, uploader ni procedencia;
- el identificador estable del Resource que el usuario añade a su biblioteca;
- una operación de edición, borrador o publicación.

Además, el bridge reconstruye un Score con identificador marcador y contenido vacío. Eso es aceptable para el generador que consume los campos estructurales, pero no puede convertirse en el modelo general de biblioteca o edición.

**Conclusión:** mantener `ScoreContract` para el caso de uso de generación, si supera las pruebas y la revisión de compatibilidad; no reutilizarlo como contrato principal de integración de Chorus con OSAP.

## 4. Acoplamiento observado

`GenerateMaterialsUseCase` tipa el Score de OSAP mediante TYPE_CHECKING. Sin embargo, `ExerciseGenerator` importa `QualityReport` desde OSAP en tiempo de ejecución y lo usa para leer dimensiones de calidad.

Por tanto, la independencia del paquete no es absoluta en ejecución. Para extraer el generador puede convenir que el contrato incluya los datos de calidad ya normalizados y que el generador consuma ese contrato/dto, o mantener un adaptador explícito. La decisión se tomará después de ejecutar pruebas y verificar el productor real de OSAP.

## 5. Diferencia con el modelo de producto nuevo

El nuevo Chorus necesita dos flujos distintos:

### Biblioteca y trabajo personal

`Work` → `Resource` → `File` (referencias de OSAP)  
`WorkspaceItem` → organización personal  
`Draft` → `DraftRevision` → archivo privado

### Generación de materiales

`Resource` / contenido autorizado → adaptador de entrada → datos musicales validados → generador → `StudyMaterial`

No se debe confundir el Resource que el usuario organiza/edita con el Score resumido que un generador necesita para producir un ejercicio.

## 6. Estado de verificación

Esta revisión es una lectura estática de los archivos accesibles en GitHub. No se han ejecutado tests, no se ha probado la web localmente y no se ha verificado contra una instancia viva de OSAP. No se declara todavía que el paquete esté listo para extracción.

Siguientes comprobaciones:
1. Obtener una copia de trabajo del repositorio OSAP o usar su entorno de desarrollo.
2. Ejecutar `pytest tests/chorus` y los chequeos configurados por el proyecto.
3. Revisar `web/app.py`, configuración y endpoints OSAP línea por línea.
4. Confirmar si `GET /api/v1/sessions/{session_id}/score-contract` sigue existiendo y si es un contrato de generación, no de biblioteca.
5. Definir y versionar los contratos de biblioteca y edición contra las APIs reales de V6.
