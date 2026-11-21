"""Lanza los tests de esquema, entidades y modelo V6."""

import sys

from _common import run_pytest

sys.exit(run_pytest(
    "tests/test_schema_mysql.py",
    "tests/test_entity_leads.py",
    "tests/test_v6_schema.py",
))