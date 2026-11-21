"""Lanza los tests de biblioteca de material e integridad."""

import sys

from _common import run_pytest

sys.exit(run_pytest("tests/test_material.py", "tests/test_library_integrity.py"))