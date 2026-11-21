"""Lanza los tests de campos de agrupación coral."""

import sys

from _common import run_pytest

sys.exit(run_pytest("tests/test_coral_fields.py"))