"""Mocks del contrato M2M de osap-auth para las pruebas de Chorus.

`osap-auth` es la fuente única de identidad. Estos ayudantes simulan el
contrato real sin inventar endpoints:

- ``POST /oauth/token`` (client_credentials) devuelve un service token.
- ``GET /auth/m2m/users?ids=...`` resuelve ``{id, name}`` y omite los ids
  desconocidos, igual que el contrato real.
"""
from __future__ import annotations

import json
import urllib.parse
from typing import Any

import httpx

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
    ) -> None:
        self.directory = dict(directory)
        self.token_status = token_status
        self.lookup_status = lookup_status
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
            self._tokens_issued += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"service-token-{self._tokens_issued}",
                    "token_type": "Bearer",
                    "expires_in": 300,
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

    No es una segunda implementación del contrato: sólo registra llamadas y
    devuelve respuestas preparadas, para poder assertar el comportamiento de
    Chorus (agrupación, rechazo, indisponibilidad).
    """

    def __init__(
        self,
        directory: dict[str, str] | None = None,
        *,
        available: bool = True,
    ) -> None:
        self.directory = dict(directory or {})
        self.available = available
        self.calls: list[list[str]] = []

    def resolve_public_names(self, user_ids):
        self.calls.append(list(user_ids))
        if not self.available:
            _raise_unavailable()
        return {
            uid: self.directory[uid]
            for uid in dict.fromkeys(user_ids)
            if uid in self.directory
        }

    def resolve_one(self, user_id: str):
        self.calls.append([user_id])
        if not self.available:
            _raise_unavailable()
        return self.directory.get(user_id)


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