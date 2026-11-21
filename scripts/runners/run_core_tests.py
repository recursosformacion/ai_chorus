"""Lanza los tests de grupos, artículos y auditoría."""

import sys

from _common import run_pytest

sys.exit(run_pytest(
    "tests/test_articles.py",
    "tests/test_group_roles.py",
    "tests/test_group_social_links.py",
    "tests/test_legacy_uploads.py",
    "tests/test_activity_log.py",
))