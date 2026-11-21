"""Utilidades compartidas por los runners de test de Chorus.

Los runners existen para lanzar pytest con una conexión fija a `osap_chorus_test`,
que es la base de integración. Centralizar aquí la preparación evita repetir las
credenciales y el ajuste de rutas en cada archivo.

`unittest`/`pytest` siempre se lanzan desde la raíz del proyecto, aunque el runner
esté en `scripts/runners/`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Raíz del repositorio: scripts/runners/_common.py -> parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEST_DATABASE_URL = (
    "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"
)


def run_pytest(*args: str) -> int:
    """Ejecuta pytest desde la raíz del proyecto con la BD de test."""

    os.environ.setdefault("CHORUS_DATABASE_URL", TEST_DATABASE_URL)
    os.chdir(PROJECT_ROOT)

    import pytest

    return pytest.main(["-v", *args])
