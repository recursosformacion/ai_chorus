"""Lanza los tests de agenda y borradores de creación."""

import sys

from _common import run_pytest

sys.exit(run_pytest(
    "tests/test_agenda.py",
    "tests/test_creation_drafts.py",
    "tests/test_creation_drafts_mysql.py",
))