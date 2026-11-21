# Scripts de un solo uso (archivo histórico)

Estos scripts se ejecutaron puntualmente durante el desarrollo de la versión 0.15/0.16
y **ya han sido aplicados o superados**. No forman parte del árbol de trabajo: se
conservan aquí únicamente como referencia histórica, no para ejecutarlos.

No modifiques estos archivos ni los reactives. Si hace falta un cambio equivalente,
escríbelo como migración en `migrations/mysql/` o como script en `scripts/`.

## `one-off-patches/`

Ediciones automatizadas de código fuente: abrían `app/main.py` o `web/app.js`, hacían
`str.replace` y reescribían el archivo. Ejecutarlos hoy volvería a inyectar código
antiguo y podría corromper el archivo.

| Patrón                     | Qué hacía                                                                       |
| -------------------------- | ------------------------------------------------------------------------------- |
| `add_*.py`                 | Insertaban endpoints, modelos Pydantic o prints de depuración en `app/main.py`. |
| `insert_*.py`              | Insertaban bloques de endpoints y código JS en `web/app.js`.                    |
| `fix_*.py`                 | Corregían fragmentos concretos (rutas de subida, backslashes, tests, sintaxis). |
| `move_*.py`, `remove_*.py` | Movían o eliminaban bloques de código.                                          |
| `update_*.py`              | Parcheaban `scripts/rebuild_test_db.py` para añadir migraciones.                |

## `exploration/`

Sondas de lectura: imprimían trozos de `app/main.py` o volcados de esquema para
localizar dónde insertar código. Sustituidas por `grep` y por las herramientas de
`scripts/diagnostics/`.

## `debug/`

Depuración puntual de fallos concretos (auth falsa, TestClient ad-hoc, comprobación de
sintaxis). Los tests reales de comportamiento viven en `tests/` con sus propias
fixtures en `tests/conftest.py`.

## Notas de limpieza

- Ninguno de estos archivos estaba referenciado por `pyproject.toml`, CI
  (`.github/workflows/`), `docs/` ni por los tests.
- Los runners de test que sí siguen siendo útiles se movieron a `scripts/runners/`.
- `apply_notification_migration.py` aplicaba la migración 036; esa migración ya está
  registrada en `scripts/rebuild_test_db.py`, que es la vía vigente.
