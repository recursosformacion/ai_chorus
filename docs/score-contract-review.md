# Revisión técnica inicial del generador Chorus Study

## 1. Paquete localizado

En `recursosformacion/AI_GAMEPC2/src/chorus` se localizaron:
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

Tests localizados: `test_domain.py`, `test_generate_materials.py`, `test_score_contract.py` y `test_web.py`.

## 2. Valor reutilizable

El generador tiene límites reconocibles: StudyMaterial/MaterialType expresan resultados; GenerateMaterialsUseCase coordina generadores; ExerciseGenerator produce material estructural; el contrato JSON desacopla el transporte de las clases Python OSAP.

Se conserva como módulo funcional Chorus Study dentro de la aplicación Chorus. No tendrá una biblioteca ni persistencia independiente.

## 3. Límites de ScoreContract

El `ScoreContract` es una entrada especializada para generar materiales a partir de un Score validado. No representa:
- Work canónica completa;
- Resource o File V6;
- metadatos, relaciones o versiones completas de la persistencia propia;
- derechos, licencia, uploader o procedencia;
- borradores, revisiones o publicación.

El bridge reconstruye un Score con identificador marcador y contenido vacío. Puede servir al generador que consume los campos estructurales, pero no es un modelo de biblioteca o edición.

**Conclusión:** mantener ScoreContract como contrato de entrada del generador si las pruebas lo avalan. No usarlo como contrato general de Chorus ni como sustituto del modelo V6.

## 4. Adaptación al modelo de contenido

Chorus tendrá dos fuentes de entrada:
- Work/Resource/File propios, almacenados en su instancia de Chorus conforme al modelo y formato V6.
- Resource/File OSAP consultado mediante API y con acceso autorizado.

Un adaptador de Chorus obtiene el contenido musical, valida/normaliza los datos necesarios y construye el contrato de entrada del generador. El módulo no consulta directamente la base de datos Chorus ni gestiona autenticación.

El resultado StudyMaterial y sus ficheros se guardan en la persistencia propia de Chorus, usando el modelo/formato V6 donde corresponda, asociados a la obra/revisión de origen.

## 5. Acoplamiento observado

GenerateMaterialsUseCase tipa Score de OSAP mediante TYPE_CHECKING, mientras ExerciseGenerator importa QualityReport de OSAP en tiempo de ejecución. La independencia no es completa. Antes de extraer, hay que decidir si se normalizan los datos de calidad en el contrato o se mantiene un adaptador explícito.

## 6. Estado de verificación

Revisión estática de archivos accesibles en GitHub. No se han ejecutado tests, no se ha probado la web localmente y no se ha verificado contra una instancia viva de OSAP. No se declara que el paquete esté listo para extracción.

Siguientes comprobaciones:
1. Ejecutar la suite existente.
2. Revisar configuración y endpoints OSAP usados.
3. Verificar el contrato de Score vigente.
4. Diseñar adaptadores para el contenido V6 propio y el contenido OSAP.
5. Extraer el generador con pruebas de equivalencia.
