# Modelo de dominio de Chorus

Este documento define el modelo lógico inicial, no todavía el esquema SQL definitivo. Chorus mantiene su propia base de datos y su propio almacenamiento de ficheros.

## 1. Regla de propiedad

Cada usuario tiene un espacio personal permanente. Sus obras propias, ficheros, borradores, colecciones y versiones pertenecen a Chorus y al usuario. No requieren una Work publicada en OSAP.

Una persona puede consultar obras OSAP y guardar referencias a ellas en su biblioteca. Esa referencia externa no convierte el contenido en una obra privada ni duplica el catálogo.

## 2. Ámbitos de contenido

### OsapWorkReference

Referencia a una Work o Resource externa de OSAP. Guarda el identificador externo y, cuando haga falta, una pequeña caché de presentación marcada como caché.

Campos conceptuales:
- id
- workspace_id
- osap_work_id
- osap_resource_id (nullable)
- cached_display_data (nullable)
- cached_at (nullable)
- added_at

La referencia no es propietaria del contenido OSAP. En esta primera etapa solo se consulta y lee.

### PersonalWork

Obra o proyecto musical propio del usuario en Chorus. Tiene identidad local, aunque todavía no se haya publicado en OSAP.

Campos conceptuales:
- id
- workspace_id
- title
- description
- metadata
- current_revision_id
- created_at
- updated_at
- visibility

PersonalWork no equivale a una Work canónica OSAP. No se le asigna un identificador OSAP ficticio.

### PersonalWorkFile

Fichero que contiene una realización o parte del contenido de una PersonalWork en el formato propio versionado de Chorus.

Campos conceptuales:
- id
- personal_work_id
- revision_id
- file_role
- format
- format_version
- storage_key
- checksum
- size
- created_at

El fichero reside en Chorus File Store. La base de datos conserva su referencia, integridad, versión y metadatos; no se presupone guardar todos los bytes como columnas SQL.

### PersonalWorkRevision

Versión inmutable de una PersonalWork.

Campos conceptuales:
- id
- personal_work_id
- revision_number
- metadata_snapshot
- created_by_user_id
- created_at
- change_note

Cada revisión apunta a uno o varios PersonalWorkFiles. Una edición no destruye versiones anteriores.

## 3. Espacio personal y organización

### UserWorkspace

Espacio personal asociado uno a uno con el identificador de usuario de osap-auth.

### WorkspaceItem

Elemento visible en la biblioteca. Puede ser una referencia OsapWorkReference o una PersonalWork. La relación no implica duplicar ficheros OSAP.

### Collection / CollectionItem

Colecciones personales para organizar WorkspaceItems. Un elemento puede aparecer en varias colecciones.

### Draft

Trabajo en curso asociado a una PersonalWork o derivado de una referencia OSAP. Los borradores y revisiones se guardan en Chorus, nunca sobre el original externo.

## 4. Herramientas y materiales de estudio

### StudyProject

Contexto de trabajo del módulo Chorus Study, asociado a una PersonalWork o a una referencia OSAP.

### StudyMaterial

Material generado (por ejemplo, ejercicios o documentos de estudio), con referencia a su origen, tipo, versión del generador y ficheros resultantes.

El generador es un módulo de la aplicación Chorus. No tiene identidad de usuario, biblioteca ni persistencia independiente. Los materiales resultantes se guardan en el espacio Chorus.

## 5. Colaboración (fase posterior)

Group, GroupMembership, GroupSection y MembershipSection modelan agrupaciones, miembros, secciones y responsabilidades. La membresía no transfiere la propiedad de PersonalWork ni da acceso general al UserWorkspace.

Event, EventResponse, Distribution y sus elementos/destinatarios modelan agenda y distribución. Compartir requiere permisos explícitos.

## 6. Invariantes

1. Cada usuario tiene un único UserWorkspace.
2. Chorus tiene base de datos y almacenamiento propios.
3. Una referencia OSAP no es una PersonalWork.
4. Chorus no crea ni inventa identificadores OSAP para obras privadas.
5. El contenido de PersonalWork se conserva en ficheros del almacenamiento Chorus.
6. La base de datos registra metadatos, versiones, relaciones, integridad y referencias a ficheros.
7. Las revisiones son inmutables y una edición no destruye el fichero anterior.
8. La consulta OSAP es de lectura en esta primera etapa.
9. La pertenencia a un grupo no concede acceso a toda la biblioteca personal.
10. El módulo Chorus Study usa la biblioteca y el almacenamiento comunes.
11. La autorización se comprueba en servidor en cada lectura y escritura.
