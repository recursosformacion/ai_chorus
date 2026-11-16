"""Chorus API pilot: osap-auth identity, OSAP read proxy and private creation drafts."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import re
import secrets
import sqlite3
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from urllib.parse import quote, urlencode

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.db import connect as db_connect
from app.security import Principal

logger = logging.getLogger(__name__)


SUPPORTED_SOURCE_SUFFIXES = {
    ".mxl", ".musicxml", ".xml", ".mid", ".midi", ".mscz", ".mscx",
    ".capx", ".cap", ".gp", ".gpx", ".ptb", ".pt2",
}


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class DraftBody(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    resource_type: str = Field(default="score", min_length=1, max_length=80)


class SourceBody(BaseModel):
    work_id: str = Field(min_length=1, max_length=200)
    representation_id: str = Field(min_length=1, max_length=200)


class OnboardingBody(BaseModel):
    nickname: str = Field(min_length=3, max_length=30)
    terms_version: str = Field(min_length=1, max_length=40)
    privacy_version: str = Field(min_length=1, max_length=40)


class LibraryReferenceBody(BaseModel):
    provider: str = Field(default="osap", min_length=1, max_length=40)
    work_id: str = Field(min_length=1, max_length=200)
    representation_id: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] | None = None


class CollectionBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class CollectionItemBody(BaseModel):
    library_item_id: str = Field(min_length=1, max_length=64)


class GroupBody(BaseModel):
    entity_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(default="Europe/Madrid", max_length=80)


class GroupUpdateBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = Field(default=None, max_length=80)


class JoinGroupBody(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class HandoffBody(BaseModel):
    access_token: str = Field(min_length=10)
    refresh_token: str | None = None


class EntityLeadBody(BaseModel):
    entity_name: str = Field(min_length=2, max_length=160)
    entity_kind: str = Field(
        pattern="^(coral|orquesta|grupo|banda|ensemble|escuela|iglesia)$"
    )
    city: str | None = Field(default=None, max_length=120)
    members: int | None = Field(default=None, ge=0, le=100_000)
    contact_name: str = Field(min_length=2, max_length=160)
    contact_email: str = Field(min_length=5, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=40)
    manager_name: str = Field(min_length=2, max_length=160)
    manager_email: str = Field(min_length=5, max_length=254)
    manager_has_account: bool = False
    website: str | None = Field(default=None, max_length=300)
    interests: list[Literal["subscription", "whatsapp", "sms"]] = Field(
        default_factory=list
    )
    message: str | None = Field(default=None, max_length=4000)
    consent: bool
    company_website: str = ""


class EventBody(BaseModel):
    group_id: str = Field(min_length=1, max_length=64)
    kind: Literal["rehearsal", "concert", "note"]
    title: str = Field(min_length=1, max_length=200)
    starts_at: str = Field(min_length=10, max_length=64)
    ends_at: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=4000)


class RsvpBody(BaseModel):
    status: Literal["yes", "no"]
    comment: str | None = Field(default=None, max_length=1000)


class MemberUpdateBody(BaseModel):
    role: Literal["manager", "member"] | None = None
    admin_role_id: str | None = None
    musical_role_id: str | None = None
    section_id: str | None = None
    status: Literal["active", "removed"] | None = None


class MessageReplyBody(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class MessageBody(BaseModel):
    scope: Literal["group", "managers", "users"]
    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=8000)
    recipient_subs: list[str] = Field(default_factory=list, max_length=200)


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _roles(profile: dict[str, Any]) -> set[str]:
    roles = profile.get("roles")
    return {str(role) for role in roles} if isinstance(roles, list) else set()


def _approved_memberships(profile: dict[str, Any]) -> list[dict[str, Any]]:
    memberships = profile.get("memberships")
    if not isinstance(memberships, list):
        return []
    return [
        membership for membership in memberships
        if isinstance(membership, dict) and membership.get("status") == "approved"
    ]


def _is_admin(profile: dict[str, Any]) -> bool:
    return "admin" in _roles(profile)


def _is_representative(profile: dict[str, Any], entity_id: str) -> bool:
    return _is_admin(profile) or any(
        membership.get("entity_id") == entity_id
        and membership.get("is_representative") is True
        for membership in _approved_memberships(profile)
    )


def _normalise_iso(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _group_dto(row: sqlite3.Row, role: str, can_manage: bool) -> dict[str, Any]:
    return {
        "id": row["id"],
        "entity_id": row["entity_id"],
        "name": row["name"],
        "timezone": row["timezone"],
        "join_code": row["join_code"],
        "role": role,
        "can_manage": can_manage,
    }


def _join_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _event_dto(
    row: sqlite3.Row, *, my_rsvp: str | None, group_name: str | None, can_manage: bool
) -> dict[str, Any]:
    return {
        "id": row["id"],
        "group_id": row["group_id"],
        "entity_id": row["entity_id"],
        "scope": row["scope"],
        "kind": row["kind"],
        "title": row["title"],
        "starts_at": row["starts_at"],
        "ends_at": row["ends_at"],
        "location": row["location"],
        "notes": row["notes"],
        "group_name": group_name,
        "my_rsvp": my_rsvp,
        "rsvp_required": row["kind"] != "note",
        "can_manage": can_manage,
    }


def _connect(settings: Settings):
    return db_connect(settings)


def initialise_database(settings: Settings) -> None:
    root = Path(__file__).resolve().parent.parent
    with _connect(settings) as conn:
        if settings.database_url:
            conn.executescript((root / "migrations" / "mysql" / "001_schema.sql").read_text("utf-8"))
            applied = conn.execute(
                "SELECT 1 FROM chorus_schema_migrations WHERE name = ?", ("mysql_schema_v1",)
            ).fetchone()
            if applied is None:
                conn.execute(
                    "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
                    ("mysql_schema_v1", utcnow()),
                )
            return
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chorus_schema_migrations "
            "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        for name in (
            "001_v6_work_resource_file.sql",
            "002_creation_drafts.sql",
            "003_owner_and_library.sql",
            "004_oidc_states.sql",
            "005_local_draft_source.sql",
            "006_groups_events.sql",
            "007_entity_leads.sql",
            "008_entity_lead_manager.sql",
            "009_messages.sql",
            "010_group_member_roles.sql",
        ):
            applied = conn.execute(
                "SELECT 1 FROM chorus_schema_migrations WHERE name = ?", (name,)
            ).fetchone()
            if applied is None:
                conn.executescript("BEGIN IMMEDIATE;\n" + (root / "migrations" / "sqlite" / name).read_text("utf-8") + "\nCOMMIT;")
                conn.execute(
                    "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
                    (name, utcnow()),
                )


def _safe_name(name: str | None) -> str:
    candidate = Path(name or "score.mxl").name
    candidate = re.sub(r"[^A-Za-z0-9._ -]", "_", candidate).strip(" .")
    return candidate[:180] or "score.mxl"


def validate_mxl(data: bytes, filename: str, max_uncompressed: int = 100 * 1024 * 1024) -> str:
    if Path(filename).suffix.lower() != ".mxl":
        raise ValueError("Only compressed MusicXML (.mxl) files are accepted here")
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            names = {i.filename for i in infos}
            if len(infos) > 2000 or sum(i.file_size for i in infos) > max_uncompressed:
                raise ValueError("MXL archive exceeds safety limits")
            for info in infos:
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or info.filename.startswith(("/", "\\")):
                    raise ValueError("Unsafe path in MXL archive")
            if "META-INF/container.xml" not in names:
                raise ValueError("MXL container.xml is missing")
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = next(
                (node.attrib.get("full-path") for node in container.iter()
                 if node.tag.rsplit("}", 1)[-1] == "rootfile"),
                None,
            )
            if not rootfile or rootfile not in names:
                raise ValueError("MXL root MusicXML file is missing")
            score = ET.fromstring(archive.read(rootfile))
            if score.tag.rsplit("}", 1)[-1] not in {"score-partwise", "score-timewise"}:
                raise ValueError("MXL root file is not a MusicXML score")
            return rootfile
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid MXL ZIP archive") from exc
    except ET.ParseError as exc:
        raise ValueError("Invalid MusicXML XML structure") from exc
    except (KeyError, RuntimeError, OSError) as exc:
        raise ValueError("Unable to read MXL archive contents") from exc


def _unwrap_osap(doc: Any) -> Any:
    if isinstance(doc, dict) and doc.get("success") is True and "data" in doc:
        return doc["data"]
    if isinstance(doc, dict) and doc.get("success") is False:
        error = doc.get("error") or {}
        raise HTTPException(status_code=502, detail=str(error.get("message") or "OSAP request failed"))
    return doc


def _save_private(settings: Settings, data: bytes, suffix: str) -> str:
    root = Path(settings.storage_root).resolve()
    (root / "objects").mkdir(parents=True, exist_ok=True)
    object_id = uuid.uuid4().hex
    target = root / "objects" / f"{object_id}{suffix}"
    target.write_bytes(data)
    return f"objects/{object_id}{suffix}"


def _read_private(settings: Settings, pointer: str) -> bytes:
    root = Path(settings.storage_root).resolve()
    target = (root / pointer).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="Private file not found")
    return target.read_bytes()


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.load()
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        initialise_database(cfg)
        yield

    app = FastAPI(title="Chorus API", version="0.2.2", lifespan=lifespan)

    origins = list(cfg.cors_origins)
    if cfg.editor_origin and cfg.editor_origin not in origins:
        origins.append(cfg.editor_origin)
    if origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    def profile_from_authorization(authorization: str | None) -> dict[str, Any]:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        token = authorization[7:].strip()
        status_code, profile = auth_call("GET", "/auth/me", token=token)
        if status_code != 200 or not isinstance(profile, dict):
            raise HTTPException(
                status_code=401 if status_code in (400, 401, 403) else 502,
                detail="osap-auth could not validate the user session",
            )
        if profile.get("status") in {"disabled", "deleted"}:
            raise HTTPException(status_code=403, detail="Account is not active")
        return profile

    def principal_from_profile(profile: dict[str, Any]) -> Principal:
        user_id = profile.get("user_id")
        if not isinstance(user_id, str) or not user_id:
            raise HTTPException(status_code=401, detail="Identity profile has no user_id")
        roles = profile.get("roles")
        return Principal(
            sub=user_id,
            roles=tuple(str(role) for role in roles) if isinstance(roles, list) else (),
            email_verified=profile.get("email_verified") is True,
        )

    def principal_from_authorization(authorization: str | None) -> Principal:
        return principal_from_profile(profile_from_authorization(authorization))

    def principal_dependency(authorization: str | None = Header(default=None)) -> Principal:
        return principal_from_authorization(authorization)

    def current_user(authorization: str | None = Header(default=None)) -> Principal:
        profile = profile_from_authorization(authorization)
        onboarding = profile.get("onboarding")
        if isinstance(onboarding, dict) and onboarding.get("required") is True:
            raise HTTPException(
                status_code=403,
                detail={"code": "ONBOARDING_REQUIRED", "onboarding": onboarding},
            )
        return principal_from_profile(profile)

    def current_profile(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        profile = profile_from_authorization(authorization)
        onboarding = profile.get("onboarding")
        if isinstance(onboarding, dict) and onboarding.get("required") is True:
            raise HTTPException(
                status_code=403,
                detail={"code": "ONBOARDING_REQUIRED", "onboarding": onboarding},
            )
        return profile

    def auth_call(method: str, path: str, *, payload: dict[str, Any] | None = None,
                  token: str | None = None) -> tuple[int, Any]:
        try:
            cfg.validate_auth()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Identity service is not configured") from exc
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            with httpx.Client(timeout=cfg.auth_timeout_seconds) as client:
                response = client.request(method, cfg.auth_base_url + path, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Identity service unavailable") from exc
        try:
            body = response.json()
        except ValueError:
            body = {}
        return response.status_code, body

    def osap_call(method: str, path: str, *, payload: dict[str, Any] | None = None,
                  token: str | None = None) -> tuple[Any, httpx.Response]:
        if not cfg.osap_api_base_url:
            raise HTTPException(status_code=503, detail="OSAP API is not configured")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            with httpx.Client(timeout=cfg.osap_timeout_seconds, follow_redirects=True) as client:
                response = client.request(
                    method, cfg.osap_api_base_url + path, json=payload, headers=headers
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="OSAP API unavailable") from exc
        try:
            doc = response.json()
        except ValueError:
            doc = None
        if response.status_code >= 400:
            detail = "OSAP API request failed"
            if isinstance(doc, dict):
                error = doc.get("error") or {}
                detail = str(
                    doc.get("detail")
                    or (error.get("message") if isinstance(error, dict) else None)
                    or doc.get("message")
                    or detail
                )
            code = response.status_code if response.status_code in {400, 401, 403, 404, 409, 422, 429} else 502
            raise HTTPException(status_code=code, detail=detail)
        return _unwrap_osap(doc), response

    def owned_draft(draft_id: str, user: Principal) -> sqlite3.Row:
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT * FROM creation_drafts WHERE id = ? AND owner_sub = ?",
                (draft_id, user.sub),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return row

    def library_item_dto(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        raw = item.pop("metadata_json", None)
        item["metadata"] = json.loads(raw) if raw else None
        return item

    def collection_dto(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def owned_library_item(item_id: str, user: Principal) -> sqlite3.Row:
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT * FROM library_items WHERE id = ? AND owner_sub = ?",
                (item_id, user.sub),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Library item not found")
        return row

    def owned_collection(collection_id: str, user: Principal) -> sqlite3.Row:
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT * FROM collections WHERE id = ? AND owner_sub = ?",
                (collection_id, user.sub),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Collection not found")
        return row

    def draft_dto(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "status": row["status"], "source_kind": row["source_kind"],
            "title": row["title"], "resource_type": row["resource_type"],
            "source_work_id": row["source_work_id"],
            "source_representation_id": row["source_representation_id"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "materialized_work_id": row["materialized_work_id"],
        }

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "chorus-api"}

    @app.post("/api/v1/auth/login")
    def login(body: LoginBody, response: Response) -> dict[str, Any]:
        status_code, doc = auth_call(
            "POST", "/auth/login",
            payload={"email": body.email, "password": body.password},
        )
        if status_code != 200 or not isinstance(doc, dict) or not doc.get("access_token") or not doc.get("refresh_token"):
            raise HTTPException(status_code=status_code if status_code in (400, 401, 422, 429) else 502,
                                detail=doc.get("detail", "Login failed") if isinstance(doc, dict) else "Login failed")
        profile_status, profile = auth_call("GET", "/auth/me", token=str(doc["access_token"]))
        if profile_status != 200 or not isinstance(profile, dict):
            raise HTTPException(status_code=502, detail="Could not load authenticated account profile")
        refresh_token = str(doc["refresh_token"])
        response.set_cookie(
            "chorus_access", str(doc["access_token"]), httponly=True,
            secure=cfg.secure_cookies, samesite="lax", path="/api/v1", max_age=15 * 60,
        )
        response.set_cookie(
            "chorus_refresh", refresh_token, httponly=True, secure=cfg.secure_cookies,
            samesite="lax", path="/api/v1/auth", max_age=30 * 24 * 60 * 60,
        )
        result = {k: doc[k] for k in ("access_token", "user_id", "roles", "email_verified") if k in doc}
        result["onboarding"] = profile.get("onboarding")
        return result

    @app.post("/api/v1/auth/handoff")
    def handoff(body: HandoffBody, response: Response) -> dict[str, Any]:
        """Sesión SSO desde OSAP: valida el token y deja el refresh en cookie."""
        profile_status, profile = auth_call("GET", "/auth/me", token=body.access_token)
        if profile_status != 200 or not isinstance(profile, dict):
            raise HTTPException(status_code=401, detail="Invalid handoff token")
        response.set_cookie(
            "chorus_access", body.access_token, httponly=True,
            secure=cfg.secure_cookies, samesite="lax", path="/api/v1",
            max_age=15 * 60,
        )
        if body.refresh_token:
            response.set_cookie(
                "chorus_refresh", body.refresh_token, httponly=True,
                secure=cfg.secure_cookies, samesite="lax", path="/api/v1/auth",
                max_age=30 * 24 * 60 * 60,
            )
        result = {
            "access_token": body.access_token,
            "user_id": profile.get("user_id"),
            "roles": profile.get("roles", []),
            "email_verified": profile.get("email_verified"),
            "onboarding": profile.get("onboarding"),
            "nickname": profile.get("nickname"),
            "email": profile.get("email"),
        }
        return result

    @app.post("/api/v1/auth/refresh")
    def refresh(request: Request, response: Response) -> dict[str, Any]:
        refresh_token = request.cookies.get("chorus_refresh")
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Refresh session missing")
        status_code, doc = auth_call(
            "POST", "/auth/refresh",
            payload={"refresh_token": refresh_token},
        )
        if status_code != 200 or not isinstance(doc, dict) or not doc.get("access_token") or not doc.get("refresh_token"):
            response.delete_cookie("chorus_refresh", path="/api/v1/auth")
            raise HTTPException(status_code=401, detail="Session expired; sign in again")
        response.set_cookie(
            "chorus_refresh", refresh_token, httponly=True, secure=cfg.secure_cookies,
            samesite="lax", path="/api/v1/auth", max_age=30 * 24 * 60 * 60,
        )
        profile_status, profile = auth_call("GET", "/auth/me", token=str(doc["access_token"]))
        if profile_status != 200 or not isinstance(profile, dict):
            response.delete_cookie("chorus_refresh", path="/api/v1/auth")
            raise HTTPException(status_code=401, detail="Session could not be validated")
        result = {k: doc[k] for k in ("access_token", "user_id", "roles", "email_verified") if k in doc}
        result["onboarding"] = profile.get("onboarding")
        return result

    @app.get("/api/v1/auth/me")
    def me(authorization: str | None = Header(default=None)) -> Any:
        return profile_from_authorization(authorization)

    @app.get("/api/v1/auth/legal/current")
    def legal_current() -> Any:
        status_code, document = auth_call("GET", "/auth/legal/current")
        if status_code != 200:
            raise HTTPException(status_code=502, detail="Legal information unavailable")
        return document

    @app.post("/api/v1/auth/onboarding")
    def complete_onboarding(body: OnboardingBody, authorization: str | None = Header(default=None)) -> Any:
        principal_from_authorization(authorization)
        token = authorization[7:].strip() if authorization else ""
        status_code, document = auth_call(
            "POST", "/auth/onboarding",
            payload=body.model_dump(), token=token,
        )
        if status_code != 200:
            raise HTTPException(
                status_code=status_code if status_code in (400, 401, 409, 422) else 502,
                detail=document.get("detail", "Onboarding could not be completed")
                if isinstance(document, dict) else "Onboarding could not be completed",
            )
        return document

    _oidc_cache: dict[str, str] | None = None

    def oidc_discovery() -> dict[str, str]:
        nonlocal _oidc_cache
        if _oidc_cache is None:
            with httpx.Client(timeout=cfg.auth_timeout_seconds) as client:
                response = client.get(
                    f"{cfg.oidc_issuer}/.well-known/openid-configuration"
                )
            if response.status_code != 200:
                raise HTTPException(status_code=503, detail="OIDC discovery failed")
            document = response.json()
            authorization = cfg.oidc_authorize_url or document.get(
                "authorization_endpoint"
            )
            token = cfg.oidc_token_url or document.get("token_endpoint")
            if not isinstance(authorization, str) or not isinstance(token, str):
                raise HTTPException(status_code=503, detail="OIDC discovery is incomplete")
            _oidc_cache = {
                "authorization_endpoint": authorization,
                "token_endpoint": token,
            }
        return _oidc_cache

    def pkce_pair() -> tuple[str, str]:
        verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(32))
            .rstrip(b"=")
            .decode("ascii")
        )
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        return verifier, challenge

    def oidc_authorize_url(state: str, nonce: str, challenge: str) -> str:
        endpoints = oidc_discovery()
        params = {
            "response_type": "code",
            "client_id": cfg.oidc_client_id,
            "redirect_uri": cfg.oidc_redirect_uri,
            "scope": cfg.oidc_scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{endpoints['authorization_endpoint']}?{urlencode(params)}"

    def oidc_exchange(code: str, verifier: str) -> dict[str, Any]:
        endpoints = oidc_discovery()
        data = {
            "grant_type": "authorization_code",
            "client_id": cfg.oidc_client_id,
            "client_secret": cfg.oidc_client_secret,
            "redirect_uri": cfg.oidc_redirect_uri,
            "code": code,
            "code_verifier": verifier,
        }
        with httpx.Client(timeout=cfg.auth_timeout_seconds) as client:
            response = client.post(endpoints["token_endpoint"], data=data)
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="OIDC token exchange failed")
        tokens = response.json()
        if not isinstance(tokens, dict) or not tokens.get("access_token"):
            raise HTTPException(status_code=502, detail="OIDC returned no access token")
        return tokens

    @app.get("/api/v1/auth/oidc/start")
    def oidc_start() -> dict[str, Any]:
        if not cfg.oidc_configured():
            raise HTTPException(status_code=503, detail="OIDC is not configured")
        verifier, challenge = pkce_pair()
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        with _connect(cfg) as conn:
            conn.execute(
                "DELETE FROM oidc_states WHERE created_at < ?", (time.time() - 1800,)
            )
            conn.execute(
                "INSERT INTO oidc_states (state, verifier, nonce, created_at) "
                "VALUES (?,?,?,?)",
                (state, verifier, nonce, time.time()),
            )
        return {
            "authorize_url": oidc_authorize_url(state, nonce, challenge),
            "configured": True,
        }

    @app.get("/api/v1/auth/oidc/callback", response_model=None)
    def oidc_callback(code: str | None = None, state: str | None = None) -> RedirectResponse:
        if not code or not state:
            raise HTTPException(status_code=400, detail="OIDC callback is incomplete")
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT verifier, created_at FROM oidc_states WHERE state = ?", (state,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=400, detail="OIDC state is invalid")
            conn.execute("DELETE FROM oidc_states WHERE state = ?", (state,))
        if time.time() - float(row["created_at"]) > 1800:
            raise HTTPException(status_code=400, detail="OIDC state expired")
        tokens = oidc_exchange(code, str(row["verifier"]))
        access_token = str(tokens["access_token"])
        refresh_token = str(tokens.get("refresh_token") or "")
        profile_status, profile = auth_call("GET", "/auth/me", token=access_token)
        if profile_status != 200 or not isinstance(profile, dict):
            raise HTTPException(status_code=502, detail="OIDC session could not be validated")
        response = RedirectResponse(
            f"{cfg.public_base_url}/auth-callback.html"
            f"#access_token={quote(access_token)}",
            status_code=302,
        )
        response.set_cookie(
            "chorus_access", access_token, httponly=True,
            secure=cfg.secure_cookies, samesite="lax", path="/api/v1", max_age=15 * 60,
        )
        if refresh_token:
            response.set_cookie(
                "chorus_refresh", refresh_token, httponly=True, secure=cfg.secure_cookies,
                samesite="lax", path="/api/v1/auth", max_age=30 * 24 * 60 * 60,
            )
        return response

    @app.post("/api/v1/auth/logout", status_code=204)
    def logout(response: Response, user: Principal = Depends(principal_dependency),
               authorization: str | None = Header(default=None)) -> Response:
        token = authorization[7:].strip() if authorization else ""
        auth_call("POST", "/auth/logout", token=token)
        response.delete_cookie("chorus_refresh", path="/api/v1/auth")
        response.status_code = 204
        return response

    @app.get("/api/v1/works/{work_id}/integrity")
    def work_integrity(work_id: str, user: Principal = Depends(current_user)) -> dict[str, Any]:
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT w.id AS work_id, r.id AS resource_id, f.id AS file_id, "
                "f.sha256, f.size_bytes, f.storage_pointer "
                "FROM works w JOIN resources r ON r.id = w.required_resource_id "
                "JOIN files f ON f.id = r.required_file_id "
                "WHERE w.id = ? AND w.owner_sub = ?",
                (work_id, user.sub),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Work not found")
        root = Path(cfg.storage_root).resolve()
        path = (root / row["storage_pointer"]).resolve()
        result: dict[str, Any] = {
            "work_id": row["work_id"],
            "resource_id": row["resource_id"],
            "file_id": row["file_id"],
            "expected_sha256": row["sha256"],
            "actual_sha256": None,
            "size_bytes": row["size_bytes"],
            "status": "unknown",
        }
        if path != root and root not in path.parents:
            result["status"] = "invalid_pointer"
            return result
        if not path.is_file():
            result["status"] = "missing"
            return result
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        result["actual_sha256"] = actual
        result["size_bytes"] = len(data)
        result["status"] = (
            "ok"
            if actual == row["sha256"] and len(data) == (row["size_bytes"] or 0)
            else "mismatch"
        )
        return result

    @app.get("/api/v1/library")
    def list_library(
        q: str | None = None, user: Principal = Depends(current_user)
    ) -> dict[str, Any]:
        query = (q or "").strip().lower()
        with _connect(cfg) as conn:
            if query:
                like = f"%{query}%"
                rows = conn.execute(
                    "SELECT * FROM library_items WHERE owner_sub = ? AND ("
                    "LOWER(title) LIKE ? OR LOWER(COALESCE(subtitle, '')) LIKE ? "
                    "OR LOWER(COALESCE(provider, '')) LIKE ? "
                    "OR LOWER(COALESCE(metadata_json, '')) LIKE ?) "
                    "ORDER BY created_at DESC, id DESC",
                    (user.sub, like, like, like, like),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM library_items WHERE owner_sub = ? "
                    "ORDER BY created_at DESC, id DESC",
                    (user.sub,),
                ).fetchall()
            collections = conn.execute(
                "SELECT c.*, (SELECT COUNT(*) FROM collection_items ci "
                "WHERE ci.collection_id = c.id) AS item_count "
                "FROM collections c WHERE c.owner_sub = ? ORDER BY c.name",
                (user.sub,),
            ).fetchall()
        return {
            "items": [library_item_dto(row) for row in rows],
            "collections": [collection_dto(row) for row in collections],
        }

    @app.post("/api/v1/library/references", status_code=201)
    def add_reference(body: LibraryReferenceBody, user: Principal = Depends(current_user)) -> Any:
        provider = body.provider.strip().lower()
        with _connect(cfg) as conn:
            existing = conn.execute(
                "SELECT * FROM library_items WHERE owner_sub = ? AND provider = ? "
                "AND external_work_id = ? "
                "AND COALESCE(external_resource_id, '') = COALESCE(?, '')",
                (user.sub, provider, body.work_id, body.representation_id),
            ).fetchone()
            if existing is not None:
                return library_item_dto(existing)
            now = utcnow()
            item_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO library_items "
                "(id,owner_sub,kind,provider,external_work_id,external_resource_id,"
                "title,subtitle,metadata_json,created_at,updated_at) "
                "VALUES (?,?, 'osap_reference', ?,?,?,?,?,?,?,?)",
                (
                    item_id,
                    user.sub,
                    provider,
                    body.work_id,
                    body.representation_id,
                    body.title.strip(),
                    body.subtitle,
                    json.dumps(body.metadata, ensure_ascii=False) if body.metadata else None,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM library_items WHERE id = ?", (item_id,)
            ).fetchone()
        return library_item_dto(row)

    @app.post("/api/v1/library/works/{work_id}", status_code=201)
    def add_local_work(work_id: str, user: Principal = Depends(current_user)) -> Any:
        with _connect(cfg) as conn:
            work = conn.execute(
                "SELECT id, title, subtitle FROM works WHERE id = ? AND owner_sub = ?",
                (work_id, user.sub),
            ).fetchone()
            if work is None:
                raise HTTPException(status_code=404, detail="Work not found")
            existing = conn.execute(
                "SELECT * FROM library_items WHERE owner_sub = ? AND work_id = ?",
                (user.sub, work_id),
            ).fetchone()
            if existing is not None:
                return library_item_dto(existing)
            now = utcnow()
            item_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO library_items "
                "(id,owner_sub,kind,work_id,title,subtitle,created_at,updated_at) "
                "VALUES (?,?, 'local_work', ?,?,?,?,?)",
                (item_id, user.sub, work_id, work["title"], work["subtitle"], now, now),
            )
            row = conn.execute(
                "SELECT * FROM library_items WHERE id = ?", (item_id,)
            ).fetchone()
        return library_item_dto(row)

    @app.delete("/api/v1/library/{item_id}", status_code=204)
    def remove_library_item(item_id: str, user: Principal = Depends(current_user)) -> Response:
        owned_library_item(item_id, user)
        with _connect(cfg) as conn:
            conn.execute(
                "DELETE FROM library_items WHERE id = ? AND owner_sub = ?",
                (item_id, user.sub),
            )
        return Response(status_code=204)

    @app.get("/api/v1/collections")
    def list_collections(user: Principal = Depends(current_user)) -> dict[str, Any]:
        with _connect(cfg) as conn:
            rows = conn.execute(
                "SELECT c.*, (SELECT COUNT(*) FROM collection_items ci "
                "WHERE ci.collection_id = c.id) AS item_count "
                "FROM collections c WHERE c.owner_sub = ? ORDER BY c.name",
                (user.sub,),
            ).fetchall()
        return {"collections": [collection_dto(row) for row in rows]}

    @app.post("/api/v1/collections", status_code=201)
    def create_collection(body: CollectionBody, user: Principal = Depends(current_user)) -> Any:
        now = utcnow()
        collection_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            existing = conn.execute(
                "SELECT 1 FROM collections WHERE owner_sub = ? AND name = ?",
                (user.sub, body.name.strip()),
            ).fetchone()
            if existing is not None:
                raise HTTPException(status_code=409, detail="Collection name already exists")
            conn.execute(
                "INSERT INTO collections (id,owner_sub,name,description,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (collection_id, user.sub, body.name.strip(), body.description, now, now),
            )
            row = conn.execute(
                "SELECT * FROM collections WHERE id = ?", (collection_id,)
            ).fetchone()
        return collection_dto(row)

    @app.post("/api/v1/collections/{collection_id}/items", status_code=201)
    def add_collection_item(
        collection_id: str, body: CollectionItemBody, user: Principal = Depends(current_user)
    ) -> Any:
        owned_collection(collection_id, user)
        owned_library_item(body.library_item_id, user)
        now = utcnow()
        with _connect(cfg) as conn:
            position = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM collection_items "
                "WHERE collection_id = ?",
                (collection_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT OR IGNORE INTO collection_items "
                "(collection_id,library_item_id,position,added_at) VALUES (?,?,?,?)",
                (collection_id, body.library_item_id, position, now),
            )
            row = conn.execute(
                "SELECT * FROM collection_items WHERE collection_id = ? AND library_item_id = ?",
                (collection_id, body.library_item_id),
            ).fetchone()
        return dict(row)

    @app.delete("/api/v1/collections/{collection_id}/items/{item_id}", status_code=204)
    def remove_collection_item(
        collection_id: str, item_id: str, user: Principal = Depends(current_user)
    ) -> Response:
        owned_collection(collection_id, user)
        with _connect(cfg) as conn:
            conn.execute(
                "DELETE FROM collection_items WHERE collection_id = ? AND library_item_id = ?",
                (collection_id, item_id),
            )
        return Response(status_code=204)

    @app.post("/api/v1/entity-leads", status_code=201)
    def create_entity_lead(body: EntityLeadBody) -> dict[str, str]:
        """Solicitud pública de alta de una entidad (sin autenticación)."""
        if body.company_website.strip():
            return {"id": "", "status": "received"}
        if not body.consent:
            raise HTTPException(status_code=400, detail="Consent is required")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", body.contact_email):
            raise HTTPException(status_code=400, detail="Invalid contact email")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", body.manager_email):
            raise HTTPException(status_code=400, detail="Invalid manager email")
        lead_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            conn.execute(
                "INSERT INTO entity_leads "
                "(id,entity_name,entity_kind,city,members,contact_name,contact_email,"
                "contact_phone,website,interests,message,consent,status,created_at,"
                "manager_name,manager_email,manager_has_account) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'new', ?,?,?,?)",
                (
                    lead_id,
                    body.entity_name.strip(),
                    body.entity_kind,
                    body.city,
                    body.members,
                    body.contact_name.strip(),
                    body.contact_email.strip().lower(),
                    body.contact_phone,
                    body.website,
                    json.dumps(body.interests),
                    body.message,
                    1,
                    utcnow(),
                    body.manager_name.strip(),
                    body.manager_email.strip().lower(),
                    1 if body.manager_has_account else 0,
                ),
            )
        return {"id": lead_id, "status": "received"}

    @app.get("/api/v1/admin/entity-leads")
    def list_entity_leads(
        user: Principal = Depends(current_user),
    ) -> list[dict[str, Any]]:
        """Solicitudes de alta para el admin de OSAP."""
        if "admin" not in user.roles:
            raise HTTPException(status_code=403, detail="Admin role required")
        with _connect(cfg) as conn:
            rows = conn.execute(
                "SELECT * FROM entity_leads ORDER BY created_at DESC LIMIT 200"
            ).fetchall()
        return [
            {
                "id": row["id"],
                "entity_name": row["entity_name"],
                "entity_kind": row["entity_kind"],
                "city": row["city"],
                "members": row["members"],
                "contact_name": row["contact_name"],
                "contact_email": row["contact_email"],
                "contact_phone": row["contact_phone"],
                "manager_name": row["manager_name"],
                "manager_email": row["manager_email"],
                "manager_has_account": bool(row["manager_has_account"]),
                "website": row["website"],
                "interests": json.loads(row["interests"] or "[]"),
                "message": row["message"],
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def _sync_osap_groups(conn, user_id: str, token: str | None) -> None:
        """Trae a Chorus los grupos de «Los amigos» del usuario autenticado."""
        if not token or not cfg.osap_api_base_url:
            return
        data, response = osap_call("GET", "/api/v1/amigos/my/groups", token=token)
        if response.status_code != 200 or not isinstance(data, list):
            return
        now = utcnow()
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get("group"), dict):
                continue
            group = item["group"]
            gid = str(group.get("id") or "")
            if not gid:
                continue
            role = "manager" if str(item.get("role")) == "admin" else "member"
            conn.execute(
                "INSERT OR IGNORE INTO groups "
                "(id,entity_id,name,timezone,created_by,join_code,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    gid,
                    gid,
                    str(group.get("name") or "Grupo"),
                    "Europe/Madrid",
                    user_id,
                    _join_code(),
                    now,
                    now,
                ),
            )
            member = conn.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_sub = ?",
                (gid, user_id),
            ).fetchone()
            if member is None:
                conn.execute(
                    "INSERT INTO group_members "
                    "(id,group_id,user_sub,role,status,display_name,joined_at,updated_at) "
                    "VALUES (?,?,?,?,'active',?,?,?)",
                    (uuid.uuid4().hex, gid, user_id, role, "", now, now),
                )
            else:
                conn.execute(
                    "UPDATE group_members SET role = ?, status = 'active', updated_at = ? "
                    "WHERE id = ?",
                    (role, now, member["id"]),
                )

    @app.get("/api/v1/agenda")
    def get_agenda(
        request: Request, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        memberships = _approved_memberships(profile)
        entity_ids = {
            str(membership["entity_id"])
            for membership in memberships
            if membership.get("entity_id")
        }
        with _connect(cfg) as conn:
            _sync_osap_groups(conn, user_id, request.cookies.get("chorus_access"))
            group_rows = conn.execute(
                "SELECT g.*, gm.role FROM group_members gm "
                "JOIN groups g ON g.id = gm.group_id "
                "WHERE gm.user_sub = ? AND gm.status = 'active' ORDER BY g.name",
                (user_id,),
            ).fetchall()
            group_ids = [row["id"] for row in group_rows]
            roles = {row["id"]: row["role"] for row in group_rows}

            visibility: list[str] = []
            params: list[Any] = []
            if admin:
                visibility.append("1 = 1")
            if group_ids:
                visibility.append(
                    "e.scope = 'groups' AND e.group_id IN ("
                    + ",".join("?" for _ in group_ids) + ")"
                )
                params.extend(group_ids)
            if entity_ids:
                visibility.append(
                    "e.scope = 'global' AND e.entity_id IN ("
                    + ",".join("?" for _ in entity_ids) + ")"
                )
                params.extend(sorted(entity_ids))
            events: list[sqlite3.Row] = []
            if visibility:
                events = conn.execute(
                    "SELECT e.*, g.name AS group_name, r.status AS my_rsvp "
                    "FROM events e LEFT JOIN groups g ON g.id = e.group_id "
                    "LEFT JOIN event_rsvps r ON r.event_id = e.id AND r.user_sub = ? "
                    "WHERE e.cancelled_at IS NULL AND e.starts_at >= ? AND ("
                    + " OR ".join(visibility) + ") "
                    "ORDER BY e.starts_at LIMIT 50",
                    (user_id, utcnow(), *params),
                ).fetchall()
        representative_entities = [
            {
                "id": str(membership["entity_id"]),
                "name": membership.get("entity_name") or "Entidad",
                "kind": membership.get("entity_kind") or "grupo",
            }
            for membership in memberships
            if admin or membership.get("is_representative") is True
        ]
        return {
            "groups": [
                _group_dto(
                    row,
                    row["role"],
                    admin or row["role"] == "manager",
                )
                for row in group_rows
            ],
            "entities": representative_entities,
            "can_create_group": admin or bool(representative_entities),
            "events": [
                _event_dto(
                    row,
                    my_rsvp=row["my_rsvp"],
                    group_name=row["group_name"],
                    can_manage=admin or roles.get(row["group_id"]) == "manager",
                )
                for row in events
            ],
        }

    @app.post("/api/v1/groups", status_code=201)
    def create_group(
        body: GroupBody, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        entity_id = body.entity_id.strip()
        if not _is_representative(profile, entity_id):
            raise HTTPException(
                status_code=403,
                detail="Only the entity representative can create groups",
            )
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Group name is required")
        now = utcnow()
        group_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            existing = conn.execute(
                "SELECT * FROM groups WHERE entity_id = ? AND name = ?",
                (entity_id, name),
            ).fetchone()
            if existing is not None:
                raise HTTPException(status_code=409, detail="Group name already exists")
            join_code = _join_code()
            while conn.execute(
                "SELECT 1 FROM groups WHERE join_code = ?", (join_code,)
            ).fetchone() is not None:
                join_code = _join_code()
            conn.execute(
                "INSERT INTO groups "
                "(id,entity_id,name,timezone,created_by,join_code,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    group_id, entity_id, name, body.timezone.strip(),
                    user_id, join_code, now, now,
                ),
            )
            conn.execute(
                "INSERT INTO group_members "
                "(id,group_id,user_sub,role,status,display_name,joined_at,updated_at) "
                "VALUES (?,?,?,'manager','active',?,?,?)",
                (uuid.uuid4().hex, group_id, user_id, str(profile.get("name") or profile.get("nickname") or ""), now, now),
            )
            row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        return _group_dto(row, "manager", True)

    @app.get("/api/v1/groups/{group_id}/catalog")
    def group_catalog(
        group_id: str,
        request: Request,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        token = request.cookies.get("chorus_access")
        if not token:
            return {"admin": [], "musical": [], "section": []}
        data, response = osap_call(
            "GET", f"/api/v1/amigos/groups/{quote(group_id)}/catalog", token=token
        )
        return data if response.status_code == 200 and isinstance(data, dict) else {
            "admin": [], "musical": [], "section": []
        }

    @app.patch("/api/v1/groups/{group_id}/members/{user_sub}")
    def update_group_member(
        group_id: str,
        user_sub: str,
        body: MemberUpdateBody,
        request: Request,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            actor = conn.execute(
                "SELECT role FROM group_members WHERE group_id=? AND user_sub=? "
                "AND status='active'", (group_id, user_id)
            ).fetchone()
            if not _is_admin(profile) and (actor is None or actor["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can edit")
            target = conn.execute(
                "SELECT * FROM group_members WHERE group_id=? AND user_sub=?",
                (group_id, user_sub),
            ).fetchone()
            if target is None:
                raise HTTPException(status_code=404, detail="Member not found")
            if body.status == "removed" and target["role"] == "manager":
                managers = conn.execute(
                    "SELECT COUNT(*) AS n FROM group_members WHERE group_id=? "
                    "AND role='manager' AND status='active'", (group_id,)
                ).fetchone()["n"]
                if int(managers) <= 1:
                    raise HTTPException(status_code=400, detail="The group needs a manager")
            token = request.cookies.get("chorus_access")
            if token:
                if body.status == "removed":
                    _, osap_response = osap_call(
                        "DELETE",
                        f"/api/v1/admin/amigos/groups/{quote(group_id)}/members/{quote(user_sub)}",
                        token=token,
                    )
                else:
                    _, osap_response = osap_call(
                        "POST",
                        f"/api/v1/admin/amigos/groups/{quote(group_id)}/members",
                        token=token,
                        payload={
                            "user_id": user_sub,
                            "role": "admin" if (body.role or target["role"]) == "manager" else "collaborator",
                            "admin_role_id": body.admin_role_id if body.admin_role_id is not None else target["admin_role_id"],
                            "musical_role_id": body.musical_role_id if body.musical_role_id is not None else target["musical_role_id"],
                            "section_id": body.section_id if body.section_id is not None else target["section_id"],
                        },
                    )
                if osap_response.status_code not in (200, 201):
                    raise HTTPException(status_code=502, detail="OSAP rejected the change")
            updates = []
            values: list[Any] = []
            for column in ("role", "admin_role_id", "musical_role_id", "section_id", "status"):
                value = getattr(body, column)
                if value is not None:
                    updates.append(f"{column}=?")
                    values.append(value)
            if not updates:
                return {"ok": True}
            values.append(utcnow())
            values.extend([group_id, user_sub])
            conn.execute(
                f"UPDATE group_members SET {', '.join(updates)}, updated_at=? "
                "WHERE group_id=? AND user_sub=?",
                tuple(values),
            )
        return {"ok": True}

    @app.delete("/api/v1/groups/{group_id}/members/{user_sub}")
    def remove_group_member(
        group_id: str,
        user_sub: str,
        request: Request,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        return update_group_member(
            group_id, user_sub, MemberUpdateBody(status="removed"), request, profile
        )
    @app.patch("/api/v1/groups/{group_id}")
    def update_group(
        group_id: str,
        body: GroupUpdateBody,
        request: Request,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? "
                "AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can edit")
            name = (body.name or group["name"]).strip()
            timezone = (body.timezone or group["timezone"]).strip()
            if not name or not timezone:
                raise HTTPException(status_code=400, detail="Name and timezone are required")
            token = request.cookies.get("chorus_access")
            if token:
                _, osap_response = osap_call(
                    "PATCH",
                    f"/api/v1/admin/amigos/groups/{quote(group_id)}",
                    token=token,
                    payload={"name": name},
                )
                if osap_response.status_code not in (200, 201):
                    raise HTTPException(status_code=502, detail="OSAP rejected the change")
            conn.execute(
                "UPDATE groups SET name = ?, timezone = ?, updated_at = ? WHERE id = ?",
                (name, timezone, utcnow(), group_id),
            )
            row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        return _group_dto(row, "manager", True)
    @app.post("/api/v1/groups/join")
    def join_group(
        body: JoinGroupBody, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        code = body.code.strip().upper()
        now = utcnow()
        with _connect(cfg) as conn:
            group = conn.execute(
                "SELECT * FROM groups WHERE join_code = ?", (code,)
            ).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Invalid group code")
            membership = conn.execute(
                "SELECT * FROM group_members WHERE group_id = ? AND user_sub = ?",
                (group["id"], user_id),
            ).fetchone()
            if membership is None:
                conn.execute(
                    "INSERT INTO group_members "
                    "(id,group_id,user_sub,role,status,display_name,joined_at,updated_at) "
                    "VALUES (?,?,?,'member','active',?,?,?)",
                    (
                        uuid.uuid4().hex,
                        group["id"],
                        user_id,
                        str(profile.get("name") or profile.get("nickname") or ""),
                        now,
                        now,
                    ),
                )
                role = "member"
            else:
                conn.execute(
                    "UPDATE group_members SET status = 'active', display_name = ?, "
                    "updated_at = ? WHERE id = ?",
                    (str(profile.get("name") or profile.get("nickname") or ""), now, membership["id"]),
                )
                role = membership["role"]
        return _group_dto(group, role, role == "manager")

    @app.get("/api/v1/groups/{group_id}/members")
    def group_members(
        group_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? "
                "AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and member is None:
                raise HTTPException(status_code=403, detail="Not a member of this group")
            rows = conn.execute(
                "SELECT user_sub, role, display_name, voice_label, section, "
                "admin_role_id, musical_role_id, section_id FROM group_members WHERE group_id = ? AND status = 'active' "
                "ORDER BY role DESC, display_name, user_sub",
                (group_id,),
            ).fetchall()
        return [
            {
                "user_sub": row["user_sub"],
                "role": row["role"],
                "name": row["display_name"] or row["user_sub"][:8],
                "voice_label": row["voice_label"],
                "section": row["section"],
                "admin_role_id": row["admin_role_id"],
                "musical_role_id": row["musical_role_id"],
                "section_id": row["section_id"],
            }
            for row in rows
        ]

    @app.get("/api/v1/messages/unread-count")
    def unread_messages(profile: dict[str, Any] = Depends(current_profile)) -> dict[str, int]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM message_recipients "
                "WHERE user_sub = ? AND read_at IS NULL",
                (user_id,),
            ).fetchone()
        return {"count": int(row["n"])}

    @app.get("/api/v1/messages/inbox")
    def messages_inbox(profile: dict[str, Any] = Depends(current_profile)) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            rows = conn.execute(
                "SELECT m.*, g.name AS group_name, r.read_at AS my_read_at "
                "FROM messages m JOIN groups g ON g.id = m.group_id "
                "JOIN message_recipients r ON r.message_id = m.id "
                "WHERE r.user_sub = ? OR m.sender_sub = ? "
                "ORDER BY m.created_at DESC LIMIT 100",
                (user_id, user_id),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "group_id": row["group_id"],
                "group_name": row["group_name"],
                "sender_sub": row["sender_sub"],
                "scope": row["scope"],
                "subject": row["subject"],
                "body": row["body"],
                "created_at": row["created_at"],
                "my_read_at": row["my_read_at"],
                "is_sender": row["sender_sub"] == user_id,
            }
            for row in rows
        ]

    @app.get("/api/v1/messages/{message_id}")
    def get_message(
        message_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT m.*, g.name AS group_name, "
                "(SELECT read_at FROM message_recipients r WHERE r.message_id=m.id "
                "AND r.user_sub=?) AS my_read_at FROM messages m "
                "JOIN groups g ON g.id=m.group_id WHERE m.id=?",
                (user_id, message_id),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Message not found")
            allowed = row["sender_sub"] == user_id or conn.execute(
                "SELECT 1 FROM message_recipients WHERE message_id=? AND user_sub=?",
                (message_id, user_id),
            ).fetchone() is not None
            if not allowed:
                raise HTTPException(status_code=403, detail="Not allowed")
        return {
            "id": row["id"], "group_id": row["group_id"], "group_name": row["group_name"],
            "sender_sub": row["sender_sub"], "scope": row["scope"],
            "subject": row["subject"], "body": row["body"], "created_at": row["created_at"],
            "my_read_at": row["my_read_at"], "is_sender": row["sender_sub"] == user_id,
        }

    @app.post("/api/v1/messages/{message_id}/reply", status_code=201)
    def reply_message(
        message_id: str,
        body: MessageReplyBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        text = body.body.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Message is required")
        now = utcnow()
        with _connect(cfg) as conn:
            original = conn.execute(
                "SELECT * FROM messages WHERE id=?", (message_id,)
            ).fetchone()
            if original is None:
                raise HTTPException(status_code=404, detail="Message not found")
            allowed = original["sender_sub"] == user_id or conn.execute(
                "SELECT 1 FROM message_recipients WHERE message_id=? AND user_sub=?",
                (message_id, user_id),
            ).fetchone() is not None
            if not allowed:
                raise HTTPException(status_code=403, detail="Not allowed")
            recipient = original["sender_sub"]
            new_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO messages (id,group_id,sender_sub,scope,subject,body,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (new_id, original["group_id"], user_id, "users",
                 f"Re: {original['subject']}", text, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO message_recipients (message_id,user_sub,read_at) "
                "VALUES (?,?,NULL)",
                (new_id, recipient),
            )
        return {"id": new_id, "group_id": original["group_id"], "status": "sent"}

    @app.get("/api/v1/groups/directory")
    def groups_directory(
        request: Request, profile: dict[str, Any] = Depends(current_profile)
    ) -> list[dict[str, Any]]:
        token = request.cookies.get("chorus_access")
        if not token:
            return []
        data, response = osap_call("GET", "/api/v1/amigos/groups", token=token)
        if response.status_code != 200 or not isinstance(data, list):
            return []
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            local = {
                row["id"]
                for row in conn.execute("SELECT id FROM groups").fetchall()
            }
            result = []
            for item in data:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                gid = str(item["id"])
                if gid not in local:
                    now = utcnow()
                    conn.execute(
                        "INSERT OR IGNORE INTO groups "
                        "(id,entity_id,name,timezone,created_by,join_code,created_at,updated_at) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (gid, gid, str(item.get("name") or "Grupo"), "Europe/Madrid",
                         user_id, _join_code(), now, now),
                    )
                member = conn.execute(
                    "SELECT 1 FROM group_members WHERE group_id=? AND user_sub=? "
                    "AND status='active'", (gid, user_id)
                ).fetchone()
                result.append({
                    "id": gid, "name": item.get("name"), "kind": item.get("kind"),
                    "joined": member is not None,
                })
        return result
    @app.get("/api/v1/groups/{group_id}/messages")
    def group_messages(
        group_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? "
                "AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            role = "manager" if admin else (str(member["role"]) if member is not None else "")
            rows = conn.execute(
                "SELECT m.*, gm.display_name AS sender_name, "
                "(SELECT read_at FROM message_recipients r "
                " WHERE r.message_id = m.id AND r.user_sub = ?) AS my_read_at, "
                "(SELECT COUNT(*) FROM message_recipients r "
                " WHERE r.message_id = m.id) AS recipient_count "
                "FROM messages m "
                "LEFT JOIN group_members gm ON gm.group_id = m.group_id "
                "AND gm.user_sub = m.sender_sub "
                "WHERE m.group_id = ? AND ("
                "m.sender_sub = ? OR EXISTS (SELECT 1 FROM message_recipients r "
                "WHERE r.message_id = m.id AND r.user_sub = ?) "
                "OR (? <> '' AND m.scope = 'group') "
                "OR (? = 'manager' AND m.scope = 'managers')) "
                "ORDER BY m.created_at DESC LIMIT 100",
                (user_id, group_id, user_id, user_id, role, role),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "group_id": row["group_id"],
                "sender_sub": row["sender_sub"],
                "sender_name": row["sender_name"] or row["sender_sub"][:8],
                "scope": row["scope"],
                "subject": row["subject"],
                "body": row["body"],
                "created_at": row["created_at"],
                "my_read_at": row["my_read_at"],
                "recipient_count": row["recipient_count"],
                "is_sender": row["sender_sub"] == user_id,
            }
            for row in rows
        ]

    @app.post("/api/v1/groups/{group_id}/messages", status_code=201)
    def create_message(
        group_id: str,
        body: MessageBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        subject = body.subject.strip()
        text = body.body.strip()
        if not subject or not text:
            raise HTTPException(status_code=400, detail="Subject and body are required")
        now = utcnow()
        message_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? "
                "AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if body.scope != "managers" and not admin and member is None:
                raise HTTPException(status_code=403, detail="Not a member of this group")

            if body.scope == "users":
                wanted = {sub for sub in body.recipient_subs if sub}
                if not wanted:
                    raise HTTPException(status_code=400, detail="Choose at least one recipient")
                rows = conn.execute(
                    "SELECT user_sub FROM group_members WHERE group_id = ? "
                    "AND status = 'active' AND user_sub IN ("
                    + ",".join("?" for _ in wanted) + ")",
                    (group_id, *sorted(wanted)),
                ).fetchall()
                recipients = {str(row["user_sub"]) for row in rows}
                if not recipients:
                    raise HTTPException(status_code=400, detail="Recipients are not group members")
            elif body.scope == "managers":
                rows = conn.execute(
                    "SELECT user_sub FROM group_members WHERE group_id = ? "
                    "AND status = 'active' AND role = 'manager'",
                    (group_id,),
                ).fetchall()
                recipients = {str(row["user_sub"]) for row in rows}
            else:
                rows = conn.execute(
                    "SELECT user_sub FROM group_members WHERE group_id = ? "
                    "AND status = 'active'",
                    (group_id,),
                ).fetchall()
                recipients = {str(row["user_sub"]) for row in rows}

            conn.execute(
                "INSERT INTO messages "
                "(id,group_id,sender_sub,scope,subject,body,created_at) VALUES (?,?,?,?,?,?,?)",
                (message_id, group_id, user_id, body.scope, subject, text, now),
            )
            for recipient in sorted(recipients):
                conn.execute(
                    "INSERT OR IGNORE INTO message_recipients "
                    "(message_id,user_sub,read_at) VALUES (?,?,NULL)",
                    (message_id, recipient),
                )
            row = conn.execute(
                "SELECT m.*, gm.display_name AS sender_name, "
                "(SELECT COUNT(*) FROM message_recipients r "
                " WHERE r.message_id = m.id) AS recipient_count "
                "FROM messages m LEFT JOIN group_members gm ON gm.group_id = m.group_id "
                "AND gm.user_sub = m.sender_sub WHERE m.id = ?",
                (message_id,),
            ).fetchone()
        return {
            "id": row["id"],
            "group_id": row["group_id"],
            "sender_sub": row["sender_sub"],
            "sender_name": row["sender_name"] or row["sender_sub"][:8],
            "scope": row["scope"],
            "subject": row["subject"],
            "body": row["body"],
            "created_at": row["created_at"],
            "my_read_at": None,
            "recipient_count": row["recipient_count"],
            "is_sender": True,
        }

    @app.post("/api/v1/messages/{message_id}/read")
    def mark_message_read(
        message_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, bool]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            message = conn.execute(
                "SELECT 1 FROM messages WHERE id = ?", (message_id,)
            ).fetchone()
            if message is None:
                raise HTTPException(status_code=404, detail="Message not found")
            updated = conn.execute(
                "UPDATE message_recipients SET read_at = ? "
                "WHERE message_id = ? AND user_sub = ? AND read_at IS NULL",
                (utcnow(), message_id, user_id),
            ).rowcount
            if not updated:
                exists = conn.execute(
                    "SELECT 1 FROM message_recipients WHERE message_id = ? AND user_sub = ?",
                    (message_id, user_id),
                ).fetchone()
                if exists is None:
                    raise HTTPException(status_code=404, detail="Message not found")
        return {"ok": True}

    @app.post("/api/v1/events", status_code=201)
    def create_event(
        body: EventBody, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        try:
            starts_at = _normalise_iso(body.starts_at)
            ends_at = _normalise_iso(body.ends_at) if body.ends_at else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid event date") from exc
        now = utcnow()
        event_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            group = conn.execute("SELECT * FROM groups WHERE id = ?", (body.group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            role = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? "
                "AND status = 'active'",
                (group["id"], user_id),
            ).fetchone()
            if not admin and (role is None or role["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Group manager role required")
            conn.execute(
                "INSERT INTO events "
                "(id,group_id,entity_id,scope,kind,title,starts_at,ends_at,location,notes,"
                "created_by,created_at,updated_at) "
                "VALUES (?,?,?,'groups',?,?,?,?,?,?,?,?,?)",
                (
                    event_id,
                    group["id"],
                    group["entity_id"],
                    body.kind,
                    body.title.strip(),
                    starts_at,
                    ends_at,
                    body.location,
                    body.notes,
                    user_id,
                    now,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO event_groups (event_id, group_id) VALUES (?,?)",
                (event_id, group["id"]),
            )
            row = conn.execute(
                "SELECT e.*, g.name AS group_name FROM events e "
                "JOIN groups g ON g.id = e.group_id WHERE e.id = ?",
                (event_id,),
            ).fetchone()
        return _event_dto(
            row, my_rsvp=None, group_name=row["group_name"], can_manage=True
        )

    @app.post("/api/v1/events/{event_id}/rsvp")
    def set_rsvp(
        event_id: str,
        body: RsvpBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            if event is None:
                raise HTTPException(status_code=404, detail="Event not found")
            if event["kind"] == "note":
                raise HTTPException(status_code=400, detail="Notes do not take RSVP")
            allowed = _is_admin(profile)
            if not allowed and event["scope"] == "global":
                allowed = any(
                    membership.get("entity_id") == event["entity_id"]
                    for membership in _approved_memberships(profile)
                )
            if not allowed:
                allowed = conn.execute(
                    "SELECT 1 FROM group_members WHERE group_id = ? AND user_sub = ? "
                    "AND status = 'active'",
                    (event["group_id"], user_id),
                ).fetchone() is not None
            if not allowed:
                allowed = conn.execute(
                    "SELECT 1 FROM event_groups eg JOIN group_members gm "
                    "ON gm.group_id = eg.group_id "
                    "WHERE eg.event_id = ? AND gm.user_sub = ? AND gm.status = 'active'",
                    (event_id, user_id),
                ).fetchone() is not None
            if not allowed:
                raise HTTPException(status_code=403, detail="Not a member of this group")
            conn.execute(
                "INSERT INTO event_rsvps (event_id,user_sub,status,comment,updated_at) "
                "VALUES (?,?,?,?,?) ON CONFLICT(event_id,user_sub) DO UPDATE SET "
                "status = excluded.status, comment = excluded.comment, "
                "updated_at = excluded.updated_at",
                (event_id, user_id, body.status, body.comment, utcnow()),
            )
        return {"event_id": event_id, "status": body.status}

    @app.post("/api/v1/catalog/searches")
    def catalog_search(payload: dict[str, Any], user: Principal = Depends(current_user),
                       authorization: str | None = Header(default=None)) -> Any:
        token = authorization[7:].strip() if authorization else None
        data, _ = osap_call("POST", "/api/v1/searches", payload=payload, token=token)
        return data

    @app.get("/api/v1/catalog/searches/{search_id}")
    def catalog_search_result(search_id: str, user: Principal = Depends(current_user),
                              authorization: str | None = Header(default=None)) -> Any:
        token = authorization[7:].strip() if authorization else None
        data, _ = osap_call("GET", f"/api/v1/searches/{quote(search_id, safe='')}", token=token)
        return data

    @app.get("/api/v1/catalog/representations/{representation_id}")
    def catalog_representation(representation_id: str, user: Principal = Depends(current_user),
                               authorization: str | None = Header(default=None)) -> Any:
        token = authorization[7:].strip() if authorization else None
        data, _ = osap_call("GET", f"/api/v1/representations/{quote(representation_id, safe='')}", token=token)
        return data

    @app.post("/api/v1/drafts", status_code=201)
    def create_draft(body: DraftBody, user: Principal = Depends(current_user)) -> dict[str, Any]:
        now = utcnow()
        draft_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            conn.execute(
                "INSERT INTO creation_drafts (id, owner_sub, status, source_kind, title, resource_type, created_at, updated_at) "
                "VALUES (?, ?, 'editing', 'blank', ?, ?, ?, ?)",
                (draft_id, user.sub, body.title, body.resource_type, now, now),
            )
            row = conn.execute("SELECT * FROM creation_drafts WHERE id = ?", (draft_id,)).fetchone()
        return draft_dto(row)

    @app.get("/api/v1/drafts/{draft_id}")
    def get_draft(draft_id: str, user: Principal = Depends(current_user)) -> dict[str, Any]:
        return draft_dto(owned_draft(draft_id, user))

    @app.post("/api/v1/drafts/{draft_id}/source")
    def select_source(draft_id: str, body: SourceBody, user: Principal = Depends(current_user),
                      authorization: str | None = Header(default=None)) -> dict[str, Any]:
        row = owned_draft(draft_id, user)
        if row["status"] != "editing":
            raise HTTPException(status_code=409, detail="Draft is not editable")
        token = authorization[7:].strip() if authorization else None
        encoded_representation_id = quote(body.representation_id, safe="")
        metadata, _ = osap_call("GET", f"/api/v1/representations/{encoded_representation_id}", token=token)
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=502, detail="Unexpected OSAP representation response")
        # El id de obra del índice y el que devuelve la ficha de la representación
        # pueden diferir (id interno vs public_id). La representación ya viene de la
        # búsqueda del usuario: no bloqueamos el borrador por esa diferencia.
        returned_work = metadata.get("work_id") or metadata.get("workId")
        requested_work = str(body.work_id or "").strip()
        if returned_work is not None:
            requested_ref = requested_work.removeprefix("index-")
            returned_ref = str(returned_work).strip().removeprefix("index-")
            if requested_ref != returned_ref:
                logger.info(
                    "draft source: work ref differs (requested=%s, representation=%s)",
                    requested_ref,
                    returned_ref,
                )
        # `work.work_id` de la búsqueda es un id estable (`work-…`) que el endpoint
        # público de obras no acepta; la ficha de la representación sí devuelve el id
        # público (`index-…`). Se usa ese y, si falla, se sigue con los metadatos de la
        # representación (el título ya viene de la búsqueda).
        work_metadata: dict[str, Any] = {}
        metadata_work_ref = str(returned_work or body.work_id)
        try:
            work_metadata, _ = osap_call(
                "GET",
                f"/api/v1/works/public/{quote(metadata_work_ref, safe='')}",
                token=token,
            )
        except HTTPException:
            work_metadata = {}
        _, downloaded = osap_call(
            "GET", f"/api/v1/representations/{encoded_representation_id}/download", token=token
        )
        raw = downloaded.content
        if len(raw) > cfg.max_upload_bytes:
            raise HTTPException(status_code=413, detail="OSAP source exceeds staging limit")
        disposition = downloaded.headers.get("content-disposition", "")
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disposition, re.I)
        filename = _safe_name(match.group(1) if match else metadata.get("file_name") or metadata.get("filename") or "source.mxl")
        suffix = Path(filename).suffix.lower()
        content_type = downloaded.headers.get("content-type", "").split(";", 1)[0].lower()
        if not raw or content_type in {"text/html", "application/xhtml+xml"} or suffix not in SUPPORTED_SOURCE_SUFFIXES:
            raise HTTPException(status_code=422, detail="OSAP source is unavailable or not importable by MuseEncore")
        if suffix == ".mxl":
            try:
                validate_mxl(raw, filename)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="OSAP MXL source is invalid") from exc
        pointer = _save_private(cfg, raw, suffix)
        sha = hashlib.sha256(raw).hexdigest()
        now = utcnow()
        rights = metadata.get("rights_license") or metadata.get("license") or metadata.get("licence")
        if rights is not None and not isinstance(rights, str):
            rights = json.dumps(rights, ensure_ascii=False)
        work_record = work_metadata.get("work") if isinstance(work_metadata, dict) else None
        if not isinstance(work_record, dict):
            work_record = work_metadata if isinstance(work_metadata, dict) else {}
        work_title = work_record.get("title") or metadata.get("title")
        with _connect(cfg) as conn:
            conn.execute(
                "UPDATE creation_drafts SET source_kind='osap', source_work_id=?, source_representation_id=?, "
                "source_provider=?, source_format=?, source_file_name=?, source_file_pointer=?, source_sha256=?, "
                "source_rights_license=?, title=COALESCE(title, ?), updated_at=? "
                "WHERE id=? AND owner_sub=? AND status='editing'",
                (body.work_id, body.representation_id, metadata.get("provider"), suffix.lstrip("."),
                 filename, pointer, sha, rights, work_title, now, draft_id, user.sub),
            )
            updated = conn.execute("SELECT * FROM creation_drafts WHERE id=?", (draft_id,)).fetchone()
        return draft_dto(updated)

    @app.get("/api/v1/drafts/{draft_id}/source-file", response_model=None)
    def download_draft_source(
        draft_id: str, user: Principal = Depends(current_user)
    ) -> Response:
        row = owned_draft(draft_id, user)
        if not row["source_file_pointer"]:
            raise HTTPException(status_code=404, detail="El borrador no tiene fichero de origen")
        raw = _read_private(cfg, str(row["source_file_pointer"]))
        filename = _safe_name(str(row["source_file_name"] or "chorus-source.mxl"))
        media = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return Response(
            raw,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/v1/library/{item_id}/draft", status_code=201)
    def draft_from_library(
        item_id: str,
        user: Principal = Depends(current_user),
        authorization: str | None = Header(default=None),
    ) -> Any:
        """Abre una obra de la biblioteca como borrador de edición."""
        item = owned_library_item(item_id, user)
        title = str(item["title"] or "Obra")
        if item["kind"] == "osap_reference":
            representation_id = str(item["external_resource_id"] or "")
            if not representation_id:
                raise HTTPException(
                    status_code=422,
                    detail="La referencia no tiene una representación descargable",
                )
            draft = create_draft(DraftBody(title=title), user)
            return select_source(
                str(draft["id"]),
                SourceBody(
                    work_id=str(item["external_work_id"] or ""),
                    representation_id=representation_id,
                ),
                user,
                authorization,
            )
        if not item["work_id"]:
            raise HTTPException(status_code=404, detail="La obra ya no existe")
        with _connect(cfg) as conn:
            work = conn.execute(
                "SELECT id, title, required_resource_id FROM works WHERE id = ? AND owner_sub = ?",
                (item["work_id"], user.sub),
            ).fetchone()
            if work is None:
                raise HTTPException(status_code=404, detail="Work not found")
            resource = conn.execute(
                "SELECT id, required_file_id, resource_type, rights_license FROM resources WHERE id = ?",
                (work["required_resource_id"],),
            ).fetchone()
            file_row = conn.execute(
                "SELECT id, name, mime_type, sha256, storage_pointer FROM files WHERE id = ?",
                (resource["required_file_id"] if resource else "",),
            ).fetchone()
        if resource is None or file_row is None:
            raise HTTPException(status_code=404, detail="File not found")
        raw = _read_private(cfg, str(file_row["storage_pointer"]))
        suffix = Path(str(file_row["name"])).suffix or ".mxl"
        pointer = _save_private(cfg, raw, suffix)
        sha = hashlib.sha256(raw).hexdigest()
        now = utcnow()
        draft_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            conn.execute(
                "INSERT INTO creation_drafts (id,owner_sub,status,source_kind,source_work_id,"
                "source_file_name,source_file_pointer,source_sha256,source_rights_license,"
                "title,resource_type,created_at,updated_at) "
                "VALUES (?,?, 'editing','local',?,?,?,?,?,?,?,?,?)",
                (
                    draft_id,
                    user.sub,
                    str(work["id"]),
                    str(file_row["name"]),
                    pointer,
                    sha,
                    resource["rights_license"],
                    title,
                    resource["resource_type"],
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM creation_drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        return draft_dto(row)

    @app.get("/api/v1/library/{item_id}/download", response_model=None)
    def download_library_item(
        item_id: str,
        user: Principal = Depends(current_user),
        authorization: str | None = Header(default=None),
    ) -> Response:
        """Descarga el fichero de una obra de la biblioteca (para MuseScore)."""
        item = owned_library_item(item_id, user)
        if item["kind"] == "osap_reference":
            representation_id = str(item["external_resource_id"] or "")
            if not representation_id:
                raise HTTPException(status_code=404, detail="La referencia no tiene fichero")
            token = authorization[7:].strip() if authorization else None
            _, downloaded = osap_call(
                "GET",
                f"/api/v1/representations/{quote(representation_id, safe='')}/download",
                token=token,
            )
            disposition = downloaded.headers.get("content-disposition", "")
            match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disposition, re.I)
            filename = _safe_name(
                match.group(1) if match else f"{item['title'] or 'obra'}.mxl"
            )
            media = downloaded.headers.get("content-type", "application/octet-stream")
            return Response(
                downloaded.content,
                media_type=media.split(";", 1)[0],
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        if not item["work_id"]:
            raise HTTPException(status_code=404, detail="La obra ya no existe")
        with _connect(cfg) as conn:
            work = conn.execute(
                "SELECT id, required_resource_id FROM works WHERE id = ? AND owner_sub = ?",
                (item["work_id"], user.sub),
            ).fetchone()
            resource = (
                conn.execute(
                    "SELECT required_file_id FROM resources WHERE id = ?",
                    (work["required_resource_id"],),
                ).fetchone()
                if work
                else None
            )
            file_row = (
                conn.execute(
                    "SELECT name, mime_type, storage_pointer FROM files WHERE id = ?",
                    (resource["required_file_id"],),
                ).fetchone()
                if resource
                else None
            )
        if file_row is None:
            raise HTTPException(status_code=404, detail="File not found")
        raw = _read_private(cfg, str(file_row["storage_pointer"]))
        filename = _safe_name(str(file_row["name"]))
        media = str(file_row["mime_type"] or "application/octet-stream")
        return Response(
            raw,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/v1/drafts/{draft_id}/editor")
    def open_editor(draft_id: str, user: Principal = Depends(current_user)) -> dict[str, str]:
        row = owned_draft(draft_id, user)
        if not cfg.editor_base_url:
            raise HTTPException(status_code=503, detail="MuseEncore editor URL is not configured")
        editor_url = cfg.editor_base_url.rstrip("/") + "/"
        if row["source_file_pointer"]:
            if not cfg.public_base_url or not cfg.editor_origin:
                raise HTTPException(
                    status_code=503,
                    detail="Public Chorus API URL and MuseEncore origin must be configured for source sharing",
                )
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires = (datetime.now(UTC) + timedelta(seconds=cfg.source_token_ttl_seconds)).isoformat()
            with _connect(cfg) as conn:
                conn.execute(
                    "INSERT INTO editor_source_tokens (token_hash, draft_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                    (token_hash, draft_id, expires, utcnow()),
                )
            source_name = _safe_name(str(row["source_file_name"] or "source.mxl"))
            if not Path(source_name).suffix:
                source_name += "." + str(row["source_format"] or "mxl").lstrip(".")
            # MuseEncore deduce el tipo por la extensión del nombre de la URL.
            source_url = (
                f"{cfg.public_base_url}/api/v1/editor-sources/{token}/{quote(source_name)}"
            )
            editor_url += ("&" if "?" in editor_url else "?") + urlencode({"url": source_url})
        return {"editor_url": editor_url}

    @app.get("/api/v1/editor-sources/{token}")
    @app.get("/api/v1/editor-sources/{token}/{filename}")
    def editor_source(
        token: str, request: Request, filename: str | None = None
    ) -> Response:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT t.expires_at, d.source_file_pointer, d.source_file_name, d.source_format "
                "FROM editor_source_tokens t JOIN creation_drafts d ON d.id=t.draft_id WHERE t.token_hash=?",
                (token_hash,),
            ).fetchone()
        if row is None or datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
            raise HTTPException(status_code=404, detail="Editor source link expired")
        raw = _read_private(cfg, row["source_file_pointer"])
        suffix = "." + (row["source_format"] or Path(row["source_file_name"] or "source.mxl").suffix.lstrip("."))
        media = mimetypes.guess_type("source" + suffix)[0] or "application/octet-stream"
        headers = {"Cache-Control": "no-store", "Content-Disposition": f'inline; filename="{_safe_name(row["source_file_name"])}"'}
        if request.headers.get("origin") == cfg.editor_origin:
            headers["Access-Control-Allow-Origin"] = cfg.editor_origin
            headers["Vary"] = "Origin"
        return Response(content=raw, media_type=media, headers=headers)

    @app.post("/api/v1/drafts/{draft_id}/files", status_code=201)
    async def upload_draft_file(
        draft_id: str, file: UploadFile = File(...), user: Principal = Depends(current_user)
    ) -> dict[str, Any]:
        row = owned_draft(draft_id, user)
        if row["status"] == "materialized":
            return {"draft_id": draft_id, "status": "materialized", "work_id": row["materialized_work_id"]}
        if row["status"] != "editing":
            raise HTTPException(status_code=409, detail="Draft is not editable")
        filename = _safe_name(file.filename)
        accepted_mimes = {
            "application/zip", "application/x-zip-compressed",
            "application/vnd.recordare.musicxml", "application/vnd.recordare.musicxml+xml",
            "application/octet-stream", "",
        }
        if (file.content_type or "").lower() not in accepted_mimes:
            raise HTTPException(status_code=415, detail="Unsupported upload MIME type for MXL")
        data = await file.read(cfg.max_upload_bytes + 1)
        if len(data) > cfg.max_upload_bytes:
            raise HTTPException(status_code=413, detail="File exceeds upload limit")
        try:
            validate_mxl(data, filename)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        pointer = _save_private(cfg, data, ".mxl")
        sha = hashlib.sha256(data).hexdigest()
        now = utcnow()
        work_id, resource_id, file_id = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
        title = row["title"] or Path(filename).stem
        provenance = None
        if row["source_kind"] == "osap":
            provenance = json.dumps({
                "provider": row["source_provider"],
                "source_work_id": row["source_work_id"],
                "source_representation_id": row["source_representation_id"],
                "source_format": row["source_format"],
                "source_sha256": row["source_sha256"],
            }, ensure_ascii=False)
        try:
            with _connect(cfg) as conn:
                conn.execute("BEGIN IMMEDIATE")
                current = conn.execute(
                    "SELECT status, materialized_work_id FROM creation_drafts WHERE id=? AND owner_sub=?",
                    (draft_id, user.sub),
                ).fetchone()
                if current is None:
                    raise HTTPException(status_code=404, detail="Draft not found")
                if current["status"] == "materialized":
                    conn.rollback()
                    target = Path(cfg.storage_root).resolve() / pointer
                    target.unlink(missing_ok=True)
                    return {"draft_id": draft_id, "status": "materialized",
                            "work_id": current["materialized_work_id"]}
                if current["status"] != "editing":
                    raise HTTPException(status_code=409, detail="Draft is not editable")
                conn.execute(
                    "INSERT INTO works (id,title,created_at,updated_at,required_resource_id,owner_sub) "
                    "VALUES (?,?,?,?,?,?)",
                    (work_id, title, now, now, resource_id, user.sub),
                )
                conn.execute(
                    "INSERT INTO resources (id,work_id,resource_type,title,provenance,rights_license,created_at,updated_at,required_file_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (resource_id, work_id, row["resource_type"], title, provenance,
                     row["source_rights_license"], now, now, file_id),
                )
                conn.execute(
                    "INSERT INTO files (id,resource_id,name,mime_type,size_bytes,status,sha256,storage_pointer,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,'available',?,?,?,?)",
                    (file_id, resource_id, filename, "application/vnd.recordare.musicxml", len(data), sha, pointer, now, now),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO library_items "
                    "(id,owner_sub,kind,work_id,title,created_at,updated_at) "
                    "VALUES (?,?, 'local_work', ?, ?, ?, ?)",
                    (uuid.uuid4().hex, user.sub, work_id, title, now, now),
                )
                changed = conn.execute(
                    "UPDATE creation_drafts SET status='materialized',materialized_work_id=?,updated_at=? "
                    "WHERE id=? AND owner_sub=? AND status='editing'",
                    (work_id, now, draft_id, user.sub),
                )
                if changed.rowcount != 1:
                    raise RuntimeError("Draft state changed during V6 materialization")
        except Exception:
            target = Path(cfg.storage_root).resolve() / pointer
            target.unlink(missing_ok=True)
            raise
        return {"draft_id": draft_id, "status": "materialized", "work_id": work_id,
                "resource_id": resource_id, "file_id": file_id, "sha256": sha}

    return app


app = create_app()














