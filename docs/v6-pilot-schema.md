# Esquema piloto V6 de Chorus

**Estado:** implementación de referencia añadida y validada en GitHub Actions (6 pruebas correctas); pendiente de ejecución local y revisión para el motor definitivo.  
**Ámbito:** Work, Resource y File propios de Chorus.  
**Motor:** SQLite únicamente como banco de pruebas portable. No decide el motor definitivo de Chorus ni el de OSAP Storage.

## 1. Objetivo

Convertir la decisión CH-011 en una restricción de persistencia verificable:

- cada Work tiene al menos un Resource;
- cada Resource tiene al menos un File;
- cada File pertenece a un único Resource;
- una Work/Resource/File incompleta no puede confirmarse como entidad musical válida.

El borrador de composición anterior al primer fichero queda fuera de estas tres tablas. Su modelo de edición se diseñará en la capa de aplicación, sin crear Works musicales incompletas.

## 2. Estrategia de integridad

SQLite no dispone de una restricción declarativa directa del tipo «cada fila padre debe tener al menos una fila hija». La migración utiliza referencias circulares diferidas:

- works.required_resource_id referencia un Resource de esa misma Work;
- resources.required_file_id referencia un File perteneciente a ese Resource;
- los dos vínculos se comprueban al confirmar la transacción (COMMIT), no después de cada INSERT.

Por eso el caso de creación válido es una única transacción:

1. insertar Work indicando el ID del Resource inicial;
2. insertar Resource indicando el ID del File inicial;
3. insertar File con su resource_id y puntero físico interno;
4. confirmar la transacción.

La misma regla se aplica a cada Resource adicional: debe insertarse junto con su primer File dentro de la transacción. Un fallo antes del commit permite rollback y no deja una entidad musical huérfana.

Los IDs son texto opaco en este banco de pruebas. No se impone prefijo, formato UUID, secuencia ni relación con IDs de OSAP.

## 3. Columnas incluidas

Se limita el esquema a conceptos documentados en la propuesta V6 y en la matriz de campos:

- Work: id, title, subtitle, catalogue, year, description, language, timestamps y el vínculo estructural al Resource requerido.
- Resource: id, work_id, resource_type, title, description, provenance, rights_license, timestamps y el vínculo estructural al File requerido.
- File: id, resource_id, name, mime_type, size_bytes, status, sha256, storage_pointer interno y timestamps.

No se añaden créditos, géneros, instrumentos, voces, personas, licencias detalladas, historial de versiones ni permisos en esta migración. Esas áreas requieren vocabularios y contratos propios antes de fijar tablas.

storage_pointer es un identificador físico opaco privado de Chorus; nunca debe aparecer en DTO públicos. sha256 solo es evidencia de integridad: admite duplicados y no es ID, clave única, ruta ni mecanismo de deduplicación.

## 4. Lo que esta migración no pretende resolver

- No es el DDL oficial de OSAP Storage.
- No fija el motor final de Chorus.
- No define todavía la serialización pública completa de V6.
- No implementa el borrador de composición sin fichero.
- No define revisiones/versiones ni su política de retención.
- No define los créditos de Work ni los créditos no compositivos de Resource.
- No define las clasificaciones normalizadas de Work/Resource.
- No crea tablas de usuario, espacio personal, grupos o permisos.
- No realiza operaciones de almacenamiento físico ni migraciones de datos.

## 5. Pruebas

tests/test_v6_schema.py verifica:
- cadena completa válida;
- rechazo de Work sin Resource al commit;
- rechazo de Resource sin File al commit;
- exigencia de File propio para cada Resource;
- imposibilidad de compartir un File entre Resources;
- ausencia de unicidad de negocio sobre SHA-256.

El workflow de GitHub Actions V6 schema tests se ha ejecutado correctamente: 6 passed. La ejecución CI valida este DDL y estas invariantes en SQLite; no sustituye las pruebas de integración con el motor definitivo.
