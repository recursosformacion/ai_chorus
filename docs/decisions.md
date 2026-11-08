# Decisiones de diseño de Chorus

## CH-001 — Chorus es una aplicación independiente

**Estado:** Aceptada.

Chorus tiene interfaz, API, repositorio, configuración y base de datos propios. No es una sección de la aplicación OSAP. Se conecta a servicios externos mediante APIs.

## CH-002 — La biblioteca personal es el núcleo

**Estado:** Aceptada.

Chorus debe ser útil para un músico individual. La colaboración no es requisito para usarlo.

## CH-003 — Un espacio personal por usuario

**Estado:** Aceptada.

Cada identidad de osap-auth se vincula a un único espacio personal permanente en Chorus.

## CH-004 — Capacidades contextuales

**Estado:** Aceptada.

No hay perfiles globales excluyentes de músico, director o compositor. Las responsabilidades dependen del grupo y del contexto.

## CH-005 — OSAP es catálogo externo; Chorus lo consulta en lectura

**Estado:** Aceptada.

En la primera etapa Chorus puede buscar, consultar y leer Works y Resources OSAP. Conserva referencias externas y no modifica el catálogo ni escribe en su base de datos.

## CH-006 — Las obras propias usan el modelo y formato V6

**Estado:** Aceptada.

Las obras propias del usuario se guardan en la base de datos y almacenamiento propios de Chorus, utilizando el modelo y formato V6 de osap-storage (Work, Resource y File). No se desarrollará un formato propietario Chorus alternativo. Los identificadores de esas entidades pertenecen a la instancia Chorus y no se presentarán como identificadores del catálogo OSAP.

## CH-007 — Editar no sobrescribe

**Estado:** Aceptada.

Cada modificación conserva las versiones anteriores y crea la revisión/fichero correspondiente conforme a las reglas V6. Una partitura consultada en OSAP nunca se modifica desde Chorus.

## CH-008 — Persistencia propia, contrato V6 compartido

**Estado:** Aceptada.

Chorus mantiene su propia base de datos y almacenamiento. La independencia de la aplicación no implica duplicar ni modificar el formato V6. La implementación debe ajustarse al esquema y las restricciones reales de osap-storage.

## CH-009 — Herramientas con biblioteca común

**Estado:** Aceptada.

Muse-encore y Chorus Study son herramientas dentro de la aplicación Chorus. Comparten identidad, biblioteca, autorización, base de datos y almacenamiento. Chorus Study no tiene usuarios ni biblioteca propios.

## CH-010 — Publicación OSAP posterior y explícita

**Estado:** Aceptada.

La primera etapa es de lectura de OSAP. La publicación de obras propias se diseñará posteriormente como una operación explícita que use los contratos oficiales OSAP; nunca sobrescribirá obras o Resources existentes.

## Decisiones técnicas pendientes

- Contrastar el esquema V6 completo y sus invariantes con el código y documentación actuales de osap-storage.
- Motor de base de datos y estrategia de migraciones para la instancia propia de Chorus.
- Tecnología y política de respaldo del almacenamiento propio.
- Contratos reales de osap-auth y lectura OSAP.
- Integración de Muse-encore.
- Contrato de entrada/salida del módulo Chorus Study.
- Compartición, permisos y publicación futura.


## CH-011 — Cardinalidad obligatoria Work → Resource → File

**Estado:** Aceptada.

Una Work musical no está completa ni tiene entidad útil en la biblioteca si no dispone de al menos un Resource, y cada Resource debe contener al menos un File. La estructura válida es Work → uno o más Resources → uno o más Files por Resource. Un Resource sin File no se considera un Resource musical válido en Chorus.

Durante la composición el usuario puede definir una obra antes de grabar su primer fichero. Ese estado de trabajo puede mantenerse como borrador incompleto, pero no se confunde con una Work musical completa del modelo V6. Al guardar el primer fichero se materializa la cadena Work/Resource/File.

Chorus implementará y probará esta regla como primera implementación práctica del modelo V6, antes de que OSAP Storage lo despliegue. No se adoptan para Chorus los textos antiguos que permiten Work sin Resource o Resource sin File.
