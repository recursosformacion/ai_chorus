"""JWT validation against osap-auth JWKS. Never trust decoded, unsigned claims."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient

from app.config import Settings


@dataclass(frozen=True)
class Principal:
    sub: str
    roles: tuple[str, ...]
    email_verified: bool


class TokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwks: PyJWKClient | None = None

    def verify(self, token: str) -> Principal:
        self.settings.validate_auth()
        try:
            if self._jwks is None:
                self._jwks = PyJWKClient(
                    self.settings.auth_jwks_url, cache_jwk_set=True, lifespan=300
                )
            key = self._jwks.get_signing_key_from_jwt(token).key
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.settings.auth_issuer,
                audience=self.settings.auth_audience,
                options={"require": ["iss", "sub", "aud", "exp", "iat", "jti"]},
                leeway=60,
            )
        except Exception as exc:  # noqa: BLE001 — cualquier fallo de validación cierra acceso
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc
        if claims.get("token_use") != "user" or not isinstance(claims.get("sub"), str):
            raise HTTPException(status_code=401, detail="User access token required")
        roles = claims.get("roles")
        return Principal(
            sub=claims["sub"],
            roles=tuple(str(x) for x in roles) if isinstance(roles, list) else (),
            email_verified=claims.get("email_verified") is True,
        )


def bearer_principal(
    authorization: str | None = Header(default=None),
    verifier: TokenVerifier | None = None,
) -> Principal:
    if verifier is None or not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    return verifier.verify(authorization[7:].strip())
