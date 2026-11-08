"""Identity value returned by the authoritative osap-auth /auth/me endpoint."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    sub: str
    roles: tuple[str, ...]
    email_verified: bool
