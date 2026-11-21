"""Lanza la suite completa de integración con trazas cortas."""

import sys

from _common import run_pytest

sys.exit(run_pytest("tests/", "--tb=short", "-m", "not unit"))