"""Utilidades compartidas para Chorus."""
from datetime import UTC, datetime


def utcnow() -> str:
    return datetime.now(UTC).isoformat()