# Módulo Chorus Study

## Propósito

Chorus Study es la herramienta de estudio coral integrada en Chorus. Reutiliza el generador existente localizado en `AI_GAMEPC2/src/chorus`, pero no es una aplicación independiente: no tiene usuarios, autenticación, biblioteca ni base de datos propios.

## Relación con Chorus

- Utiliza la identidad y los permisos de Chorus.
- Recibe obras desde la biblioteca común: una PersonalWork del usuario o una partitura/Resource OSAP que el usuario tenga derecho a consultar.
- No crea una segunda copia de la biblioteca.
- Guarda proyectos, resultados y ficheros generados en el almacenamiento de Chorus.
- Registra metadatos, origen, tipo de material y versión del generador en Chorus DB.

## Flujo lógico

1. El usuario selecciona una obra de su biblioteca.
2. Chorus obtiene el contenido musical desde sus ficheros propios o, cuando proceda, desde OSAP mediante su API de lectura.
3. Un adaptador convierte el contenido a un contrato de entrada específico para el generador.
4. El generador produce ejercicios y materiales.
5. Chorus persiste los resultados como StudyMaterial y ficheros asociados a la obra de origen.
6. El usuario consulta, descarga, revisa o comparte esos materiales desde Chorus.

## Contrato de entrada

El `ScoreContract` existente se considera un contrato especializado para la generación, no el modelo de la biblioteca ni un sustituto de Work, Resource o File. Puede mantenerse si las pruebas y la revisión técnica lo avalan.

La frontera del módulo debe recibir datos musicales normalizados y validados. Los adaptadores de Chorus resuelven el origen del contenido y las dependencias con OSAP; el generador no debe gestionar autenticación ni consultar directamente la base de datos de Chorus.

## Persistencia

- Los metadatos del proyecto y de cada material se guardan en Chorus DB.
- Los PDF, audios u otros resultados se guardan en Chorus File Store.
- Cada material conserva referencia a la obra/revisión de origen y a la versión del generador.
- Los resultados no se guardan en una biblioteca separada.

## Extracción del código existente

No copiar ni mover todavía el paquete desde `AI_GAMEPC2`. Antes:
1. Inventariar código, dependencias y configuración.
2. Ejecutar la suite de tests y registrar el resultado real.
3. Confirmar los contratos OSAP usados.
4. Aislar los adaptadores de entrada/salida.
5. Extraer el generador como módulo de Chorus, preservando su comportamiento mediante pruebas.
6. Retirar la implementación anterior solo después de verificar la extracción y sus consumidores.

La auditoría y revisión del contrato se detallan en [existing-implementation-assessment.md](existing-implementation-assessment.md) y [score-contract-review.md](score-contract-review.md).
