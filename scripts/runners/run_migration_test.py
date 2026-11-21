"""Comprueba que las migraciones son repetibles sobre MariaDB."""

import sys

from _common import run_pytest

sys.exit(run_pytest(
    "tests/test_api_runtime.py::test_database_migrations_are_repeatable_mariadb",
))