# Chorus

Chorus es una aplicación musical independiente de OSAP, con interfaz, API y base de datos propias. Se conecta a OSAP para consultar y leer obras y recursos del catálogo compartido, pero no es una sección de su aplicación ni depende de su interfaz.

Su núcleo es el espacio personal del músico: biblioteca, obras propias, ficheros musicales, colecciones, borradores y herramientas de trabajo. La colaboración se incorpora cuando el usuario participa en grupos o decide compartir su trabajo.

## Dos procedencias de contenido

- **Catálogo OSAP:** Chorus puede buscar, consultar y leer Works y Resources publicados en OSAP. En esta primera etapa los mantiene como referencias externas; no necesita importar ni duplicar el catálogo.
- **Obras y trabajos personales:** se guardan en la base de datos y el almacenamiento propios de Chorus, utilizando el modelo y el formato de ficheros de V6 de osap-storage. No se inventará un formato Chorus alternativo ni necesitarán existir previamente en el catálogo OSAP.

Chorus mantiene sus propios datos e instancia de persistencia, pero adopta el contrato V6 para representar Work, Resource y File. La separación de aplicaciones y bases de datos no implica crear formatos incompatibles.

## Principios

- **La persona y su biblioteca son el centro.** Una cuenta y una biblioteca personal, aunque el usuario participe en varios grupos.
- **Aplicación independiente.** Chorus tiene repositorio, configuración, API y base de datos propios.
- **Compatibilidad V6.** Las obras propias siguen el modelo Work → Resource → File de V6: toda Work válida tiene al menos un Resource y todo Resource al menos un File. Chorus será la primera implementación práctica para probar esta estructura antes de OSAP Storage.
- **OSAP es el catálogo compartido.** Chorus consulta OSAP mediante APIs y conserva referencias externas.
- **Lo privado permanece en Chorus.** Las obras propias, borradores y versiones se guardan en la persistencia propia, con formato V6.
- **Editar no sobrescribe.** Las modificaciones generan nuevas versiones o ficheros.
- **La colaboración es opcional.** Chorus debe ser útil a una persona que solo quiere organizar, estudiar o escribir música.

## Herramientas

Chorus integra herramientas sobre la misma cuenta, biblioteca y modelo de datos. El generador de materiales de estudio coral existente se conserva como una herramienta/módulo de Chorus, no como una aplicación con usuarios o biblioteca independientes. Muse-encore se integra para editar partituras y trabajos personales.

## Primera entrega

1. Aplicación y autenticación propias, conectadas a osap-auth.
2. Base de datos propia compatible con el modelo V6.
3. Escritorio y biblioteca personal.
4. Lectura y consulta de obras y Resources de OSAP.
5. Alta y gestión de obras propias usando el formato V6 de osap-storage.
6. Integración de Muse-encore y del módulo Chorus Study Generator.

Los grupos, distribución y agenda se desarrollarán sobre esta base personal.

## Documentación

- [Arquitectura](docs/architecture.md)
- [Modelo de dominio](docs/domain-model.md)
- [Roadmap](docs/roadmap.md)
- [Decisiones de diseño](docs/decisions.md)
- [Esquema piloto V6 y pruebas de integridad](docs/v6-pilot-schema.md)
- [Flujo API de creación y edición con OSAP y MuseEncore](docs/work-creation-api.md)
- [Módulo de estudio coral](docs/study-module.md)
- [Auditoría de la implementación anterior](docs/existing-implementation-assessment.md)
- [Revisión técnica del ScoreContract](docs/score-contract-review.md)
- [Contratos de integración](docs/integration-contracts.md)
- [Autenticación y audiencia de Chorus](docs/authentication-runtime.md)
- [API ejecutable y despliegue local](docs/api-runtime.md)
- [Interfaz HTML y configuración de Apache en desarrollo](docs/apache-dev.md)
- [Instalación y publicación local de MuseEncore](docs/muse-encore-install.md)
- [Auditoría de compatibilidad con OSAP Storage V6](docs/v6-storage-audit.md)

## Interfaz web

La primera interfaz estática se encuentra en `web/` (HTML, CSS y JavaScript sin framework ni build). Apache la sirve en **`http://chorus-app/`** desde el `DocumentRoot` y reenvía `/api/` a FastAPI en `127.0.0.1:9600`, siguiendo el patrón del entorno `osap-app`. El editor MuseEncore compilado se sirve aparte (en local, `http://127.0.0.1:9601`; ver `docs/muse-encore-install.md`). Incluye acceso con cuenta OSAP, búsqueda de obras, selección de una representación, creación de borradores y el intercambio MXL con MuseEncore. La configuración del VirtualHost está en [docs/apache-dev.md](docs/apache-dev.md). MuseEncore es una aplicación GitHub independiente: se clona con sus submódulos, se compila y Apache sirve su directorio `dist-editor`; ver [docs/muse-encore-install.md](docs/muse-encore-install.md).

## Estado

El repositorio ya contiene un primer servidor FastAPI ejecutable para Chorus: autenticación delegada a osap-auth, proxy de lectura OSAP, borradores, puente temporal a MuseEncore y carga MXL que materializa Work → Resource → File. SQLite y almacenamiento local privado son todavía el banco de pruebas; no son la persistencia de producción. La configuración de la URL real de osap-auth, OSAP API y MuseEncore es requisito de despliegue. En el piloto Chorus usa la audiencia predeterminada de osap-auth (`osap-api`) y delega la validación de cada sesión en /auth/me; una audiencia propia `chorus-api` queda como endurecimiento posterior (decisión CH-016). La suite completa del runtime y V6 ha superado 30 pruebas en GitHub Actions. La biblioteca personal ya tiene API (`/api/v1/library`, colecciones) y un listado en la web; las obras materializadas guardan su propietario y se verifican con `/api/v1/works/{id}/integrity`.
