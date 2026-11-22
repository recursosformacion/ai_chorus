"""Cliente de identidad de Chorus.

`osap-auth` es la **fuente única de identidad**. Chorus no mantiene catálogo,
directorio ni caché persistente de usuarios: sólo resuelve nombres públicos
mediante el contrato M2M de servicio.

Contrato utilizado (ver `osap-auth`):

- ``POST /oauth/token`` con ``grant_type=client_credentials``,
  ``client_id``, ``client_secret``, ``scope`` y ``audience``.
  Devuelve ``{access_token, token_type, expires_in, scope}``.
- ``GET /auth/m2m/users?ids=<uuid,...>`` con ``Authorization: Bearer <service token>``.
  Audiencia ``osap-auth``, scope ``auth:read_public_names``. Máximo 500 ids.
  Devuelve una lista de ``{id, name, nickname, nickname_public_consent}``.
  Los UUID inexistentes o mal formados se **omiten**.

No se utiliza el token del administrador como sustituto de la credencial M2M:
el alta administrativa necesita el contexto de Auth para el destinatario, no
para el actor.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

# Contrato cerrado del lado de osap-auth (api/routes/m2m_users.py).
M2M_PATH = "/auth/m2m/users"
M2M_AUDIENCE = "osap-auth"
M2M_SCOPE = "auth:read_public_names"
M2M_MAX_IDS = 500
_TOKEN_PATH = "/oauth/token"
_TOKEN_SAFETY_MARGIN_SECONDS = 30


class IdentityError(RuntimeError):
    """Uso incorrecto del cliente de identidad (configuración o contrato)."""


class IdentityUnavailable(RuntimeError):
    """osap-auth no está disponible o no puede resolver la identidad."""


@dataclass(frozen=True)
class ResolvedIdentity:
    """Identidad pública devuelta por Auth."""

    user_id: str
    name: str | None


def _is_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


class IdentityClient:
    """Cliente M2M de osap-auth con caché en memoria del token de servicio.

    La caché es sólo del **token** (corta vida, 5 minutos), nunca de identidades:
    los nombres no se persisten en Chorus.
    """

    def __init__(
        self,
        base_url: str,
        *,
        client_id: str = "",
        client_secret: str = "",
        scope: str = M2M_SCOPE,
        audience: str = M2M_AUDIENCE,
        timeout_seconds: float = 15.0,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._audience = audience
        self._timeout = timeout_seconds
        self._transport = transport
        self._clock = clock
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._client_id and self._client_secret)

    def _require_configured(self) -> None:
        if not self.configured:
            raise IdentityUnavailable(
                "osap-auth M2M no está configurado "
                "(CHORUS_AUTH_M2M_CLIENT_ID / CHORUS_AUTH_M2M_CLIENT_SECRET)"
            )

    def _client(self) -> httpx.Client:
        kwargs: dict[str, Any] = {"timeout": self._timeout}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def _service_token(self) -> str:
        """Devuelve un token de servicio válido, renovándolo si procede."""
        self._require_configured()
        now = self._clock()
        with self._lock:
            if self._token and now < self._token_expires_at:
                return self._token

            payload = {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self._scope,
                "audience": self._audience,
            }
            try:
                with self._client() as client:
                    response = client.post(
                        f"{self._base_url}{_TOKEN_PATH}", data=payload
                    )
            except httpx.HTTPError as exc:
                raise IdentityUnavailable(
                    f"osap-auth no ha podido emitir el token de servicio: {exc}"
                ) from exc

            if response.status_code != 200:
                raise IdentityUnavailable(
                    "osap-auth ha rechazado las credenciales de servicio "
                    f"(HTTP {response.status_code})"
                )
            try:
                body = response.json()
            except ValueError as exc:
                raise IdentityUnavailable(
                    "respuesta de token no interpretable de osap-auth"
                ) from exc

            token = body.get("access_token") if isinstance(body, dict) else None
            if not isinstance(token, str) or not token:
                raise IdentityUnavailable(
                    "osap-auth no ha devuelto access_token de servicio"
                )
            try:
                expires_in = int(body.get("expires_in") or 0)
            except (TypeError, ValueError):
                expires_in = 0
            ttl = max(expires_in - _TOKEN_SAFETY_MARGIN_SECONDS, 0)

            self._token = token
            self._token_expires_at = now + ttl
            return token

    def resolve_public_names(self, user_ids: list[str] | tuple[str, ...]) -> dict[str, str]:
        """Resuelve ``user_id -> nombre público`` mediante el contrato M2M.

        Agrupa los identificadores en lotes de 500 (máximo del contrato), no
        lanza una petición por usuario y no persiste los nombres recibidos.
        """
        self._require_configured()
        targets = [uid for uid in dict.fromkeys(user_ids) if uid]
        if not targets:
            return {}

        resolved: dict[str, str] = {}
        for start in range(0, len(targets), M2M_MAX_IDS):
            chunk = targets[start:start + M2M_MAX_IDS]
            ids_param = ",".join(chunk)
            token = self._service_token()
            try:
                with self._client() as client:
                    response = client.get(
                        f"{self._base_url}{M2M_PATH}",
                        params={"ids": ids_param},
                        headers={"Authorization": f"Bearer {token}"},
                    )
            except httpx.HTTPError as exc:
                raise IdentityUnavailable(
                    f"osap-auth no ha podido resolver identidades: {exc}"
                ) from exc

            if response.status_code in (401, 403):
                # Token caducado o sin scope: se descarta y se reintenta una vez.
                with self._lock:
                    self._token = None
                    self._token_expires_at = 0.0
                token = self._service_token()
                try:
                    with self._client() as client:
                        response = client.get(
                            f"{self._base_url}{M2M_PATH}",
                            params={"ids": ids_param},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                except httpx.HTTPError as exc:
                    raise IdentityUnavailable(
                        f"osap-auth no ha podido resolver identidades: {exc}"
                    ) from exc

            if response.status_code != 200:
                raise IdentityUnavailable(
                    f"osap-auth ha rechazado la resolución de identidades "
                    f"(HTTP {response.status_code})"
                )
            try:
                items = response.json()
            except ValueError as exc:
                raise IdentityUnavailable(
                    "respuesta de identidades no interpretable de osap-auth"
                ) from exc
            if not isinstance(items, list):
                raise IdentityUnavailable(
                    "respuesta de identidades con formato inesperado"
                )

            for item in items:
                if not isinstance(item, dict):
                    continue
                uid = item.get("id")
                name = item.get("name")
                if not isinstance(uid, str) or not uid:
                    continue
                if isinstance(name, str) and name.strip():
                    resolved[uid] = name
        return resolved

    def resolve_one(self, user_id: str) -> str | None:
        """Resuelve el nombre público de un único identificador.

        Devuelve ``None`` si Auth no lo devuelve: nunca se inventa un nombre.
        """
        if not user_id:
            return None
        if not _is_uuid(user_id):
            # El contrato M2M sólo acepta UUID; un id mal formado no es una
            # identidad verificable.
            return None
        return self.resolve_public_names([user_id]).get(user_id)