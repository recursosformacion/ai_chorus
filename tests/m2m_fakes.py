"""Mocks del contrato M2M de osap-auth para las pruebas de Chorus.

`osap-auth` es la fuente única de identidad. Estos ayudantes simulan el
contrato real sin inventar endpoints:

- ``POST /oauth/token`` (client_credentials) devuelve un service token.
- ``GET /auth/m2m/users?ids=...`` resuelve ``{id, name}`` y omite los ids
  desconocidos, igual que el contrato real.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

import httpx

from app.identity import PublicIdentity, canonical_uuid

TOKEN_PATH = "/oauth/token"
M2M_PATH = "/auth/m2m/users"


class FakeM2MTransport(httpx.BaseTransport):
    """Transport de httpx que emula el contrato M2M de osap-auth.

    Registra las llamadas para poder assertar que se agrupan los ids y que no
    se usa el token del administrador.
    """

    def __init__(
        self,
        directory: dict[str, str],
        *,
        token_status: int = 200,
        lookup_status: int = 200,
        expires_in: int = 300,
        require_audience: str | None = None,
        require_scope: str | None = None,
    ) -> None:
        self.directory = dict(directory)
        self.token_status = token_status
        self.lookup_status = lookup_status
        self.expires_in = expires_in
        self.require_audience = require_audience
        self.require_scope = require_scope
        self.token_calls: list[dict[str, Any]] = []
        self.lookup_calls: list[dict[str, Any]] = []
        self._tokens_issued = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == TOKEN_PATH:
            body = dict(urllib.parse.parse_qsl(request.content.decode("utf-8")))
            self.token_calls.append(body)
            if self.token_status != 200:
                return httpx.Response(
                    self.token_status, json={"error": "invalid_client"}
                )
            if (
                self.require_audience is not None
                and body.get("audience") != self.require_audience
            ):
                return httpx.Response(
                    400,
                    json={
                        "error": "invalid_client",
                        "error_description": "audience not allowed",
                    },
                )
            if (
                self.require_scope is not None
                and body.get("scope") != self.require_scope
            ):
                return httpx.Response(403, json={"error": "invalid_scope"})
            self._tokens_issued += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"service-token-{self._tokens_issued}",
                    "token_type": "Bearer",
                    "expires_in": self.expires_in,
                    "scope": body.get("scope", ""),
                },
            )

        if request.method == "GET" and request.url.path == M2M_PATH:
            params = dict(urllib.parse.parse_qsl(request.url.query.decode("utf-8")))
            raw_ids = params.get("ids", "")
            self.lookup_calls.append(
                {
                    "ids": [i for i in raw_ids.split(",") if i],
                    "authorization": request.headers.get("Authorization"),
                }
            )
            if self.lookup_status != 200:
                return httpx.Response(self.lookup_status, json={"detail": "error"})
            items = [
                {"id": uid, "name": name, "nickname": None,
                 "nickname_public_consent": False}
                for uid in raw_ids.split(",")
                if (name := self.directory.get(uid.strip())) is not None
            ]
            return httpx.Response(200, json=items)

        return httpx.Response(404, json={"detail": "not found"})


class RecordingIdentityClient:
    """Sustituto del cliente de identidad para pruebas de endpoints.

    Implementa el mismo contrato de métodos que ``IdentityClient``:
    ``lookup`` (identidades reconocidas), ``resolve_public_names`` (sólo con
    nombre) y ``resolve_identity`` (distinguir no reconocido de sin nombre).
    """

    def __init__(
        self,
        directory: dict[str, str | None] | None = None,
        *,
        available: bool = True,
    ) -> None:
        # Un valor None representa "identidad reconocida sin nombre público".
        self.directory: dict[str, str | None] = dict(directory or {})
        self.available = available
        self.calls: list[list[str]] = []

    def lookup(self, user_ids):
        self.calls.append(list(user_ids))
        if not self.available:
            _raise_unavailable()
        resolved = {}
        for uid in dict.fromkeys(user_ids):
            if uid not in self.directory:
                continue
            try:
                canonical = canonical_uuid(uid)
            except (ValueError, AttributeError, TypeError):
                # Auth omite los identificadores mal formados
                continue
            resolved[canonical] = PublicIdentity(
                user_id=canonical, name=self.directory[uid]
            )
        return resolved

    def resolve_public_names(self, user_ids):
        return {
            uid: identity.name
            for uid, identity in self.lookup(user_ids).items()
            if identity.name
        }

    def resolve_identity(self, user_id: str):
        self.calls.append([user_id])
        if not self.available:
            _raise_unavailable()
        if user_id not in self.directory:
            return None
        try:
            canonical = canonical_uuid(user_id)
        except (ValueError, AttributeError, TypeError):
            return None
        return PublicIdentity(user_id=canonical, name=self.directory[user_id])

    def resolve_one(self, user_id: str):
        identity = self.resolve_identity(user_id)
        return identity.name if identity is not None else None


class _Unavailable(Exception):
    """Marca de indisponibilidad para las pruebas."""


def _raise_unavailable():
    from app.identity import IdentityUnavailable

    raise IdentityUnavailable("osap-auth M2M no disponible (simulado)")


def install_identity(monkeypatch, client) -> None:
    """Sustituye el cliente de identidad de una app ya creada."""
    import app.main as main_module

    original = main_module.IdentityClient

    def _factory(*args, **kwargs):
        return client

    monkeypatch.setattr(main_module, "IdentityClient", _factory)
    return original