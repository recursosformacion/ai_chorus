"""Validación estricta del contrato de respuestas M2M de osap-auth.

Un elemento malformado NO debe confundirse con una identidad que Auth omite
legítimamente: se rechaza con ``IdentityUnavailable`` (que los endpoints
convierten en 503).
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from app.identity import (
    IdentityClient,
    IdentityUnavailable,
    PublicIdentity,
    _validate_contract_item,
)

A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class _ScriptedTransport(httpx.BaseTransport):
    """Transport que devuelve una secuencia fija de respuestas JSON."""

    def __init__(self, payloads: list[tuple[int, object]]) -> None:
        self.payloads = list(payloads)
        self.calls: list[dict] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append({"method": request.method, "url": str(request.url)})
        # La primera llamada es el token de servicio
        if request.method == "POST" and request.url.path == "/oauth/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "tok",
                    "token_type": "Bearer",
                    "expires_in": 300,
                    "scope": "auth:read_public_names",
                },
            )
        status, payload = self.payloads.pop(0) if self.payloads else (500, {})
        return httpx.Response(status, json=payload)


def _client(payloads) -> IdentityClient:
    return IdentityClient(
        "https://auth.test",
        client_id="cid",
        client_secret="secret",
        transport=_ScriptedTransport(payloads),
    )


# --------------------------------------------------------------------------
# Validación por elemento (unidad)
# --------------------------------------------------------------------------
@pytest.mark.unit
def test_valid_element_is_accepted():
    uid, name = _validate_contract_item(
        {
            "id": A,
            "name": "Nombre",
            "nickname": "nick",
            "nickname_public_consent": True,
        },
        [A],
    )
    assert uid == A
    assert name == "Nombre"


@pytest.mark.unit
def test_null_name_is_allowed_by_contract():
    """El contrato admite `name: null` explícitamente (PublicNameItem)."""
    uid, name = _validate_contract_item({"id": A, "name": None}, [A])
    assert uid == A
    assert name is None


@pytest.mark.unit
def test_element_not_a_dict_is_rejected():
    for bad in ("cadena", 42, ["lista"], None, True):
        with pytest.raises(IdentityUnavailable):
            _validate_contract_item(bad, [A])


@pytest.mark.unit
def test_element_without_id_is_rejected():
    with pytest.raises(IdentityUnavailable) as exc:
        _validate_contract_item({"name": "Sin id"}, [A])
    assert "id" in str(exc.value)


@pytest.mark.unit
def test_element_with_non_string_id_is_rejected():
    with pytest.raises(IdentityUnavailable):
        _validate_contract_item({"id": 12345}, [A])


@pytest.mark.unit
def test_element_with_malformed_id_is_rejected():
    for bad in ("no-es-uuid", "123", "aaaaaaaa-aaaa-4aaa-8aaa", ""):
        with pytest.raises(IdentityUnavailable):
            _validate_contract_item({"id": bad, "name": "X"}, [bad])


@pytest.mark.unit
def test_element_with_unrequested_id_is_rejected():
    """Auth no puede devolver un id que no se pidió en ese lote."""
    with pytest.raises(IdentityUnavailable) as exc:
        _validate_contract_item({"id": B, "name": "X"}, [A])
    assert "no se había solicitado" in str(exc.value)


@pytest.mark.unit
def test_element_with_wrong_name_type_is_rejected():
    for bad in (123, 1.5, ["x"], {"a": 1}, True):
        with pytest.raises(IdentityUnavailable):
            _validate_contract_item({"id": A, "name": bad}, [A])


@pytest.mark.unit
def test_element_with_wrong_nickname_type_is_rejected():
    with pytest.raises(IdentityUnavailable):
        _validate_contract_item({"id": A, "nickname": 7}, [A])


@pytest.mark.unit
def test_element_with_wrong_consent_type_is_rejected():
    for bad in ("true", 1, None):
        with pytest.raises(IdentityUnavailable):
            _validate_contract_item(
                {"id": A, "nickname_public_consent": bad}, [A]
            )


# --------------------------------------------------------------------------
# Respuesta completa
# --------------------------------------------------------------------------
@pytest.mark.unit
def test_legitimate_omission_returns_partial_result():
    """Auth omite ids que no reconoce: eso es legítimo y no es un error."""
    client = _client([(200, [{"id": A, "name": "Nombre A"}])])

    result = client.lookup([A, B])

    assert set(result) == {A}
    assert result[A] == PublicIdentity(user_id=A, name="Nombre A")


@pytest.mark.unit
def test_unknown_identity_is_absent_not_none():
    """Ausente = no reconocido; distinto de reconocido-sin-nombre."""
    client = _client([(200, [{"id": A, "name": None}])])

    result = client.lookup([A, B])

    assert set(result) == {A}
    assert result[A].name is None
    assert B not in result, "B no fue devuelto por Auth: no reconocido"


@pytest.mark.unit
def test_body_not_a_list_raises():
    client = _client([(200, {"id": A, "name": "X"})])
    with pytest.raises(IdentityUnavailable):
        client.lookup([A])


@pytest.mark.unit
def test_any_malformed_element_aborts_whole_response():
    """No se devuelve resultado parcial si un elemento incumple el contrato."""
    client = _client(
        [(200, [{"id": A, "name": "Uno"}, {"name": "Sin id"}])]
    )
    with pytest.raises(IdentityUnavailable):
        client.lookup([A])


@pytest.mark.unit
def test_malformed_element_after_valid_one_aborts():
    client = _client(
        [(200, [{"id": A, "name": "Uno"}, {"id": B, "name": 99}])]
    )
    with pytest.raises(IdentityUnavailable):
        client.lookup([A, B])


@pytest.mark.unit
def test_duplicate_ids_in_response_are_rejected():
    client = _client([(200, [{"id": A, "name": "Uno"}, {"id": A, "name": "Dos"}])])
    with pytest.raises(IdentityUnavailable):
        client.lookup([A])


@pytest.mark.unit
def test_non_json_body_raises():
    class _BadJson(_ScriptedTransport):
        def handle_request(self, request):
            if request.method == "POST":
                return httpx.Response(
                    200,
                    json={
                        "access_token": "tok",
                        "token_type": "Bearer",
                        "expires_in": 300,
                        "scope": "s",
                    },
                )
            return httpx.Response(200, text="no soy json")

    client = IdentityClient(
        "https://auth.test",
        client_id="c",
        client_secret="s",
        transport=_BadJson([]),
    )
    with pytest.raises(IdentityUnavailable):
        client.lookup([A])


@pytest.mark.unit
def test_resolve_public_names_skips_unnamed_identities():
    client = _client([(200, [{"id": A, "name": None}, {"id": B, "name": "B"}])])

    assert client.resolve_public_names([A, B]) == {B: "B"}


@pytest.mark.unit
def test_resolve_identity_distinguishes_unknown_from_unnamed():
    # Auth devuelve A sin nombre público y omite B (no lo reconoce)
    client = _client([(200, [{"id": A, "name": None}]), (200, [])])

    identity = client.resolve_identity(A)
    assert identity is not None
    assert identity.name is None

    assert client.resolve_identity(B) is None


@pytest.mark.unit
def test_malformed_resolve_identity_does_not_call_auth():
    """Un id mal formado se rechaza sin llamar a Auth."""
    transport = _ScriptedTransport([])
    client = IdentityClient(
        "https://auth.test", client_id="c", client_secret="s", transport=transport
    )

    for bad in ("", "no-uuid", "123", None):
        assert client.resolve_identity(bad) is None

    assert transport.calls == [], "No debe emitirse ni una petición"


@pytest.mark.unit
def test_uuid_case_and_braces_are_normalised():
    """Se compara por forma canónica, no por literal."""
    braced = "{" + A.upper() + "}"
    uid, name = _validate_contract_item({"id": A, "name": "X"}, [braced])
    assert uid == A
    assert name == "X"


@pytest.mark.unit
def test_batch_splits_at_contract_limit():
    """600 ids -> 2 llamadas (500 + 100), sin llamadas individuales."""
    ids = [str(uuid.UUID(int=i)) for i in range(600)]
    payload = [{"id": uid, "name": f"N{uid[:3]}"} for uid in ids[:500]]
    payload += [{"id": uid, "name": f"N{uid[:3]}"} for uid in ids[500:]]

    transport = _ScriptedTransport([(200, payload[:500]), (200, payload[500:])])
    client = IdentityClient(
        "https://auth.test", client_id="c", client_secret="s", transport=transport
    )

    resolved = client.lookup(ids)

    assert len(resolved) == 600
    lookups = [c for c in transport.calls if c["method"] == "GET"]
    assert len(lookups) == 2, "Una llamada por lote, no una por usuario"