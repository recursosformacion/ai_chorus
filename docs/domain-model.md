# Modelo de dominio de Chorus

Este documento define el modelo lógico inicial. Chorus mantiene su propia base de datos y almacenamiento, pero utiliza el modelo y el formato V6 de osap-storage para representar obras, recursos y ficheros. No se diseñará un formato musical alternativo.

## 1. Regla de propiedad

Cada usuario tiene un espacio personal permanente. Sus obras propias, recursos, ficheros, borradores, colecciones y versiones pertenecen a la instancia de Chorus. No requieren que exista una Work publicada en el catálogo OSAP.

Una persona también puede consultar obras OSAP y guardar referencias a ellas en su biblioteca. La referencia externa no transfiere la propiedad ni duplica el catálogo.

## 2. Modelo V6 en la persistencia propia de Chorus

Las obras propias se representarán usando las entidades y relaciones V6:
- **Work:** identidad de la obra.
- **Resource:** interpretación, arreglo o edición concreta.
- **File:** fichero físico asociado al Resource.

Chorus implementará estas estructuras en su propia base de datos y almacenamiento, siguiendo el esquema, formato, restricciones e invariantes definidos por V6 de osap-storage. No se deben inventar campos ni relaciones nuevas que contradigan ese contrato.

Los identificadores de las entidades propias pertenecen al ámbito de Chorus. No se presentarán como identificadores de catálogo OSAP ni se supondrá que OSAP ya conoce esas obras.

## 3. Referencias al catálogo OSAP

### OsapReference

Relación personal con una Work o Resource del catálogo externo.

Conceptualmente contiene:
- id local de la referencia;
- owner/workspace;
- identificador externo de Work y/o Resource;
- fecha de incorporación;
- caché opcional de presentación, marcada como tal.

La referencia no es una copia de la entidad canónica. En la primera etapa solo se consulta y lee OSAP.

## 4. Espacio personal y organización

### UserWorkspace

Espacio personal asociado uno a uno con el identificador de usuario de osap-auth.

### WorkspaceItem

Elemento visible en la biblioteca. Puede apuntar a una entidad V6 propia de Chorus o a una referencia externa OSAP.

### Collection / CollectionItem

Colecciones personales para organizar elementos de la biblioteca. Un elemento puede aparecer en varias colecciones.

### Draft / Revision

Trabajo en curso y sus revisiones. Deben conservar el formato V6 cuando representen Work, Resource o File; no se crea un segundo formato solo para los borradores. Las revisiones son inmutables y no alteran recursos externos OSAP.

## 5. Herramientas y materiales de estudio

### StudyProject

Contexto de trabajo del módulo Chorus Study, asociado a una Work/Resource propia o a una referencia OSAP.

### StudyMaterial

Material generado (por ejemplo, ejercicios o documentos de estudio), con referencia a su origen, tipo, versión del generador y ficheros resultantes. Su persistencia debe utilizar las estructuras V6 aplicables cuando corresponda; cualquier metadato específico del módulo se mantiene como extensión de aplicación sin alterar el núcleo V6.

El generador es un módulo de Chorus. No tiene identidad de usuario, biblioteca ni persistencia independiente.

## 6. Colaboración (fase posterior)

Group, GroupMembership, GroupSection y MembershipSection modelan agrupaciones, miembros, secciones y responsabilidades. La membresía no transfiere la propiedad de las obras ni da acceso general al espacio personal.

Event, EventResponse, Distribution y sus elementos/destinatarios modelan agenda y distribución. Compartir requiere permisos explícitos.

## 7. Invariantes

1. Chorus tiene base de datos y almacenamiento propios.
2. La representación de Work, Resource y File sigue el modelo V6 de osap-storage.
3. No existe un formato propietario Chorus alternativo para las obras musicales.
4. Toda Work musical válida tiene al menos un Resource.
5. Todo Resource válido tiene al menos un File; un Resource sin fichero no constituye una unidad musical persistida válida en Chorus.
6. La cadena obligatoria es Work → uno o más Resources → uno o más Files por Resource.
7. Una obra que todavía se está definiendo y aún no tiene un primer fichero puede permanecer en el proceso de edición como borrador incompleto, pero no se considera todavía una Work musical completa de la biblioteca V6.
8. Las obras privadas no reciben identificadores de catálogo OSAP.
9. Los ficheros y metadatos propios se persisten en la instancia Chorus.
10. Las referencias al catálogo OSAP son externas y de solo lectura en la primera etapa.
11. Las revisiones no destruyen versiones anteriores.
12. El módulo Chorus Study utiliza la biblioteca y persistencia comunes.
13. La pertenencia a un grupo no concede acceso a toda la biblioteca personal.
14. La autorización se comprueba en servidor en cada lectura y escritura.
