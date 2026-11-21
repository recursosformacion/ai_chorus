"""Lanza los tests de OIDC y mensajes."""

import sys

from _common import run_pytest

sys.exit(run_pytest("tests/test_oidc.py", "tests/test_messages.py"))