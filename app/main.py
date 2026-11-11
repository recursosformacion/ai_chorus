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
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import Settings
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


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _connect(settings: Settings) -> sqlite3.Connection:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialise_database(settings: Settings) -> None:
    root = Path(__file__).resolve().parent.parent
    with _connect(settings) as conn:
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

    app = FastAPI(title="Chorus API", version="0.2.1", lifespan=lifespan)

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
        response.set_cookie(
            "chorus_refresh", str(doc["refresh_token"]), httponly=True, secure=cfg.secure_cookies,
            samesite="lax", path="/api/v1/auth", max_age=30 * 24 * 60 * 60,
        )
        result = {k: doc[k] for k in ("access_token", "user_id", "roles", "email_verified") if k in doc}
        result["onboarding"] = profile.get("onboarding")
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
            "chorus_refresh", str(doc["refresh_token"]), httponly=True, secure=cfg.secure_cookies,
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
