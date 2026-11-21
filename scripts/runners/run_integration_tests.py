"""Lanza todos los tests que requieren MariaDB real."""

import sys

from _common import run_pytest

sys.exit(run_pytest("-m", "not unit", "tests/"))