"""Lanza los tests de obras de preparación."""

import sys

from _common import run_pytest

sys.exit(run_pytest("tests/test_preparation_works.py"))