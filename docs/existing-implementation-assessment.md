# Auditoría del desarrollo Chorus preexistente

## 1. Hallazgo

El repositorio `ai_chorus` se creó vacío. Existía una implementación parcial en `recursosformacion/AI_GAMEPC2/src/chorus`, con pruebas en `tests/chorus` y documentación asociada.

Referencias:
- [Código](https://github.com/recursosformacion/AI_GAMEPC2/tree/main/src/chorus)
- [Tests](https://github.com/recursosformacion/AI_GAMEPC2/tree/main/tests/chorus)
- [Visión anterior](https://github.com/recursosformacion/AI_GAMEPC2/blob/main/docs/chorus-vision.md)

## 2. Qué existe según el árbol revisado

- Paquete Python organizado en domain, application, ports, infrastructure, bootstrap, contract y web.
- `ScoreContract` serializable y versionado.
- Adaptadores entre el contrato y el Score de OSAP.
- `GenerateMaterialsUseCase` y `ExerciseGenerator`.
- Generadores/exportadores PDF y audio.
- Aplicación web FastAPI mínima y pruebas de dominio, generación, contrato y web.

La revisión previa fue estática. No se han ejecutado aquí los tests y no se afirma que estén pasando.

## 3. Papel en el nuevo Chorus

Esta implementación es el núcleo del módulo Chorus Study: una herramienta integrada en la aplicación Chorus para generar materiales de estudio coral.

No es una aplicación independiente ni tendrá usuarios, biblioteca, autenticación o base de datos propios. Utilizará la biblioteca y la persistencia comunes de Chorus.

El generador es una capacidad especializada. No representa el producto Chorus completo ni el modelo general de biblioteca.

## 4. Contrato de entrada

El `ScoreContract` actual es un contrato de entrada específico para generación a partir de un Score validado. No representa Work, Resource, File ni una revisión V6 completa.

Debe mantenerse como contrato especializado si supera la revisión y las pruebas. Los adaptadores de Chorus convertirán el contenido de una obra propia representada según V6 o de un Resource OSAP autorizado al formato de entrada que necesite el generador.

## 5. Estrategia de reutilización

1. Inspeccionar todos los módulos y dependencias reales.
2. Revisar el contrato y los adaptadores OSAP.
3. Ejecutar los tests en el entorno del repositorio original y registrar resultados.
4. Aislar la lógica de generación de la web y de dependencias de persistencia.
5. Integrar el módulo en `ai_chorus`, usando la persistencia propia de Chorus y el modelo/formato V6 para sus resultados cuando corresponda.
6. Preservar el comportamiento mediante pruebas de equivalencia.
7. No retirar el código original hasta verificar la extracción y sus consumidores.

No copiar ni mover código todavía. No mantener dos implementaciones activas del generador.

## 6. Repositorios

- `AI_GAMEPC2` conserva el código existente mientras se audita y prepara una extracción segura.
- `ai_chorus` es el destino de la aplicación Chorus independiente y del módulo integrado Chorus Study.
- No se modifica ni elimina código de OSAP durante esta fase documental.

## 7. Pendientes

- [ ] Inventariar ficheros y dependencias.
- [ ] Leer los módulos completos.
- [ ] Ejecutar tests y registrar el resultado real.
- [ ] Confirmar contratos OSAP usados.
- [ ] Diseñar adaptadores desde entidades/ficheros V6 propios y referencias OSAP.
- [ ] Extraer el generador como módulo de Chorus.
