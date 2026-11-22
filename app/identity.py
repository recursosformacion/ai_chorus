"""Cliente de identidad de Chorus.

`osap-auth` es la **fuente única de identidad**. Chorus no mantiene catálogo,
directorio ni caché persistente de usuarios: sólo resuelve identidades públicas
mediante el contrato M2M de servicio.

Contrato utilizado (ver `osap-auth`):

- ``POST /oauth/token`` con ``grant_type=client_credentials``,
  ``client_id``, ``client_secret``, ``scope`` y ``audience``.
  Devuelve ``{access_token, token_type, expires_in, scope}``.
- ``GET /auth/m2m/users?ids=<uuid,...>`` con ``Authorization: Bearer <service token>``.
  Audiencia ``osap-auth``, scope ``auth:read_public_names``. Máximo 500 ids.
  Devuelve una lista de objetos con el contrato de ``PublicNameItem``:

  - ``id``: ``str`` (UUID canónico), obligatorio.
  - ``name``: ``str | None`` — el contrato lo admite nulo expresamente.
  - ``nickname``: ``str | None``.
  - ``nickname_public_consent``: ``bool``.

  Los UUID inexistentes o mal formados se **omiten** de la respuesta.

Validación estricta: cualquier elemento que no cumpla el contrato se rechaza con
``IdentityUnavailable``. Así un error del proveedor nunca se confunde con una
identidad que Auth no reconoce legítimamente.
"""
from __future__ import annotations

import threading
import time
import uuid as uuid_module
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
    """osap-auth no está disponible, no está configurado o incumple el contrato."""


@dataclass(frozen=True)
class PublicIdentity:
    """Identidad reconocida por Auth.

    ``name`` puede ser ``None``: el contrato de Auth lo permite cuando el
    usuario no tiene nombre público. La identidad sigue estando **resuelta**.
    """

    user_id: str
    name: str | None


@dataclass(frozen=True)
class ResolvedIdentity:
    """Identidad pública devuelta por Auth (alias histórico)."""

    user_id: str
    name: str | None


def _is_uuid(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        uuid_module.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _canonical(value: str) -> str:
    """Forma canónica de un UUID ya validado."""
    return str(uuid_module.UUID(value))


def _validate_contract_item(item: Any, chunk: list[str]) -> tuple[str, str | None]:
    """Valida un elemento de la respuesta contra el contrato de osap-auth.

    Devuelve ``(id_canónico, name)``. Lanza ``IdentityUnavailable`` si el
    elemento no es un objeto válido, si le falta ``id``, si el ``id`` no es un
    UUID, si no se había solicitado, o si los tipos no respetan el contrato.
    """
    if not isinstance(item, dict):
        raise IdentityUnavailable(
            "osap-auth devolvió un elemento que no es un objeto "
            f"({type(item).__name__}) incumpliendo el contrato M2M"
        )

    missing = [f for f in ("id",) if f not in item]
    if missing:
        raise IdentityUnavailable(
            "osap-auth devolvió un elemento sin el campo obligatorio "
            f"{missing[0]} (contrato PublicNameItem)"
        )

    raw_id = item["id"]
    if not isinstance(raw_id, str):
        raise IdentityUnavailable(
            "osap-auth devolvió un `id` que no es texto "
            f"({type(raw_id).__name__})"
        )
    if not _is_uuid(raw_id):
        raise IdentityUnavailable(
            f"osap-auth devolvió un `id` con formato no válido: {raw_id!r}"
        )

    canonical_id = _canonical(raw_id)
    requested = {_canonical(uid) for uid in chunk if _is_uuid(uid)}
    if canonical_id not in requested:
        raise IdentityUnavailable(
            "osap-auth devolvió un identificador que no se había solicitado: "
            f"{canonical_id}"
        )

    if "name" in item:
        name = item["name"]
        if name is not None and not isinstance(name, str):
            raise IdentityUnavailable(
                "osap-auth devolvió `name` con tipo no válido "
                f"({type(name).__name__}); el contrato admite texto o nulo"
            )
    else:
        name = None

    if "nickname" in item:
        nickname = item["nickname"]
        if nickname is not None and not isinstance(nickname, str):
            raise IdentityUnavailable(
                "osap-auth devolvió `nickname` con tipo no válido "
                f"({type(nickname).__name__})"
            )

    if "nickname_public_consent" in item:
        consent = item["nickname_public_consent"]
        if not isinstance(consent, bool):
            raise IdentityUnavailable(
                "osap-auth devolvió `nickname_public_consent` con tipo no válido "
                f"({type(consent).__name__}); el contrato exige booleano"
            )

    return canonical_id, name


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

    def _get_chunk(self, chunk: list[str]) -> list[Any]:
        """Pide un lote de ids y devuelve la lista sin validar del contrato."""
        token = self._service_token()
        try:
            with self._client() as client:
                response = client.get(
                    f"{self._base_url}{M2M_PATH}",
                    params={"ids": ",".join(chunk)},
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
                        params={"ids": ",".join(chunk)},
                        headers={"Authorization": f"Bearer {token}"},
                    )
            except httpx.HTTPError as exc:
                raise IdentityUnavailable(
                    f"osap-auth no ha podido resolver identidades: {exc}"
                ) from exc

        if response.status_code != 200:
            raise IdentityUnavailable(
                "osap-auth ha rechazado la resolución de identidades "
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
                "osap-auth devolvió un cuerpo que no es una lista "
                f"({type(items).__name__}) incumpliendo el contrato M2M"
            )
        return items

    def lookup(self, user_ids: list[str] | tuple[str, ...]) -> dict[str, PublicIdentity]:
        """Resuelve identidades reconocidas por Auth.

        Devuelve una entrada por cada identificador que Auth reconoce, incluidas
        las identidades sin nombre público (``name=None``). Un identificador que
        Auth **omite** no aparece en el resultado: eso significa "no reconocido".

        Si la respuesta de Auth incumple el contrato se lanza
        ``IdentityUnavailable`` en lugar de devolver un resultado parcial.
        """
        self._require_configured()
        targets = [uid for uid in dict.fromkeys(user_ids) if uid]
        if not targets:
            return {}

        resolved: dict[str, PublicIdentity] = {}
        for start in range(0, len(targets), M2M_MAX_IDS):
            chunk = targets[start:start + M2M_MAX_IDS]
            for item in self._get_chunk(chunk):
                canonical_id, name = _validate_contract_item(item, chunk)
                if canonical_id in resolved:
                    raise IdentityUnavailable(
                        "osap-auth devolvió dos veces el mismo identificador: "
                        f"{canonical_id}"
                    )
                resolved[canonical_id] = PublicIdentity(
                    user_id=canonical_id, name=name
                )
        return resolved

    def resolve_public_names(self, user_ids: list[str] | tuple[str, ...]) -> dict[str, str]:
        """Resuelve ``user_id -> nombre público`` mediante el contrato M2M.

        Sólo incluye identidades **con nombre público**. Agrupa los
        identificadores en lotes de 500 (máximo del contrato), no lanza una
        petición por usuario y no persiste los nombres recibidos.
        """
        return {
            uid: identity.name
            for uid, identity in self.lookup(user_ids).items()
            if identity.name
        }

    def resolve_identity(self, user_id: str) -> PublicIdentity | None:
        """Identidad reconocida por Auth, o ``None`` si no la reconoce.

        Distingue "Auth no conoce este id" (``None``) de "Auth lo conoce pero no
        expone nombre público" (``PublicIdentity(name=None)``).
        """
        if not _is_uuid(user_id):
            # El contrato M2M sólo acepta UUID; un id mal formado no es una
            # identidad verificable y no se consulta a Auth.
            return None
        return self.lookup([user_id]).get(_canonical(user_id))

    def resolve_one(self, user_id: str) -> str | None:
        """Nombre público de un identificador, o ``None``.

        Precaución: ``None`` aquí significa "sin nombre público" o "no
        reconocido". Para altas de destinatario debe usarse ``resolve_identity``,
        que distingue ambos casos.
        """
        identity = self.resolve_identity(user_id)
        return identity.name if identity is not None else None