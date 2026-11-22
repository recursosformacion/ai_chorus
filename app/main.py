"""Chorus API pilot: osap-auth identity, OSAP read proxy and private creation drafts."""
from __future__ import annotations

import base64
import calendar
import hashlib
import json
import logging
import mimetypes
import re
import secrets
import sqlite3
import time
import unicodedata
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
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.db import connect as db_connect
from app.identity import IdentityClient, IdentityUnavailable, PublicIdentity
from app.db import (
    _verify_legacy_baseline,
    _register_legacy_baseline_recognition,
    _analyze_003_state,
    _safe_execute_migration,
    _is_migration_registered,
    _register_migration,
    _execute_sql_script,
)
from app.security import Principal
from app.utils import utcnow

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
    entity_id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(default="Europe/Madrid", max_length=80)
    kind: str = Field(default="grupo", max_length=32)
    foundation_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    dissolution_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    locality: str | None = Field(default=None, max_length=160)
    region: str | None = Field(default=None, max_length=160)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    venue: str | None = Field(default=None, max_length=255)
    formation_type: str | None = Field(default=None, max_length=48)
    member_count: int | None = Field(default=None, ge=0)
    public_email: str | None = Field(default=None, max_length=254)
    language: list[str] | None = Field(default=None)
    repertoire: list[dict[str, Any]] | None = Field(default=None)
    venues: list[dict[str, Any]] | None = Field(default=None)


class ArticleMediaBody(BaseModel):
    kind: str = Field(default="photo", max_length=16)
    url: str = Field(min_length=1, max_length=1024)
    provider: str | None = Field(default=None, max_length=32)
    video_id: str | None = Field(default=None, max_length=64)
    caption: str | None = Field(default=None, max_length=512)
    credit: str | None = Field(default=None, max_length=512)
    position: int = 0


class ArticleBody(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    summary: str | None = Field(default=None, max_length=4000)
    body: str | None = None
    cover_url: str | None = Field(default=None, max_length=1024)
    event_date: str | None = Field(default=None, max_length=32)
    status: Literal["draft", "pending", "published", "withdrawn"] = "draft"
    media: list[ArticleMediaBody] = Field(default_factory=list)


class ArticleUpdateBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    summary: str | None = Field(default=None, max_length=4000)
    body: str | None = None
    cover_url: str | None = Field(default=None, max_length=1024)
    event_date: str | None = Field(default=None, max_length=32)
    media: list[ArticleMediaBody] | None = None


class ArticleReviewBody(BaseModel):
    review_note: str | None = Field(default=None, max_length=512)


class GroupUpdateBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = Field(default=None, max_length=80)
    foundation_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    dissolution_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    locality: str | None = Field(default=None, max_length=160)
    region: str | None = Field(default=None, max_length=160)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    venue: str | None = Field(default=None, max_length=255)
    formation_type: str | None = Field(default=None, max_length=48)
    member_count: int | None = Field(default=None, ge=0)
    public_email: str | None = Field(default=None, max_length=254)
    language: list[str] | None = Field(default=None)
    repertoire: list[dict[str, Any]] | None = Field(default=None)
    venues: list[dict[str, Any]] | None = Field(default=None)


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
    group_id: str | None = Field(default=None, max_length=64)
    scope: Literal["personal", "group", "section", "users"] = "group"
    section_id: str | None = None
    recipient_subs: list[str] = Field(default_factory=list)
    kind: Literal["rehearsal", "concert", "note"]
    title: str = Field(min_length=1, max_length=200)
    starts_at: str = Field(min_length=10, max_length=64)
    ends_at: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=4000)
    recurrence: Literal["none", "daily", "monthly"] = "none"
    recurrence_until: str | None = Field(default=None, max_length=64)
    edit_scope: Literal["single", "series"] = "single"


class RsvpBody(BaseModel):
    status: Literal["yes", "no"]
    comment: str | None = Field(default=None, max_length=1000)


class MemberUpdateBody(BaseModel):
    role: Literal["manager", "member"] | None = None
    admin_role_id: str | None = None
    musical_role_id: str | None = None
    section_id: str | None = None
    status: Literal["active", "removed"] | None = None


class MemberSelfUpdateBody(BaseModel):
    voice_code: str | None = Field(default=None, max_length=32)
    voice_label: str | None = Field(default=None, max_length=64)
    section_id: str | None = Field(default=None, max_length=191)
    notify_email: bool | None = None
    notify_osap: bool | None = None
    notify_whatsapp: bool | None = None
    notify_sms: bool | None = None


class MemberCreateBody(BaseModel):
    user_sub: str = Field(min_length=1, max_length=191)
    role: Literal["manager", "member"] = "member"
    admin_role_id: str | None = Field(default=None, max_length=191)
    musical_role_id: str | None = Field(default=None, max_length=191)
    section_id: str | None = Field(default=None, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)


class AdminMemberCreateBody(BaseModel):
    """Incorporación de un usuario existente por administración global.

    No expone el campo ``role``: el alta administrativa siempre crea un miembro
    ordinario. La responsabilidad de gestor sólo la concede un gestor del grupo
    mediante el mantenimiento normal.
    """
    user_sub: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    admin_role_id: str | None = Field(default=None, max_length=191)
    musical_role_id: str | None = Field(default=None, max_length=191)
    section_id: str | None = Field(default=None, max_length=191)


class GroupRoleBody(BaseModel):
    scope: Literal["admin", "musical"]
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    parent_id: str | None = Field(default=None, max_length=191)
    sort_order: int = Field(default=0, ge=0)
    active: bool = True


class GroupRoleUpdateBody(BaseModel):
    scope: Literal["admin", "musical"] | None = None
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    parent_id: str | None = Field(default=None, max_length=191)
    sort_order: int | None = Field(default=None, ge=0)
    active: bool | None = None


class SocialLinkBody(BaseModel):
    kind: Literal["instagram", "facebook", "twitter", "youtube", "website", "other"]
    label: str | None = Field(default=None, max_length=160)
    url: str = Field(min_length=1, max_length=1024)
    position: int = Field(default=0, ge=0)


class SocialLinkUpdateBody(BaseModel):
    kind: Literal["instagram", "facebook", "twitter", "youtube", "website", "other"] | None = None
    label: str | None = Field(default=None, max_length=160)
    url: str | None = Field(default=None, min_length=1, max_length=1024)
    position: int | None = Field(default=None, ge=0)


class PerformanceGroupBody(BaseModel):
    group_id: str | None = Field(default=None, max_length=191)
    role: Literal["participant", "organizer", "guest"] = "participant"


class PreparationWorkBody(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    composer: str | None = Field(default=None, max_length=500)
    destination_type: Literal["repertoire", "program"] = "repertoire"
    event_name: str | None = Field(default=None, max_length=500)
    event_date: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=5000)


class PreparationWorkUpdateBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    composer: str | None = Field(default=None, max_length=500)
    destination_type: Literal["repertoire", "program"] | None = None
    event_name: str | None = Field(default=None, max_length=500)
    event_date: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=5000)
    status: Literal["preparing", "ready", "published", "archived"] | None = None


# Columnas actualizables de preparation_works vía PATCH. Todas admiten NULL,
# por lo que un envío explícito de null limpia el valor.
_PREP_WORK_UPDATABLE_COLUMNS = (
    "title",
    "composer",
    "destination_type",
    "event_name",
    "event_date",
    "notes",
    "status",
)

# Columnas NOT NULL en preparation_works: un null explícito se rechaza en vez
# de intentar escribir NULL contra la base de datos.
_PREP_WORK_NON_NULL_COLUMNS = frozenset({"title", "destination_type", "status"})

# Columnas actualizables de preparation_work_items y su nulabilidad en esquema.
_PREP_ITEM_UPDATABLE_COLUMNS = (
    "voice_label",
    "instrument",
    "custom_title",
    "sort_order",
    "status",
    "notes",
)
_PREP_ITEM_NON_NULL_COLUMNS = frozenset({"sort_order", "status"})


def _apply_patch_fields(
    body: Any,
    columns: tuple[str, ...],
    non_null_columns: frozenset[str],
    transform: dict[str, Any] | None = None,
) -> tuple[list[str], list[Any]]:
    """Traduce un modelo PATCH a asignaciones SQL con semántica estricta.

    - Campo omitido: no aparece en el resultado (conserva su valor).
    - Campo enviado con valor: se asigna.
    - Campo enviado como null: se asigna NULL si la columna lo admite; si la
      columna es NOT NULL se rechaza con 400 en lugar de provocar un error de BD.
    """
    provided = body.model_fields_set
    updates: list[str] = []
    values: list[Any] = []
    for column in columns:
        if column not in provided:
            continue
        value = getattr(body, column)
        if value is None and column in non_null_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Field '{column}' cannot be null",
            )
        if value is not None and transform and column in transform:
            value = transform[column](value)
        updates.append(f"{column}=?")
        values.append(value)
    return updates, values


class PreparationFileBody(BaseModel):
    part_label: str | None = Field(default=None, max_length=191)
    purpose: Literal["score", "part", "midi", "audio", "video", "reference", "other"] | None = None


class MessageReplyBody(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    all: bool = False


class MessageBody(BaseModel):
    scope: Literal["group", "managers", "users"]
    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=8000)
    recipient_subs: list[str] = Field(default_factory=list, max_length=200)


# ===== Spaces models =====
class SpaceCreateBody(BaseModel):
    space_type: Literal["personal", "group", "project"]
    group_id: str | None = Field(default=None, max_length=191)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class SpaceUpdateBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class SpaceConvertBody(BaseModel):
    target_type: Literal["group", "project"]
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


# ===== Preparation work items models =====
class PreparationWorkItemBody(BaseModel):
    work_id: str = Field(min_length=1, max_length=191)
    resource_id: str = Field(min_length=1, max_length=191)
    voice_label: str | None = Field(default=None, max_length=64)
    instrument: str | None = Field(default=None, max_length=64)
    custom_title: str | None = Field(default=None, max_length=200)
    sort_order: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=5000)


class PreparationWorkItemUpdateBody(BaseModel):
    voice_label: str | None = Field(default=None, max_length=64)
    instrument: str | None = Field(default=None, max_length=64)
    custom_title: str | None = Field(default=None, max_length=200)
    sort_order: int | None = Field(default=None, ge=0)
    status: Literal["pending", "rehearsing", "ready", "archived"] | None = None
    notes: str | None = Field(default=None, max_length=5000)


# ===== Preparation work files models =====
class PreparationWorkFileBody(BaseModel):
    file_id: str = Field(min_length=1, max_length=191)
    purpose: Literal["score", "part", "audio", "video", "other"] = "other"
    sort_order: int = Field(default=0, ge=0)


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


# ===== Autorización de grupos y membresías =====
# Modelo de roles de pertenencia (group_members.role): sólo hay dos valores.
#   - 'manager': gestor del grupo. Único rol que puede conceder/retirar la
#     responsabilidad de gestor.
#   - 'member' : miembro ordinario. Es el rol por defecto de cualquier alta.
# No existe un tercer rol de pertenencia. Los cargos administrativos y los
# roles musicales son catálogos del grupo (group_roles) y no confieren
# privilegios de gestión por sí mismos.
ORDINARY_MEMBER_ROLE = "member"
MANAGER_ROLE = "manager"


def _is_group_manager(conn, group_id: str, user_id: str) -> bool:
    """True si el usuario es gestor activo del grupo."""
    member = _group_membership(conn, group_id, user_id)
    return member is not None and member["role"] == MANAGER_ROLE


def _may_manage_group(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
    """Gestión ordinaria del grupo: admin de plataforma o gestor del grupo."""
    return _is_admin(profile) or _is_group_manager(conn, group_id, user_id)


def _may_grant_manager(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
    """Conceder o retirar la responsabilidad de gestor.

    Exclusivo de un gestor autorizado del propio grupo. Un administrador global
    NO puede otorgar permisos de gestor: sólo un gestor del grupo puede hacerlo,
    aunque el administrador global sea quien dé de alta al miembro.
    """
    return _is_group_manager(conn, group_id, user_id)


def _activity_legacy_id(prefix: str, user_sub: str) -> str:
    """Identificador único para activity_log.

    Evita colisiones cuando se registran varias operaciones del mismo usuario en
    el mismo segundo (el esquema exige unicidad en legacy_id).
    """
    return f"{prefix}-{user_sub[:8]}-{uuid.uuid4().hex[:12]}"


def _validate_group_catalog_refs(conn, group_id: str, *,
                                 admin_role_id: str | None = None,
                                 musical_role_id: str | None = None,
                                 section_id: str | None = None) -> None:
    """Rechaza identificadores de catálogo que no pertenezcan al grupo.

    Los catálogos (cargos, roles musicales y secciones) pertenecen al grupo y
    son los identificadores que se guardan en la pertenencia del miembro.
    """
    if admin_role_id is not None:
        role = conn.execute(
            "SELECT scope FROM group_roles WHERE id = ? AND group_id = ?",
            (admin_role_id, group_id),
        ).fetchone()
        if role is None:
            raise HTTPException(status_code=400, detail="Admin role not found in this group")
        if role["scope"] != "admin":
            raise HTTPException(status_code=400, detail="Admin role must have scope 'admin'")
    if musical_role_id is not None:
        role = conn.execute(
            "SELECT scope FROM group_roles WHERE id = ? AND group_id = ?",
            (musical_role_id, group_id),
        ).fetchone()
        if role is None:
            raise HTTPException(status_code=400, detail="Musical role not found in this group")
        if role["scope"] != "musical":
            raise HTTPException(status_code=400, detail="Musical role must have scope 'musical'")
    if section_id is not None:
        section = conn.execute(
            "SELECT 1 FROM group_sections WHERE id = ? AND group_id = ? AND active = 1",
            (section_id, group_id),
        ).fetchone()
        if section is None:
            raise HTTPException(status_code=400, detail="Section not found in this group")


def _is_representative(profile: dict[str, Any], entity_id: str) -> bool:
    return _is_admin(profile) or any(
        membership.get("entity_id") == entity_id
        and membership.get("is_representative") is True
        for membership in _approved_memberships(profile)
    )


# ===== Spaces helpers =====
def _get_space(conn, space_id: str) -> dict[str, Any] | None:
    """Devuelve la fila del espacio o None."""
    row = conn.execute(
        "SELECT id, space_type, owner_sub, group_id, name, description, created_at, updated_at "
        "FROM spaces WHERE id = ?",
        (space_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def _is_space_owner(conn, space_id: str, user_id: str) -> bool:
    """Check if user is the owner of a space."""
    space = _get_space(conn, space_id)
    return space is not None and space["owner_sub"] == user_id


def _group_membership(conn, group_id: str, user_id: str) -> dict[str, Any] | None:
    """Devuelve la membresía activa del usuario en un grupo, o None."""
    row = conn.execute(
        "SELECT role, musical_role_id FROM group_members "
        "WHERE group_id = ? AND user_sub = ? AND status = 'active'",
        (group_id, user_id),
    ).fetchone()
    return dict(row) if row is not None else None


def _has_musical_director_role(conn, group_id: str, musical_role_id: str | None) -> bool:
    """True si el rol musical es de dirección (code o name contienen 'director')."""
    if not musical_role_id:
        return False
    role = conn.execute(
        "SELECT scope, code, name FROM group_roles WHERE id = ? AND group_id = ?",
        (musical_role_id, group_id),
    ).fetchone()
    if role is None or role["scope"] != "musical":
        return False
    code = (role["code"] or "").lower()
    name = (role["name"] or "").lower()
    return code == "director" or "director" in name


def _can_manage_space(conn, space_id: str, user_id: str, profile: dict[str, Any]) -> bool:
    """Gestión general del espacio (nombre, descripción, miembros, configuración).

    - Admin de plataforma: sí.
    - Espacio personal: sólo su propietario.
    - Espacio de grupo/proyecto: manager activo del grupo. Ser creador del
      espacio NO concede permisos permanentes: si el usuario deja de ser
      manager del grupo, pierde la gestión.
    """
    if _is_admin(profile):
        return True
    space = _get_space(conn, space_id)
    if space is None:
        return False
    if space["space_type"] == "personal":
        return space["owner_sub"] == user_id
    if not space["group_id"]:
        return False
    member = _group_membership(conn, space["group_id"], user_id)
    return member is not None and member["role"] == "manager"


def _can_manage_space_preparation(conn, space_id: str, user_id: str, profile: dict[str, Any]) -> bool:
    """Gestión de trabajos de preparación dentro de un espacio.

    - Admin de plataforma: sí.
    - Espacio personal: sólo su propietario.
    - Espacio de grupo/proyecto: manager del grupo, o miembro con rol musical
      de dirección (se mantiene el permiso histórico de director musical).
      Los roles musicales NO son permisos administrativos: sólo habilitan la
      preparación, no la gestión del espacio ni de sus miembros.
    """
    if _can_manage_space(conn, space_id, user_id, profile):
        return True
    space = _get_space(conn, space_id)
    if space is None or not space["group_id"]:
        return False
    member = _group_membership(conn, space["group_id"], user_id)
    if member is None:
        return False
    return _has_musical_director_role(conn, space["group_id"], member["musical_role_id"])


def _can_view_space(conn, space_id: str, user_id: str, profile: dict[str, Any]) -> bool:
    """Consulta de un espacio.

    - Admin de plataforma: sí.
    - Espacio personal: sólo su propietario.
    - Espacio de grupo/proyecto: cualquier miembro activo del grupo.
    """
    if _is_admin(profile):
        return True
    space = _get_space(conn, space_id)
    if space is None:
        return False
    if space["space_type"] == "personal":
        return space["owner_sub"] == user_id
    if not space["group_id"]:
        return False
    return _group_membership(conn, space["group_id"], user_id) is not None


def _resource_section_allowed(conn, group_id: str | None, section_id: str | None,
                              user_id: str) -> bool:
    """Acceso a una Resource restringida a una sección concreta.

    - Sin sección restringida: sin restricción adicional.
    - Manager del grupo: acceso a todas las secciones.
    - Miembro: sólo si su ``group_members.section_id`` coincide.
    """
    if not section_id:
        return True
    if not group_id:
        return False
    member = _group_membership(conn, group_id, user_id)
    if member is None:
        return False
    if member["role"] == "manager":
        return True
    row = conn.execute(
        "SELECT section_id FROM group_members "
        "WHERE group_id = ? AND user_sub = ? AND status = 'active'",
        (group_id, user_id),
    ).fetchone()
    if row is None:
        return False
    return row["section_id"] == section_id


def _can_use_work_in_space(conn, space: dict[str, Any], user_id: str, profile: dict[str, Any],
                           work_id: str, resource_id: str) -> bool:
    """Valida que el usuario puede incorporar una Work/Resource a un espacio.

    Reglas:
    - Admin de plataforma: sí.
    - Work propia (works.owner_sub = user_id): sí, salvo que la Resource esté
      restringida a una sección del grupo y el usuario no pertenezca a ella.
    - Resource compartida con el grupo del espacio (resources.group_id): sí,
      respetando la restricción de sección.
    - Cualquier otro caso: no (evita incorporar material privado ajeno).
    """
    if _is_admin(profile):
        return True
    row = conn.execute(
        "SELECT w.owner_sub AS work_owner, r.work_id AS resource_work_id, "
        "       r.group_id AS resource_group, r.group_section_id AS section_id "
        "FROM resources r JOIN works w ON w.id = r.work_id WHERE r.id = ?",
        (resource_id,),
    ).fetchone()
    if row is None or row["resource_work_id"] != work_id:
        return False

    space_group_id = space.get("group_id")
    if not _resource_section_allowed(
        conn, row["resource_group"], row["section_id"], user_id
    ):
        return False

    if row["work_owner"] is not None and row["work_owner"] == user_id:
        return True
    if space_group_id and row["resource_group"] == space_group_id:
        return True
    return False


def _can_use_file_in_space(conn, space: dict[str, Any], user_id: str, profile: dict[str, Any],
                           file_id: str) -> bool:
    """Valida que el usuario puede asociar un File existente a un espacio.

    Un archivo pertenece a una Resource, que a su vez pertenece a una Work.
    Se permite si el usuario es propietario de la Work, o si la Resource está
    compartida con el grupo del espacio (respetando restricción de sección),
    o si es admin. Un identificador conocido NO basta para apropiarse del
    archivo de otro usuario.
    """
    if _is_admin(profile):
        return True
    row = conn.execute(
        "SELECT r.id AS resource_id, r.work_id AS resource_work_id, "
        "       r.group_id AS resource_group, r.group_section_id AS section_id, "
        "       w.owner_sub AS work_owner "
        "FROM files f JOIN resources r ON r.id = f.resource_id "
        "JOIN works w ON w.id = r.work_id WHERE f.id = ?",
        (file_id,),
    ).fetchone()
    if row is None:
        return False

    space_group_id = space.get("group_id")
    if not _resource_section_allowed(
        conn, row["resource_group"], row["section_id"], user_id
    ):
        return False

    if row["work_owner"] is not None and row["work_owner"] == user_id:
        return True
    if space_group_id and row["resource_group"] == space_group_id:
        return True
    return False


def _normalise_iso(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _parse_dt(value: str) -> datetime:
    raw = value.strip()
    if len(raw) == 10:
        raw += "T23:59:59+00:00"
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _occurrence_times(
    starts_at: str, ends_at: str | None, recurrence: str, until: str | None
) -> list[tuple[str, str]]:
    start = _parse_dt(starts_at)
    end = _parse_dt(ends_at) if ends_at else start + timedelta(hours=1)
    if end <= start:
        raise ValueError("ends_at must be after starts_at")
    if recurrence == "none":
        return [(start.isoformat(), end.isoformat())]
    if not until:
        raise ValueError("recurrence_until is required")
    limit = _parse_dt(until)
    if limit < start:
        raise ValueError("recurrence_until must be after starts_at")
    duration = end - start
    rows: list[tuple[str, str]] = []
    cursor = start
    while cursor <= limit and len(rows) < 400:
        rows.append((cursor.isoformat(), (cursor + duration).isoformat()))
        cursor = cursor + timedelta(days=1) if recurrence == "daily" else _add_months(cursor, 1)
    if not rows:
        raise ValueError("recurrence produces no occurrences")
    return rows


def _creator_badge(scope: str, role: str | None, is_admin: bool = False) -> str:
    if scope == "personal":
        return "P"
    if scope == "section":
        return "S"
    return "D" if is_admin else "G"


def _insert_event_rows(
    conn,
    *,
    body: "EventBody",
    user_id: str,
    group,
    entity_id: str,
    stored_scope: str,
    series_id: str | None,
    badge: str,
) -> list[str]:
    until = _normalise_iso(body.recurrence_until) if body.recurrence_until else None
    occurrences = _occurrence_times(
        _normalise_iso(body.starts_at),
        _normalise_iso(body.ends_at) if body.ends_at else None,
        body.recurrence,
        until,
    )
    now = utcnow()
    ids: list[str] = []
    for starts_at, ends_at in occurrences:
        event_id = uuid.uuid4().hex
        ids.append(event_id)
        conn.execute(
            "INSERT INTO events "
            "(id,group_id,entity_id,scope,kind,title,starts_at,ends_at,location,notes,"
            "created_by,created_at,updated_at,recurrence,recurrence_until,series_id,creator_badge) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event_id, group["id"] if group is not None else None, entity_id,
                stored_scope, body.kind, body.title.strip(), starts_at, ends_at,
                body.location, body.notes, user_id, now, now, body.recurrence,
                until, series_id, badge,
            ),
        )
        if group is not None:
            conn.execute(
                "INSERT OR IGNORE INTO event_groups (event_id, group_id) VALUES (?,?)",
                (event_id, group["id"]),
            )
        if body.scope == "section" and body.section_id:
            conn.execute(
                "INSERT OR IGNORE INTO event_targets (event_id,target_type,target_value) VALUES (?,?,?)",
                (event_id, "section", body.section_id),
            )
        if body.scope == "users":
            for sub in body.recipient_subs:
                conn.execute(
                    "INSERT OR IGNORE INTO event_targets (event_id,target_type,target_value) VALUES (?,?,?)",
                    (event_id, "user", sub),
                )
    return ids


def _can_manage_event(conn, event, user_id: str, profile: dict[str, Any]) -> bool:
    if _is_admin(profile) or str(event["created_by"]) == user_id:
        return True
    if event["group_id"]:
        member = conn.execute(
            "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
            (event["group_id"], user_id),
        ).fetchone()
        return member is not None and member["role"] == "manager"
    return False

def _group_dto(row: sqlite3.Row, role: str, can_manage: bool) -> dict[str, Any]:
    def _parse_json(value: str | None):
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    return {
        "id": row["id"],
        "entity_id": row["entity_id"],
        "name": row["name"],
        "timezone": row["timezone"],
        "join_code": row["join_code"],
        "role": role,
        "can_manage": can_manage,
        "foundation_date": row["foundation_date"],
        "dissolution_date": row["dissolution_date"],
        "locality": row["locality"],
        "region": row["region"],
        "country_code": row["country_code"],
        "venue": row["venue"],
        "formation_type": row["formation_type"],
        "member_count": row["member_count"],
        "public_email": row["public_email"],
        "language": _parse_json(row["language"]),
        "repertoire": _parse_json(row["repertoire"]),
        "venues": _parse_json(row["venues"]),
    }


def _slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:180] or "articulo"


def _article_media(conn, article_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM group_article_media WHERE article_id=? ORDER BY position, id",
        (article_id,),
    ).fetchall()
    return [
        {
            "id": row["id"], "kind": row["kind"], "url": row["url"],
            "provider": row["provider"], "video_id": row["video_id"],
            "caption": row["caption"], "credit": row["credit"],
            "position": row["position"],
        }
        for row in rows
    ]


def _article_dto(conn, row, *, can_edit: bool = False, can_publish: bool = False) -> dict[str, Any]:
    return {
        "id": row["id"],
        "group_id": row["group_id"],
        "title": row["title"],
        "slug": row["slug"],
        "summary": row["summary"],
        "body": row["body"],
        "cover_url": row["cover_url"],
        "event_date": row["event_date"],
        "status": row["status"],
        "author_user_id": row["author_user_id"],
        "publisher_user_id": row["publisher_user_id"],
        "reviewed_by": row["reviewed_by"],
        "reviewed_at": row["reviewed_at"],
        "review_note": row["review_note"],
        "published_at": row["published_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "media": _article_media(conn, row["id"]),
        "can_edit": can_edit,
        "can_publish": can_publish,
    }


def _article_permissions(conn, row, user_id: str, profile: dict[str, Any]) -> tuple[bool, bool]:
    admin = _is_admin(profile)
    member = conn.execute(
        "SELECT role FROM group_members WHERE group_id=? AND user_sub=? AND status='active'",
        (row["group_id"], user_id),
    ).fetchone()
    role = member["role"] if member is not None else None
    # Modelo único de roles de pertenencia: 'manager' o 'member'.
    can_edit = admin or role == MANAGER_ROLE or str(row["author_user_id"]) == user_id
    can_publish = admin or role == MANAGER_ROLE
    return can_edit, can_publish


def _replace_article_media(conn, article_id: str, media: list["ArticleMediaBody"], now: str) -> None:
    conn.execute("DELETE FROM group_article_media WHERE article_id=?", (article_id,))
    for index, item in enumerate(media):
        conn.execute(
            "INSERT INTO group_article_media "
            "(id,article_id,kind,url,provider,video_id,caption,credit,position,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                uuid.uuid4().hex, article_id, item.kind, item.url, item.provider,
                item.video_id, item.caption, item.credit,
                item.position if item.position else index, now,
            ),
        )

def _join_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _event_dto(
    row: sqlite3.Row, *, my_rsvp: str | None, my_rsvp_updated_at: str | None = None, group_name: str | None = None, can_manage: bool = False
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
        "my_rsvp_updated_at": my_rsvp_updated_at,
        "rsvp_required": row["kind"] != "note",
        "can_manage": can_manage,
        "created_by": row["created_by"],
        "recurrence": row["recurrence"] or "none",
        "recurrence_until": row["recurrence_until"],
        "series_id": row["series_id"],
        "creator_badge": row["creator_badge"] or ("P" if row["scope"] == "global" else "D"),
        "section_id": row["section_id"],
        "is_series": bool(row["series_id"]),
    }


def _group_role_dto(row: dict[str, Any], children: list | None = None) -> dict[str, Any]:
    return {
        "id": row["id"],
        "legacy_id": row["legacy_id"],
        "group_id": row["group_id"],
        "scope": row["scope"],
        "code": row["code"],
        "name": row["name"],
        "parent_id": row["parent_id"],
        "sort_order": row["sort_order"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "children": children or [],
    }


def _social_link_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "legacy_id": row["legacy_id"],
        "group_id": row["group_id"],
        "kind": row["kind"],
        "label": row["label"],
        "url": row["url"],
        "position": row["position"],
        "created_at": row["created_at"],
    }


def _legacy_upload_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "legacy_file_id": row["legacy_file_id"],
        "group_id": row["group_id"],
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "chorus_file_id": row["chorus_file_id"],
    }


def _activity_log_dto(row: dict[str, Any]) -> dict[str, Any]:
    detail = row["detail_json"]
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except json.JSONDecodeError:
            detail = None
    return {
        "id": row["id"],
        "legacy_id": row["legacy_id"],
        "group_id": row["group_id"],
        "article_id": row["article_id"],
        "event_type": row["event_type"],
        "actor": row["actor"],
        "from_status": row["from_status"],
        "to_status": row["to_status"],
        "detail_json": detail,
        "created_at": row["created_at"],
    }

def _performance_groups_dto(conn: Any, performance_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT pg.group_id, pg.role, g.name AS group_name, g.slug AS group_slug "
        "FROM performance_groups pg LEFT JOIN groups g ON g.id = pg.group_id "
        "WHERE pg.performance_id = ? ORDER BY g.name, pg.group_id",
        (performance_id,),
    ).fetchall()
    return [
        {
            "group_id": row["group_id"],
            "group_name": row["group_name"],
            "group_slug": row["group_slug"],
            "role": row["role"],
        }
        for row in rows
    ]


def _performance_dto(row: Any, groups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """DTO de lectura de una actuacion. No expone datos internos de contacto."""
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "summary": row["summary"],
        "description": row["description"],
        "image_url": row["image_url"],
        "kind": row["kind"],
        "modality": row["modality"],
        "event_status": row["event_status"],
        "editorial_status": row["editorial_status"],
        "starts_on": row["starts_on"],
        "starts_at": row["starts_at"],
        "ends_at": row["ends_at"],
        "venue_address": row["venue_address"],
        "latitude": str(row["latitude"]) if row["latitude"] is not None else None,
        "longitude": str(row["longitude"]) if row["longitude"] is not None else None,
        "map_url": row["map_url"],
        "organizer_name": row["organizer_name"],
        "organizer_website": row["organizer_website"],
        "event_url": row["event_url"],
        "tickets_url": row["tickets_url"],
        "price": row["price"],
        "access_info": row["access_info"],
        "public_contact": row["public_contact"],
        "registration_deadline": row["registration_deadline"],
        "views": row["views"],
        "published_at": row["published_at"],
        "cancelled_at": row["cancelled_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "groups": groups or [],
    }


def _connect(settings: Settings):
    return db_connect(settings)


def _has_application_tables(conn: Any) -> bool:
    """Verifica si ya existen tablas de aplicación (instalación legacy).
    Comprueba la EXISTENCIA de la tabla, no que contenga filas."""
    try:
        from app.db import _table_exists
        return _table_exists(conn, "groups")
    except Exception:
        return False


def initialise_database(settings: Settings) -> None:
    root = Path(__file__).resolve().parent.parent
    migrations_dir = root / "migrations"

    with _connect(settings) as conn:
        # Asegurar tabla de migraciones
        if settings.database_url:
            # MySQL/MariaDB
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chorus_schema_migrations (
                    name VARCHAR(191) PRIMARY KEY,
                    applied_at VARCHAR(64) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
        else:
            # SQLite
            conn.execute(
                "CREATE TABLE IF NOT EXISTS chorus_schema_migrations "
                "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )

        if not settings.database_url:
            # SQLite: mantener comportamiento existente (15 migraciones incrementales)
            sqlite_migrations = (
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
                "011_event_targets.sql",
                "012_material_library.sql",
                "013_material_groups.sql",
                "014_agenda_recurrence.sql",
                "015_group_articles.sql",
            )
            for name in sqlite_migrations:
                applied = conn.execute(
                    "SELECT 1 FROM chorus_schema_migrations WHERE name = ?", (name,)
                ).fetchone()
                if applied is None:
                    script = (migrations_dir / "sqlite" / name).read_text("utf-8")
                    conn.executescript("BEGIN IMMEDIATE;\n" + script + "\nCOMMIT;")
                    conn.execute(
                        "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
                        (name, utcnow()),
                    )
            return

        # MySQL/MariaDB
        is_new_install = not _has_application_tables(conn)

        if is_new_install:
            # --- INSTALACIÓN NUEVA ---
            # 1. Ejecutar 001_schema.sql (esquema base completo)
            script = (migrations_dir / "mysql" / "001_schema.sql").read_text("utf-8")
            action = _safe_execute_migration(conn, "001_schema.sql", script)
            if action == "EXECUTE":
                _execute_sql_script(conn, script, is_mysql=True)
                _register_migration(conn, "001_schema.sql")
            # action SKIP or SKIP_EXISTED means already registered or objects exist

            # 2. Ejecutar migraciones nuevas 004-007
            new_migrations = [
                "004_material_library.sql",
                "005_material_groups.sql",
                "006_group_articles_tables.sql",
                "007_events_series_index.sql",
            ]
            for mig_name in new_migrations:
                mig_path = migrations_dir / "mysql" / mig_name
                if not mig_path.exists():
                    raise RuntimeError(f"Migración no encontrada: {mig_path}")
                script = mig_path.read_text("utf-8")
                action = _safe_execute_migration(conn, mig_name, script)
                if action == "EXECUTE":
                    _execute_sql_script(conn, script, is_mysql=True)
                    _register_migration(conn, mig_name)
                # SKIP or SKIP_EXISTED handled by _safe_execute_migration

            # NO ejecutar 009_legacy_baseline — no hay legacy que reconocer
            return

        # --- INSTALACIÓN HISTÓRICA (legacy) ---
        # Primero, comprobar si ya está todo migrado (instalación nueva ya completada)
        all_new_migrations = [
            "004_material_library.sql",
            "005_material_groups.sql",
            "006_group_articles_tables.sql",
            "007_events_series_index.sql",
        ]
        if all(_is_migration_registered(conn, m) for m in all_new_migrations):
            # Ya está todo migrado, no hay nada que hacer
            return

        # Verificar baseline histórico
        ok, errors = _verify_legacy_baseline(conn, settings)
        if not ok:
            raise RuntimeError(f"Baseline histórico incompatible: {'; '.join(errors)}")

        # Registrar reconocimiento de baseline (operación Python)
        _register_legacy_baseline_recognition(conn)

        # Analizar estado de migraciones históricas 002 y 003
        # 002_agenda_recurrence.sql: solo índice idx_events_series (columnas ya en 001)
        # 003_group_articles.sql: 3 CREATE TABLE necesarios + ALTER TABLE redundantes
        state_003 = _analyze_003_state(conn)

        if state_003 in ("REGISTERED_TABLES_MISSING", "PARTIAL_TABLES"):
            raise RuntimeError(
                f"Estado contradictorio en 003_group_articles.sql: {state_003}. "
                "Migración registrada pero tablas incompletas. ABORTAR."
            )
        if state_003 == "PARTIAL_TABLES_UNREGISTERED":
            raise RuntimeError(
                "Tablas de artículos parciales sin registro de migración 003_group_articles.sql. "
                "Estado ambiguo. ABORTAR."
            )

        # Si 003 está OK (registrada+completa o tablas existen sin registro), saltamos 006
        skip_006 = state_003 in ("COMPLETED_OK", "TABLES_EXIST_UNREGISTERED")

        # Verificar 002_agenda_recurrence.sql (solo índice)
        registered_002 = _is_migration_registered(conn, "002_agenda_recurrence.sql")
        index_exists = False
        try:
            from app.db import _index_exists
            index_exists = _index_exists(conn, "events", "idx_events_series")
        except Exception:
            pass
        skip_007 = registered_002 or index_exists

        # Ejecutar migraciones nuevas 004-007 según necesidad
        new_migrations = [
            ("004_material_library.sql", True),
            ("005_material_groups.sql", True),
            ("006_group_articles_tables.sql", not skip_006),
            ("007_events_series_index.sql", not skip_007),
        ]

        for mig_name, should_execute in new_migrations:
            if not should_execute:
                continue
            mig_path = migrations_dir / "mysql" / mig_name
            if not mig_path.exists():
                raise RuntimeError(f"Migración no encontrada: {mig_path}")
            script = mig_path.read_text("utf-8")

            # Usar ejecución segura que verifica objetos antes de ejecutar
            action = _safe_execute_migration(conn, mig_name, script)
            if action == "EXECUTE":
                _execute_sql_script(conn, script, is_mysql=True)
                _register_migration(conn, mig_name)
            elif action == "SKIP_EXISTED":
                # Objetos existen sin registro, ya se registraron en _safe_execute_migration
                pass
            # SKIP: ya registrada y completa


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


def _save_private(settings: Settings, data: bytes, suffix: str, subfolder: Path | None = None) -> str:
    root = Path(settings.storage_root).resolve()
    if subfolder:
        # subfolder is a Path relative to storage_root
        target_dir = (root / subfolder).resolve()
        # Security check: ensure target_dir is within root
        if root not in target_dir.parents and root != target_dir:
            raise HTTPException(status_code=403, detail="Invalid folder path")
        target_dir.mkdir(parents=True, exist_ok=True)
        object_id = uuid.uuid4().hex
        target = target_dir / f"{object_id}{suffix}"
        target.write_bytes(data)
        # Return relative path from storage_root
        return str(target.relative_to(root))
    else:
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
    # Cliente de identidad M2M (osap-auth es la fuente única de identidad).
    app.state.identity_client = IdentityClient(
        cfg.auth_base_url,
        client_id=cfg.auth_m2m_client_id,
        client_secret=cfg.auth_m2m_client_secret,
        scope=cfg.auth_m2m_scope,
        audience=cfg.auth_m2m_audience,
        timeout_seconds=cfg.auth_timeout_seconds,
    )

    origins = list(cfg.cors_origins)
    if cfg.editor_origin and cfg.editor_origin not in origins:
        origins.append(cfg.editor_origin)
    if origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    def _identity_client_of() -> IdentityClient:
        """Cliente de identidad M2M de la aplicación (osap-auth).

        Se obtiene de ``app.state`` para que las pruebas puedan sustituirlo sin
        tocar la configuración global.
        """
        client = getattr(app.state, "identity_client", None)
        if client is None:
            raise IdentityUnavailable("El cliente de identidad no está disponible")
        return client

    def _resolve_member_identities(
        conn, user_subs: list[str]
    ) -> dict[str, PublicIdentity]:
        """Resuelve identidades en lote mediante el contrato M2M.

        Devuelve una entrada por cada identificador que Auth reconoce, con su
        nombre público (que puede ser ``None``). Un identificador ausente del
        resultado es una identidad que Auth **no reconoce**: no se inventa nombre.

        Si Auth no está disponible o incumple el contrato se responde 503 en
        lugar de degradar silenciosamente a "nadie está verificado".
        """
        targets = [uid for uid in dict.fromkeys(user_subs) if uid]
        if not targets:
            return {}
        try:
            return _identity_client_of().lookup(targets)
        except IdentityUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Identity service unavailable: {exc}",
            ) from exc

    def _verify_member_identity(user_sub: str) -> str | None:
        """Verifica al DESTINATARIO de un alta en osap-auth.

        Se aplica a todos los flujos que reciben un identificador de destinatario
        (alta de gestor y alta administrativa). Los flujos donde el propio
        usuario autenticado se incorpora usan la identidad ya validada por
        ``/auth/me`` y no pasan por aquí.

        Devuelve el nombre canónico de Auth, que puede ser ``None`` si Auth
        reconoce la identidad pero no expone nombre público.

        - Identidad no reconocida: ``400`` (no se inserta nada).
        - Auth no disponible o respuesta malformada: ``503`` (no se inserta nada).
        """
        try:
            identity = _identity_client_of().resolve_identity(user_sub)
        except IdentityUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Identity service unavailable: {exc}",
            ) from exc
        if identity is None:
            raise HTTPException(
                status_code=400,
                detail="Unknown user_id: osap-auth does not recognise this identity",
            )
        return identity.name

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

    def local_avatar(profile: dict[str, Any]) -> dict[str, Any]:
        user_id = profile.get("user_id")
        if user_id and profile.get("avatar_url"):
            profile["avatar_url"] = f"/api/v1/auth/users/{user_id}/avatar"
        return profile

    @app.get("/api/v1/auth/me")
    def me(authorization: str | None = Header(default=None)) -> Any:
        return local_avatar(profile_from_authorization(authorization))

    @app.patch("/api/v1/auth/me")
    def update_my_profile(
        body: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> Any:
        """Proxy to osap-auth for updating user's own profile (name, email, etc.)."""
        profile_from_authorization(authorization)
        token = authorization[7:].strip() if authorization else ""
        status_code, document = auth_call(
            "PATCH", "/auth/me", token=token, payload=body
        )
        if status_code != 200:
            detail = document.get("detail") if isinstance(document, dict) else None
            raise HTTPException(
                status_code=status_code if status_code < 500 else 502,
                detail=detail or "No se pudo actualizar el perfil",
            )
        return local_avatar(document) if isinstance(document, dict) else document

    @app.get("/api/v1/auth/users/{user_id}/avatar")
    def user_avatar(user_id: str) -> Response:
        try:
            cfg.validate_auth()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Identity service is not configured") from exc
        try:
            with httpx.Client(timeout=cfg.auth_timeout_seconds) as client:
                upstream = client.get(f"{cfg.auth_base_url}/auth/users/{user_id}/avatar")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Identity service unavailable") from exc
        if upstream.status_code != 200:
            raise HTTPException(status_code=404, detail="Avatar no encontrado")
        return Response(
            content=upstream.content,
            media_type=upstream.headers.get("content-type", "image/jpeg"),
            headers={"Cache-Control": "public, max-age=300"},
        )

    @app.patch("/api/v1/auth/me/avatar")
    def update_my_avatar(
        body: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> Any:
        profile_from_authorization(authorization)
        token = authorization[7:].strip() if authorization else ""
        status_code, document = auth_call(
            "PATCH", "/auth/me/avatar", token=token, payload=body
        )
        if status_code != 200:
            detail = document.get("detail") if isinstance(document, dict) else None
            raise HTTPException(
                status_code=status_code if status_code < 500 else 502,
                detail=detail or "No se pudo guardar la foto",
            )
        return local_avatar(document) if isinstance(document, dict) else document

    @app.delete("/api/v1/auth/me/avatar")
    def delete_my_avatar(authorization: str | None = Header(default=None)) -> Any:
        profile_from_authorization(authorization)
        token = authorization[7:].strip() if authorization else ""
        status_code, document = auth_call(
            "DELETE", "/auth/me/avatar", token=token
        )
        if status_code != 200:
            detail = document.get("detail") if isinstance(document, dict) else None
            raise HTTPException(
                status_code=status_code if status_code < 500 else 502,
                detail=detail or "No se pudo quitar la foto",
            )
        return local_avatar(document) if isinstance(document, dict) else document

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
            result = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 AS pos FROM collection_items "
                "WHERE collection_id = ?",
                (collection_id,),
            ).fetchone()
            position = list(result.values())[0] if result else 0
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

    @app.get("/api/v1/agenda")
    def get_agenda(
        request: Request, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
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
                    + " AND (NOT EXISTS (SELECT 1 FROM event_targets t WHERE t.event_id=e.id) "
                    + " OR EXISTS (SELECT 1 FROM event_targets t WHERE t.event_id=e.id AND ("
                    + "(t.target_type='user' AND t.target_value=?) OR "
                    + "(t.target_type='section' AND t.target_value IN (SELECT section_id FROM group_members WHERE user_sub=? AND status='active')))))"
                )
                params.extend(group_ids)
                params.extend([user_id, user_id])
            visibility.append("e.scope = 'personal' AND e.created_by = ?")
            params.append(user_id)
            visibility.append("e.created_by = ?")
            params.append(user_id)
            visibility.append(
                "e.scope IN ('section','users') AND EXISTS ("
                "SELECT 1 FROM event_targets t WHERE t.event_id = e.id AND ("
                "(t.target_type = 'user' AND t.target_value = ?) OR "
                "(t.target_type = 'section' AND t.target_value IN ("
                "SELECT section_id FROM group_members WHERE user_sub = ? "
                "AND status = 'active' AND section_id IS NOT NULL))))"
            )
            params.extend([user_id, user_id])
            events: list[sqlite3.Row] = []
            if visibility:
                events = conn.execute(
                    "SELECT e.*, g.name AS group_name, r.status AS my_rsvp, r.updated_at AS my_rsvp_updated_at, "
                    "(SELECT target_value FROM event_targets t WHERE t.event_id = e.id AND t.target_type = 'section' LIMIT 1) AS section_id "
                    "FROM events e LEFT JOIN groups g ON g.id = e.group_id "
                    "LEFT JOIN event_rsvps r ON r.event_id = e.id AND r.user_sub = ? "
                    "WHERE e.cancelled_at IS NULL AND ("
                    + " OR ".join(visibility) + ") "
                    "ORDER BY e.starts_at LIMIT 500",
                    (user_id, *params),
                ).fetchall()
        return {
            "groups": [
                _group_dto(
                    row,
                    row["role"],
                    admin or row["role"] == "manager",
                )
                for row in group_rows
            ],
            "entities": [],
            "can_create_group": True,
            "events": [
                _event_dto(
                    row,
                    my_rsvp=row["my_rsvp"],
                    my_rsvp_updated_at=row["my_rsvp_updated_at"],
                    group_name=row["group_name"],
                    can_manage=(
                        admin
                        or roles.get(row["group_id"]) == "manager"
                        or str(row["created_by"]) == user_id
                    ),
                )
                for row in events
            ],
        }

    @app.post("/api/v1/groups", status_code=201)
    def create_group(
        body: GroupBody, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Group name is required")
        now = utcnow()
        group_id = uuid.uuid4().hex
        entity_id = (body.entity_id or group_id).strip()
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
            # Serializar JSON
            language_json = json.dumps(body.language, ensure_ascii=False) if body.language else None
            repertoire_json = json.dumps(body.repertoire, ensure_ascii=False) if body.repertoire else None
            venues_json = json.dumps(body.venues, ensure_ascii=False) if body.venues else None

            # Paso 1: insertar con columnas básicas (compatibles con esquema original)
            conn.execute(
                "INSERT INTO groups "
                "(id,entity_id,name,timezone,created_by,join_code,created_at,updated_at,kind,slug,status,editorial_mode) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    group_id, entity_id, name, body.timezone.strip(),
                    user_id, join_code, now, now, body.kind.strip() or "grupo", group_id,
                    "active", "moderated",
                ),
            )

            # Paso 2: actualizar campos corales si hay datos
            coral_fields = []
            coral_values = []
            if body.foundation_date is not None:
                coral_fields.append("foundation_date=?")
                coral_values.append(body.foundation_date)
            if body.dissolution_date is not None:
                coral_fields.append("dissolution_date=?")
                coral_values.append(body.dissolution_date)
            if body.locality is not None:
                coral_fields.append("locality=?")
                coral_values.append(body.locality)
            if body.region is not None:
                coral_fields.append("region=?")
                coral_values.append(body.region)
            if body.country_code is not None:
                coral_fields.append("country_code=?")
                coral_values.append(body.country_code)
            if body.venue is not None:
                coral_fields.append("venue=?")
                coral_values.append(body.venue)
            if body.formation_type is not None:
                coral_fields.append("formation_type=?")
                coral_values.append(body.formation_type)
            if body.member_count is not None:
                coral_fields.append("member_count=?")
                coral_values.append(body.member_count)
            if body.public_email is not None:
                coral_fields.append("public_email=?")
                coral_values.append(body.public_email)
            if language_json is not None:
                coral_fields.append("language=?")
                coral_values.append(language_json)
            if repertoire_json is not None:
                coral_fields.append("repertoire=?")
                coral_values.append(repertoire_json)
            if venues_json is not None:
                coral_fields.append("venues=?")
                coral_values.append(venues_json)

            if coral_fields:
                coral_values.append(group_id)
                conn.execute(
                    f"UPDATE groups SET {', '.join(coral_fields)} WHERE id = ?",
                    tuple(coral_values),
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
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            member = conn.execute(
                "SELECT 1 FROM group_members WHERE group_id=? AND user_sub=? "
                "AND status='active'", (group_id, user_id)
            ).fetchone()
            if member is None and not _is_admin(profile):
                raise HTTPException(status_code=403, detail="Active member required")
            # Fetch sections
            section_rows = conn.execute(
                "SELECT * FROM group_sections WHERE group_id=? AND active=1 "
                "ORDER BY scope, sort_order, name", (group_id,)
            ).fetchall()
            # Fetch roles from group_roles
            admin_roles = conn.execute(
                "SELECT * FROM group_roles WHERE group_id=? AND scope='admin' AND active=1 "
                "ORDER BY sort_order, name", (group_id,)
            ).fetchall()
            musical_roles = conn.execute(
                "SELECT * FROM group_roles WHERE group_id=? AND scope='musical' AND active=1 "
                "ORDER BY sort_order, name", (group_id,)
            ).fetchall()
        result: dict[str, list[dict[str, Any]]] = {"admin": [], "musical": [], "section": []}
        for row in section_rows:
            scope = str(row["scope"] or "section")
            result.setdefault(scope, []).append({
                "id": row["id"], "code": row["code"], "name": row["name"],
                "parent_id": row["parent_id"], "sort_order": row["sort_order"],
            })
        for row in admin_roles:
            result["admin"].append({
                "id": row["id"], "code": row["code"], "name": row["name"],
                "parent_id": row["parent_id"], "sort_order": row["sort_order"],
            })
        for row in musical_roles:
            result["musical"].append({
                "id": row["id"], "code": row["code"], "name": row["name"],
                "parent_id": row["parent_id"], "sort_order": row["sort_order"],
            })
        return result

    @app.patch("/api/v1/groups/{group_id}/members/@me")
    def update_own_membership(
        group_id: str,
        body: MemberSelfUpdateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Allow a user to update their own membership profile (voice, section, notifications)."""
        user_id = str(profile["user_id"])
        now = utcnow()
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT * FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if member is None:
                raise HTTPException(status_code=403, detail="Not an active member of this group")
            # Validate section_id if provided
            if body.section_id is not None:
                section = conn.execute(
                    "SELECT 1 FROM group_sections WHERE id = ? AND group_id = ? AND active = 1",
                    (body.section_id, group_id),
                ).fetchone()
                if section is None:
                    raise HTTPException(status_code=400, detail="Section not found in this group")
            updates = []
            values: list[Any] = []
            for column in ("voice_code", "voice_label", "section_id", "notify_email", "notify_osap", "notify_whatsapp", "notify_sms"):
                value = getattr(body, column)
                if value is not None:
                    updates.append(f"{column}=?")
                    values.append(value)
            if not updates:
                return {"ok": True, "message": "No changes"}
            values.append(now)
            values.extend([group_id, user_id])
            conn.execute(
                f"UPDATE group_members SET {', '.join(updates)}, updated_at=? WHERE group_id=? AND user_sub=?",
                tuple(values),
            )
            # Activity log
            conn.execute(
                "INSERT INTO activity_log (legacy_id, group_id, event_type, actor, from_status, to_status, detail_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (_activity_legacy_id("mem", user_id), group_id, "member_self_update", user_id, None, None, None, now),
            )
            updated = conn.execute(
                "SELECT * FROM group_members WHERE group_id = ? AND user_sub = ?", (group_id, user_id)
            ).fetchone()
        return dict(updated)

    @app.patch("/api/v1/groups/{group_id}/members/{user_sub}")
    def update_group_member(
        group_id: str,
        user_sub: str,
        body: MemberUpdateBody,
        request: Request,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        now = utcnow()
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            actor = conn.execute(
                "SELECT role FROM group_members WHERE group_id=? AND user_sub=? "
                "AND status='active'", (group_id, user_id)
            ).fetchone()
            if not _is_admin(profile) and (actor is None or actor["role"] != MANAGER_ROLE):
                raise HTTPException(status_code=403, detail="Only group managers can edit")
            target = conn.execute(
                "SELECT * FROM group_members WHERE group_id=? AND user_sub=?",
                (group_id, user_sub),
            ).fetchone()
            if target is None:
                raise HTTPException(status_code=404, detail="Member not found")
            # Conceder o retirar la responsabilidad de gestor corresponde sólo
            # a un gestor del grupo: un administrador global no puede hacerlo.
            if body.role is not None and body.role != target["role"]:
                if not _may_grant_manager(conn, group_id, user_id, profile):
                    raise HTTPException(
                        status_code=403,
                        detail="Only a group manager can change manager permissions",
                    )
            if body.status == "removed" and target["role"] == MANAGER_ROLE:
                managers = conn.execute(
                    "SELECT COUNT(*) AS n FROM group_members WHERE group_id=? "
                    "AND role='manager' AND status='active'", (group_id,)
                ).fetchone()["n"]
                if int(managers) <= 1:
                    raise HTTPException(status_code=400, detail="The group needs a manager")
            # Los catálogos (cargo, rol musical, sección) deben ser de este grupo
            _validate_group_catalog_refs(
                conn, group_id,
                admin_role_id=body.admin_role_id,
                musical_role_id=body.musical_role_id,
                section_id=body.section_id,
            )
            # Capture before values for activity log
            before_role = target["role"]
            before_admin_role = target["admin_role_id"]
            before_musical_role = target["musical_role_id"]
            before_section = target["section_id"]
            before_status = target["status"]
            updates = []
            values: list[Any] = []
            for column in ("role", "admin_role_id", "musical_role_id", "section_id", "status"):
                value = getattr(body, column)
                if value is not None:
                    updates.append(f"{column}=?")
                    values.append(value)
            if not updates:
                return {"ok": True}
            values.append(now)
            values.extend([group_id, user_sub])
            conn.execute(
                f"UPDATE group_members SET {', '.join(updates)}, updated_at=? "
                "WHERE group_id=? AND user_sub=?",
                tuple(values),
            )
            # Activity log for significant changes
            detail = {}
            if body.role is not None and body.role != before_role:
                detail["role"] = {"from": before_role, "to": body.role}
            if body.admin_role_id != before_admin_role:
                detail["admin_role"] = {"from": before_admin_role, "to": body.admin_role_id}
            if body.musical_role_id != before_musical_role:
                detail["musical_role"] = {"from": before_musical_role, "to": body.musical_role_id}
            if body.section_id != before_section:
                detail["section"] = {"from": before_section, "to": body.section_id}
            if body.status is not None and body.status != before_status:
                detail["status"] = {"from": before_status, "to": body.status}
            if detail:
                conn.execute(
                    "INSERT INTO activity_log (legacy_id, group_id, event_type, actor, from_status, to_status, detail_json, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (_activity_legacy_id("mem", user_sub), group_id, "member_role_change", user_id, before_role, body.role or before_role, json.dumps(detail) if detail else None, now),
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

            # Serializar JSON
            language_json = json.dumps(body.language, ensure_ascii=False) if body.language else None
            repertoire_json = json.dumps(body.repertoire, ensure_ascii=False) if body.repertoire else None
            venues_json = json.dumps(body.venues, ensure_ascii=False) if body.venues else None

            conn.execute(
                "UPDATE groups SET "
                "name = ?, timezone = ?, updated_at = ?, "
                "foundation_date = ?, dissolution_date = ?, locality = ?, region = ?, "
                "country_code = ?, venue = ?, formation_type = ?, member_count = ?, "
                "public_email = ?, language = ?, repertoire = ?, venues = ? "
                "WHERE id = ?",
                (
                    name, timezone, utcnow(),
                    body.foundation_date, body.dissolution_date, body.locality, body.region,
                    body.country_code, body.venue, body.formation_type, body.member_count,
                    body.public_email, language_json, repertoire_json, venues_json,
                    group_id,
                ),
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
            # Resolve role details
            role_ids = set()
            for row in rows:
                if row["admin_role_id"]:
                    role_ids.add(row["admin_role_id"])
                if row["musical_role_id"]:
                    role_ids.add(row["musical_role_id"])
            role_map = {}
            if role_ids:
                placeholders = ",".join("?" * len(role_ids))
                role_rows = conn.execute(
                    f"SELECT id, code, name FROM group_roles WHERE id IN ({placeholders})",
                    tuple(role_ids),
                ).fetchall()
                role_map = {r["id"]: {"code": r["code"], "name": r["name"]} for r in role_rows}
            # Nombres públicos resueltos en UNA consulta agrupada a osap-auth.
            identities = _resolve_member_identities(
                conn, [row["user_sub"] for row in rows]
            )
        return [
            {
                "user_sub": row["user_sub"],
                "role": row["role"],
                # Nombre canónico de Auth; None si Auth no lo resuelve o si el
                # contrato no expone nombre público para esa identidad.
                "name": (
                    identities[row["user_sub"]].name
                    if row["user_sub"] in identities
                    else None
                ),
                "identity_verified": row["user_sub"] in identities,
                "voice_label": row["voice_label"],
                "section": row["section"],
                "admin_role_id": row["admin_role_id"],
                "admin_role": role_map.get(row["admin_role_id"]) if row["admin_role_id"] else None,
                "musical_role_id": row["musical_role_id"],
                "musical_role": role_map.get(row["musical_role_id"]) if row["musical_role_id"] else None,
                "section_id": row["section_id"],
            }
            for row in rows
        ]

    @app.get("/api/v1/admin/groups/{group_id}/members")
    def admin_list_group_members(
        group_id: str,
        status: str | None = None,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        """Membresías del grupo para mantenimiento, incluidos los estados.

        A diferencia del listado ordinario (que sólo devuelve miembros activos),
        esta vista administrativa incluye altas, bajas y estados de pertenencia,
        con los identificadores de catálogo guardados en cada membresía.

        Los nombres se resuelven en lote mediante el contrato M2M de osap-auth.
        ``display_name`` se expone como ``legacy_display_name`` y queda marcado
        como no verificado: es una instantánea histórica, no identidad.
        """
        if not _is_admin(profile):
            raise HTTPException(status_code=403, detail="Admin role required")
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if status:
                rows = conn.execute(
                    "SELECT user_sub, role, status, display_name, admin_role_id, "
                    "       musical_role_id, section_id, granted_by, joined_at, updated_at "
                    "FROM group_members WHERE group_id = ? AND status = ? "
                    "ORDER BY status, role DESC, user_sub",
                    (group_id, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT user_sub, role, status, display_name, admin_role_id, "
                    "       musical_role_id, section_id, granted_by, joined_at, updated_at "
                    "FROM group_members WHERE group_id = ? "
                    "ORDER BY status, role DESC, user_sub",
                    (group_id,),
                ).fetchall()
            identities = _resolve_member_identities(
                conn, [row["user_sub"] for row in rows]
            )
        result = []
        for row in rows:
            identity = identities.get(row["user_sub"])
            item = dict(row)
            item["name"] = identity.name if identity is not None else None
            item["identity_verified"] = identity is not None
            item["legacy_display_name"] = row["display_name"]
            del item["display_name"]
            result.append(item)
        return result

    @app.post("/api/v1/groups/{group_id}/members", status_code=201)
    def add_group_member(
        group_id: str,
        body: MemberCreateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Manager adds/invites a member directly to the group.

        La identidad del destinatario se verifica en osap-auth antes de crear la
        pertenencia: un ``user_sub`` que Auth no reconoce se rechaza y no
        genera ninguna fila. El ``display_name`` que envíe el cliente no es
        prueba de identidad; sólo se usa el nombre canónico devuelto por Auth.
        """
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        now = utcnow()
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != MANAGER_ROLE):
                raise HTTPException(status_code=403, detail="Only group managers can add members")
            # Sólo un gestor del grupo puede dar de alta con rol de gestor. Un
            # administrador global puede incorporar miembros ordinarios, pero
            # nunca conceder permisos de gestión.
            if body.role == MANAGER_ROLE and not _may_grant_manager(conn, group_id, user_id, profile):
                raise HTTPException(
                    status_code=403,
                    detail="Only a group manager can grant manager permissions",
                )
            # Check if user is already a member
            existing = conn.execute(
                "SELECT * FROM group_members WHERE group_id = ? AND user_sub = ?",
                (group_id, body.user_sub),
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="User is already a member of this group")
            # Los catálogos deben pertenecer a este grupo
            _validate_group_catalog_refs(
                conn, group_id,
                admin_role_id=body.admin_role_id,
                musical_role_id=body.musical_role_id,
                section_id=body.section_id,
            )
            # Verificar la identidad del DESTINATARIO en osap-auth antes de
            # cualquier escritura en group_members o activity_log.
            canonical_name = _verify_member_identity(body.user_sub)
            # Create member
            member_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO group_members "
                "(id, group_id, user_sub, role, status, display_name, admin_role_id, musical_role_id, section_id, granted_by, joined_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    member_id, group_id, body.user_sub, body.role, "active",
                    canonical_name, body.admin_role_id, body.musical_role_id,
                    body.section_id, user_id, now, now,
                ),
            )
            # Activity log
            conn.execute(
                "INSERT INTO activity_log (legacy_id, group_id, event_type, actor, from_status, to_status, detail_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (_activity_legacy_id("mem", body.user_sub), group_id, "member_added", user_id, None, "active",
                 json.dumps({
                     "role": body.role,
                     "identity_verified_by": "osap-auth",
                     "admin_role_id": body.admin_role_id,
                     "musical_role_id": body.musical_role_id,
                     "section_id": body.section_id,
                 }), now),
            )
            new_member = conn.execute(
                "SELECT * FROM group_members WHERE id = ?", (member_id,)
            ).fetchone()
        return dict(new_member)

    # ===== group_roles CRUD =====
    @app.get("/api/v1/groups/{group_id}/roles")
    def list_group_roles(
        group_id: str,
        scope: Literal["admin", "musical"] | None = None,
        active: bool | None = None,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and member is None:
                raise HTTPException(status_code=403, detail="Not a member of this group")
            where = ["group_id = ?"]
            params: list[Any] = [group_id]
            if scope is not None:
                where.append("scope = ?")
                params.append(scope)
            if active is not None:
                where.append("active = ?")
                params.append(1 if active else 0)
            rows = conn.execute(
                f"SELECT * FROM group_roles WHERE {' AND '.join(where)} ORDER BY scope, sort_order, name",
                tuple(params),
            ).fetchall()
        return [_group_role_dto(row) for row in rows]

    @app.get("/api/v1/groups/{group_id}/roles/{role_id}")
    def get_group_role(
        group_id: str,
        role_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and member is None:
                raise HTTPException(status_code=403, detail="Not a member of this group")
            row = conn.execute(
                "SELECT * FROM group_roles WHERE id = ? AND group_id = ?",
                (role_id, group_id),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Role not found")
        return _group_role_dto(row)

    @app.post("/api/v1/groups/{group_id}/roles", status_code=201)
    def create_group_role(
        group_id: str,
        body: GroupRoleBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can create roles")
            if body.parent_id:
                parent = conn.execute(
                    "SELECT 1 FROM group_roles WHERE id = ? AND group_id = ?",
                    (body.parent_id, group_id),
                ).fetchone()
                if parent is None:
                    raise HTTPException(status_code=400, detail="Parent role not found in this group")
            now = utcnow()
            role_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO group_roles "
                "(id, legacy_id, group_id, scope, code, name, parent_id, sort_order, active, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    role_id, f"new-{role_id}", group_id, body.scope, body.code.strip(), body.name.strip(),
                    body.parent_id, body.sort_order, 1 if body.active else 0, now, now,
                ),
            )
            row = conn.execute("SELECT * FROM group_roles WHERE id = ?", (role_id,)).fetchone()
        return _group_role_dto(row)

    @app.patch("/api/v1/groups/{group_id}/roles/{role_id}")
    def update_group_role(
        group_id: str,
        role_id: str,
        body: GroupRoleUpdateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can update roles")
            role = conn.execute(
                "SELECT * FROM group_roles WHERE id = ? AND group_id = ?",
                (role_id, group_id),
            ).fetchone()
            if role is None:
                raise HTTPException(status_code=404, detail="Role not found")
            if body.parent_id:
                if body.parent_id == role_id:
                    raise HTTPException(status_code=400, detail="Role cannot be its own parent")
                parent = conn.execute(
                    "SELECT 1 FROM group_roles WHERE id = ? AND group_id = ?",
                    (body.parent_id, group_id),
                ).fetchone()
                if parent is None:
                    raise HTTPException(status_code=400, detail="Parent role not found in this group")
            updates = []
            values: list[Any] = []
            for column in ("scope", "code", "name", "parent_id", "sort_order", "active"):
                value = getattr(body, column)
                if value is not None:
                    updates.append(f"{column}=?")
                    values.append(value)
            if not updates:
                return _group_role_dto(role)
            values.append(utcnow())
            values.append(role_id)
            conn.execute(
                f"UPDATE group_roles SET {', '.join(updates)}, updated_at=? WHERE id=?",
                tuple(values),
            )
            row = conn.execute("SELECT * FROM group_roles WHERE id = ?", (role_id,)).fetchone()
        return _group_role_dto(row)

    @app.delete("/api/v1/groups/{group_id}/roles/{role_id}")
    def delete_group_role(
        group_id: str,
        role_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can delete roles")
            role = conn.execute(
                "SELECT * FROM group_roles WHERE id = ? AND group_id = ?",
                (role_id, group_id),
            ).fetchone()
            if role is None:
                raise HTTPException(status_code=404, detail="Role not found")
            # Check if role is referenced by any member
            refs = conn.execute(
                "SELECT 1 FROM group_members WHERE group_id = ? AND (admin_role_id = ? OR musical_role_id = ?)",
                (group_id, role_id, role_id),
            ).fetchone()
            if refs:
                raise HTTPException(status_code=400, detail="Role is assigned to members")
            # Check for children
            children = conn.execute(
                "SELECT 1 FROM group_roles WHERE parent_id = ?", (role_id,)
            ).fetchone()
            if children:
                raise HTTPException(status_code=400, detail="Role has child roles")
            conn.execute("DELETE FROM group_roles WHERE id = ?", (role_id,))
        return {"ok": True}

    # ===== group_social_links CRUD =====
    @app.get("/api/v1/groups/{group_id}/social-links")
    def list_group_social_links(
        group_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and member is None:
                raise HTTPException(status_code=403, detail="Not a member of this group")
            rows = conn.execute(
                "SELECT * FROM group_social_links WHERE group_id = ? ORDER BY position, id",
                (group_id,),
            ).fetchall()
        return [_social_link_dto(row) for row in rows]

    @app.get("/api/v1/groups/{group_id}/social-links/{link_id}")
    def get_group_social_link(
        group_id: str,
        link_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and member is None:
                raise HTTPException(status_code=403, detail="Not a member of this group")
            row = conn.execute(
                "SELECT * FROM group_social_links WHERE id = ? AND group_id = ?",
                (link_id, group_id),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Social link not found")
        return _social_link_dto(row)

    @app.post("/api/v1/groups/{group_id}/social-links", status_code=201)
    def create_group_social_link(
        group_id: str,
        body: SocialLinkBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can add social links")
            now = utcnow()
            link_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO group_social_links "
                "(id, legacy_id, group_id, kind, label, url, position, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    link_id, f"new-{link_id}", group_id, body.kind, body.label, body.url.strip(),
                    body.position, now,
                ),
            )
            row = conn.execute("SELECT * FROM group_social_links WHERE id = ?", (link_id,)).fetchone()
        return _social_link_dto(row)

    @app.patch("/api/v1/groups/{group_id}/social-links/{link_id}")
    def update_group_social_link(
        group_id: str,
        link_id: str,
        body: SocialLinkUpdateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can update social links")
            link = conn.execute(
                "SELECT * FROM group_social_links WHERE id = ? AND group_id = ?",
                (link_id, group_id),
            ).fetchone()
            if link is None:
                raise HTTPException(status_code=404, detail="Social link not found")
            updates = []
            values: list[Any] = []
            for column in ("kind", "label", "url", "position"):
                value = getattr(body, column)
                if value is not None:
                    updates.append(f"{column}=?")
                    values.append(value)
            if not updates:
                return _social_link_dto(link)
            values.append(link_id)
            conn.execute(
                f"UPDATE group_social_links SET {', '.join(updates)} WHERE id=?",
                tuple(values),
            )
            row = conn.execute("SELECT * FROM group_social_links WHERE id = ?", (link_id,)).fetchone()
        return _social_link_dto(row)

    @app.delete("/api/v1/groups/{group_id}/social-links/{link_id}")
    def delete_group_social_link(
        group_id: str,
        link_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can delete social links")
            link = conn.execute(
                "SELECT 1 FROM group_social_links WHERE id = ? AND group_id = ?",
                (link_id, group_id),
            ).fetchone()
            if link is None:
                raise HTTPException(status_code=404, detail="Social link not found")
            conn.execute("DELETE FROM group_social_links WHERE id = ?", (link_id,))
        return {"ok": True}

    # ===== legacy_uploads (read-only) =====
    @app.get("/api/v1/groups/{group_id}/legacy-uploads")
    def list_legacy_uploads(
        group_id: str,
        mime_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can view legacy uploads")
            where = ["group_id = ?"]
            params: list[Any] = [group_id]
            if mime_type:
                where.append("mime_type = ?")
                params.append(mime_type)
            rows = conn.execute(
                f"SELECT * FROM legacy_uploads WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            ).fetchall()
        return [_legacy_upload_dto(row) for row in rows]

    @app.get("/api/v1/legacy-uploads/{upload_id}")
    def get_legacy_upload(
        upload_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            row = conn.execute("SELECT * FROM legacy_uploads WHERE id = ?", (upload_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Legacy upload not found")
            if row["group_id"]:
                member = conn.execute(
                    "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                    (row["group_id"], user_id),
                ).fetchone()
                if not admin and (member is None or member["role"] != "manager"):
                    raise HTTPException(status_code=403, detail="Not authorized")
        return _legacy_upload_dto(row)

    # ===== activity_log (read-only) =====
    @app.get("/api/v1/groups/{group_id}/activity-log")
    def list_group_activity_log(
        group_id: str,
        event_type: str | None = None,
        actor: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        article_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
                (group_id, user_id),
            ).fetchone()
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can view activity log")
            where = ["group_id = ?"]
            params: list[Any] = [group_id]
            if event_type:
                where.append("event_type = ?")
                params.append(event_type)
            if actor:
                where.append("actor = ?")
                params.append(actor)
            if date_from:
                where.append("created_at >= ?")
                params.append(date_from)
            if date_to:
                where.append("created_at <= ?")
                params.append(date_to)
            if article_id:
                where.append("article_id = ?")
                params.append(article_id)
            rows = conn.execute(
                f"SELECT * FROM activity_log WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            ).fetchall()
        return [_activity_log_dto(row) for row in rows]

    @app.get("/api/v1/admin/activity-log")
    def list_admin_activity_log(
        event_type: str | None = None,
        actor: str | None = None,
        group_id: str | None = None,
        article_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
        offset: int = 0,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        admin = _is_admin(profile)
        if not admin:
            raise HTTPException(status_code=403, detail="Admin only")
        with _connect(cfg) as conn:
            where = []
            params: list[Any] = []
            if event_type:
                where.append("event_type = ?")
                params.append(event_type)
            if actor:
                where.append("actor = ?")
                params.append(actor)
            if group_id:
                where.append("group_id = ?")
                params.append(group_id)
            if article_id:
                where.append("article_id = ?")
                params.append(article_id)
            if date_from:
                where.append("created_at >= ?")
                params.append(date_from)
            if date_to:
                where.append("created_at <= ?")
                params.append(date_to)
            where_clause = f"WHERE {' AND '.join(where)}" if where else ""
            rows = conn.execute(
                f"SELECT * FROM activity_log {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            ).fetchall()
        return [_activity_log_dto(row) for row in rows]

    # ===== performances (actuaciones) =====
    # Etapa 1 de la clasificacion de `performances` (plan AutoFree): lectura publica
    # de las actuaciones con `editorial_status = 'published'` y participacion de grupos.
    # La escritura editorial (POST/PATCH/DELETE desde admin) queda para la etapa 2.

    def _active_group_member(conn: Any, group_id: str, user_id: str) -> Any:
        return conn.execute(
            "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
            (group_id, user_id),
        ).fetchone()

    @app.get("/api/v1/performances")
    def list_performances(
        group_id: str | None = None,
        kind: str | None = None,
        modality: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        """Actuaciones visibles para el usuario.

        Publicadas para todo usuario autenticado; los borradores solo para admin o
        para miembros activos de alguno de los grupos participantes. `group_id`
        restringe el resultado a la participacion de ese grupo (403 si no es miembro).
        """
        if limit < 1 or limit > 200 or offset < 0:
            raise HTTPException(status_code=422, detail="limit debe estar entre 1 y 200")
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        clauses = ["1=1"]
        params: list[Any] = []
        if kind:
            clauses.append("p.kind = ?")
            params.append(kind)
        if modality:
            clauses.append("p.modality = ?")
            params.append(modality)
        if date_from:
            clauses.append("p.starts_on >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("p.starts_on <= ?")
            params.append(date_to)
        if q:
            clauses.append("(p.title LIKE ? OR p.summary LIKE ?)")
            params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
        if group_id is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM performance_groups pg WHERE pg.performance_id = p.id "
                "AND pg.group_id = ?)"
            )
            params.append(group_id)
            if not admin:
                with _connect(cfg) as conn:
                    group = conn.execute(
                        "SELECT 1 FROM groups WHERE id = ?", (group_id,)
                    ).fetchone()
                    if group is None:
                        raise HTTPException(status_code=404, detail="Group not found")
                    member = conn.execute(
                        "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? "
                        "AND status = 'active'",
                        (group_id, user_id),
                    ).fetchone()
                if member is None:
                    raise HTTPException(status_code=403, detail="Not a member of this group")
        if not admin:
            clauses.append(
                "(p.editorial_status = 'published' OR EXISTS ("
                "SELECT 1 FROM performance_groups pg "
                "JOIN group_members gm ON gm.group_id = pg.group_id "
                "WHERE pg.performance_id = p.id AND gm.user_sub = ? AND gm.status = 'active'"
                "))"
            )
            params.append(user_id)
        where_clause = " AND ".join(clauses)
        with _connect(cfg) as conn:
            rows = conn.execute(
                f"SELECT p.* FROM performances p WHERE {where_clause} "
                "ORDER BY p.starts_on DESC, p.starts_at DESC LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            ).fetchall()
            return [
                _performance_dto(row, _performance_groups_dto(conn, row["id"])) for row in rows
            ]

    @app.get("/api/v1/performances/{performance_id}")
    def get_performance(
        performance_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT * FROM performances WHERE id = ?", (performance_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Performance not found")
            groups = _performance_groups_dto(conn, row["id"])
            if row["editorial_status"] != "published" and not admin:
                allowed = False
                for item in groups:
                    member = _active_group_member(conn, item["group_id"], user_id)
                    if member is not None:
                        allowed = True
                        break
                if not allowed:
                    raise HTTPException(status_code=404, detail="Performance not found")
        return _performance_dto(row, groups)

    @app.get("/api/v1/groups/{group_id}/performances")
    def list_group_performances(
        group_id: str,
        include_drafts: bool = False,
        limit: int = 50,
        offset: int = 0,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        if limit < 1 or limit > 200 or offset < 0:
            raise HTTPException(status_code=422, detail="limit debe estar entre 1 y 200")
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = _active_group_member(conn, group_id, user_id)
            if not admin and member is None:
                raise HTTPException(status_code=403, detail="Not a member of this group")
            manager = admin or (member is not None and member["role"] == "manager")
            show_drafts = include_drafts and manager
            clauses = ["pg.group_id = ?"]
            params: list[Any] = [group_id]
            if not show_drafts:
                clauses.append("p.editorial_status = 'published'")
            rows = conn.execute(
                "SELECT p.* FROM performances p "
                "JOIN performance_groups pg ON pg.performance_id = p.id "
                f"WHERE {' AND '.join(clauses)} "
                "ORDER BY p.starts_on DESC, p.starts_at DESC LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            ).fetchall()
            result = [
                _performance_dto(row, _performance_groups_dto(conn, row["id"])) for row in rows
            ]
        return result

    @app.get("/api/v1/groups/{group_id}/performances/candidates")
    def list_group_performance_candidates(
        group_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> list[dict[str, Any]]:
        """Actuaciones no vinculadas disponibles para que el gestor las asocie al grupo."""
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = _active_group_member(conn, group_id, user_id)
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can link performances")
            rows = conn.execute(
                "SELECT * FROM performances p WHERE NOT EXISTS ("
                "SELECT 1 FROM performance_groups pg WHERE pg.performance_id = p.id AND pg.group_id = ?"
                ") ORDER BY starts_on DESC, starts_at DESC LIMIT 200",
                (group_id,),
            ).fetchall()
        return [_performance_dto(row) for row in rows]

    @app.post("/api/v1/groups/{group_id}/performances/{performance_id}", status_code=201)
    def link_group_performance(
        group_id: str,
        performance_id: str,
        body: PerformanceGroupBody | None = None,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        if body is not None and body.group_id is not None and body.group_id != group_id:
            raise HTTPException(status_code=400, detail="group_id del cuerpo no coincide con la ruta")
        role = body.role if body is not None else "participant"
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = _active_group_member(conn, group_id, user_id)
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can link performances")
            performance = conn.execute(
                "SELECT 1 FROM performances WHERE id = ?", (performance_id,)
            ).fetchone()
            if performance is None:
                raise HTTPException(status_code=404, detail="Performance not found")
            exists = conn.execute(
                "SELECT 1 FROM performance_groups WHERE performance_id = ? AND group_id = ?",
                (performance_id, group_id),
            ).fetchone()
            if exists is not None:
                raise HTTPException(status_code=409, detail="Performance already linked to this group")
            conn.execute(
                "INSERT INTO performance_groups (performance_id, group_id, role) VALUES (?,?,?)",
                (performance_id, group_id, role),
            )
            groups = _performance_groups_dto(conn, performance_id)
        return {"performance_id": performance_id, "group_id": group_id, "role": role, "groups": groups}



    @app.delete("/api/v1/groups/{group_id}/performances/{performance_id}")
    def unlink_group_performance(
        group_id: str,
        performance_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            member = _active_group_member(conn, group_id, user_id)
            if not admin and (member is None or member["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can unlink performances")
            cursor = conn.execute(
                "DELETE FROM performance_groups WHERE performance_id = ? AND group_id = ?",
                (performance_id, group_id),
            )
            if getattr(cursor, "rowcount", 0) == 0:
                raise HTTPException(status_code=404, detail="Participation not found")
        return {"ok": True}

    @app.get("/api/v1/messages/unread-count")
    def unread_messages(profile: dict[str, Any] = Depends(current_profile)) -> dict[str, int]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM message_recipients r "
                "JOIN messages m ON m.id=r.message_id "
                "WHERE r.user_sub = ? AND r.read_at IS NULL AND m.sender_sub <> ?",
                (user_id, user_id),
            ).fetchone()
        return {"count": int(row["n"])}

    @app.get("/api/v1/messages/inbox")
    def messages_inbox(profile: dict[str, Any] = Depends(current_profile)) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            rows = conn.execute(
                "SELECT m.*, g.name AS group_name, gm.display_name AS sender_name, "
                "(SELECT read_at FROM message_recipients r "
                " WHERE r.message_id = m.id AND r.user_sub = ?) AS my_read_at, "
                "(SELECT COUNT(*) FROM message_recipients r "
                " WHERE r.message_id = m.id) AS recipient_count, "
                "(SELECT group_concat(r.user_sub) FROM message_recipients r "
                " WHERE r.message_id = m.id) AS recipient_subs "
                "FROM messages m JOIN groups g ON g.id = m.group_id "
                "LEFT JOIN group_members gm ON gm.group_id = m.group_id "
                "AND gm.user_sub = m.sender_sub "
                "WHERE m.sender_sub = ? OR EXISTS (SELECT 1 FROM message_recipients r "
                "WHERE r.message_id = m.id AND r.user_sub = ?) "
                "ORDER BY m.created_at DESC LIMIT 100",
                (user_id, user_id, user_id),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "group_id": row["group_id"],
                "group_name": row["group_name"],
                "sender_sub": row["sender_sub"],
                "sender_name": row["sender_name"] or row["sender_sub"][:8],
                "scope": row["scope"],
                "subject": row["subject"],
                "body": row["body"],
                "created_at": row["created_at"],
                "my_read_at": row["my_read_at"],
                "recipient_count": row["recipient_count"],
                "recipient_subs": [
                    sub for sub in str(row["recipient_subs"] or "").split(",") if sub
                ],
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
                "SELECT m.*, g.name AS group_name, gm.display_name AS sender_name, "
                "(SELECT read_at FROM message_recipients r WHERE r.message_id=m.id "
                "AND r.user_sub=?) AS my_read_at, "
                "(SELECT COUNT(*) FROM message_recipients r "
                " WHERE r.message_id = m.id) AS recipient_count, "
                "(SELECT group_concat(r.user_sub) FROM message_recipients r "
                " WHERE r.message_id = m.id) AS recipient_subs "
                "FROM messages m "
                "JOIN groups g ON g.id=m.group_id "
                "LEFT JOIN group_members gm ON gm.group_id = m.group_id "
                "AND gm.user_sub = m.sender_sub "
                "WHERE m.id=?",
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
            "sender_sub": row["sender_sub"], "sender_name": row["sender_name"] or row["sender_sub"][:8],
            "scope": row["scope"],
            "subject": row["subject"], "body": row["body"], "created_at": row["created_at"],
            "my_read_at": row["my_read_at"], "is_sender": row["sender_sub"] == user_id,
            "recipient_count": row["recipient_count"],
            "recipient_subs": [
                sub for sub in str(row["recipient_subs"] or "").split(",") if sub
            ],
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
            recipients = {str(original["sender_sub"])}
            if body.all:
                for recipient_row in conn.execute(
                    "SELECT user_sub FROM message_recipients WHERE message_id=?",
                    (message_id,),
                ).fetchall():
                    recipients.add(str(recipient_row["user_sub"]))
            recipients.discard(user_id)
            new_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO messages (id,group_id,sender_sub,scope,subject,body,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (new_id, original["group_id"], user_id, "users",
                 f"Re: {original['subject']}", text, now),
            )
            for recipient in sorted(recipients):
                conn.execute(
                    "INSERT OR IGNORE INTO message_recipients (message_id,user_sub,read_at) "
                    "VALUES (?,?,NULL)",
                    (new_id, recipient),
                )
        return {
            "id": new_id,
            "group_id": original["group_id"],
            "recipient_count": len(recipients),
            "status": "sent",
        }

    @app.get("/api/v1/groups/directory")
    def groups_directory(
        profile: dict[str, Any] = Depends(current_profile)
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            rows = conn.execute(
                "SELECT g.id, g.name, g.kind, "
                "EXISTS(SELECT 1 FROM group_members gm WHERE gm.group_id=g.id "
                "AND gm.user_sub=? AND gm.status='active') AS joined "
                "FROM groups g WHERE g.status='active' ORDER BY g.name",
                (user_id,),
            ).fetchall()
        return [
            {"id": row["id"], "name": row["name"], "kind": row["kind"],
             "joined": bool(row["joined"])}
            for row in rows
        ]
    # ===== Mantenimiento administrativo de grupos y miembros =====
    @app.get("/api/v1/admin/groups")
    def admin_list_groups(
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        """Lista los grupos de Chorus con su estado de pertenencia.

        Los grupos son exclusivamente de Chorus: la identidad de los usuarios
        sigue procediendo de osap-auth, pero la pertenencia es dato de Chorus.
        """
        if not _is_admin(profile):
            raise HTTPException(status_code=403, detail="Admin role required")
        with _connect(cfg) as conn:
            rows = conn.execute(
                "SELECT g.id, g.name, g.kind, g.type_code, g.status, g.created_at, "
                "       (SELECT COUNT(*) FROM group_members gm "
                "         WHERE gm.group_id = g.id AND gm.status = 'active') AS member_count, "
                "       (SELECT COUNT(*) FROM group_members gm "
                "         WHERE gm.group_id = g.id AND gm.role = 'manager' "
                "           AND gm.status = 'active') AS manager_count, "
                "       (SELECT COUNT(*) FROM group_sections gs "
                "         WHERE gs.group_id = g.id AND gs.active = 1) AS section_count, "
                "       (SELECT COUNT(*) FROM group_roles gr "
                "         WHERE gr.group_id = g.id AND gr.active = 1) AS role_count "
                "FROM groups g ORDER BY g.name"
            ).fetchall()
        return [
            {
                "id": row["id"], "name": row["name"], "kind": row["kind"],
                "type_code": row["type_code"], "status": row["status"],
                "member_count": int(row["member_count"]),
                "manager_count": int(row["manager_count"]),
                "section_count": int(row["section_count"]),
                "role_count": int(row["role_count"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    @app.get("/api/v1/admin/groups/{group_id}")
    def admin_get_group(
        group_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Detalle de un grupo de Chorus con sus recuentos de catálogo."""
        if not _is_admin(profile):
            raise HTTPException(status_code=403, detail="Admin role required")
        with _connect(cfg) as conn:
            group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            row = conn.execute(
                "SELECT "
                " (SELECT COUNT(*) FROM group_members gm "
                "   WHERE gm.group_id = ? AND gm.status = 'active') AS member_count, "
                " (SELECT COUNT(*) FROM group_members gm "
                "   WHERE gm.group_id = ? AND gm.role = 'manager' "
                "     AND gm.status = 'active') AS manager_count, "
                " (SELECT COUNT(*) FROM group_sections gs "
                "   WHERE gs.group_id = ? AND gs.active = 1) AS section_count, "
                " (SELECT COUNT(*) FROM group_roles gr "
                "   WHERE gr.group_id = ? AND gr.scope = 'admin' AND gr.active = 1) AS admin_role_count, "
                " (SELECT COUNT(*) FROM group_roles gr "
                "   WHERE gr.group_id = ? AND gr.scope = 'musical' AND gr.active = 1) AS musical_role_count",
                (group_id, group_id, group_id, group_id, group_id),
            ).fetchone()
        return {
            "id": group["id"], "name": group["name"], "kind": group["kind"],
            "type_code": group["type_code"], "status": group["status"],
            "description": group["description"], "locality": group["locality"],
            "member_count": int(row["member_count"]),
            "manager_count": int(row["manager_count"]),
            "section_count": int(row["section_count"]),
            "admin_role_count": int(row["admin_role_count"]),
            "musical_role_count": int(row["musical_role_count"]),
        }

    @app.get("/api/v1/admin/groups/{group_id}/catalog")
    def admin_group_catalog(
        group_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Catálogos del grupo: cargos, roles musicales y secciones.

        Los tres selectores se alimentan de aquí y guardan estos identificadores
        en la pertenencia del miembro. Se rechaza cualquier id que no sea del
        grupo.
        """
        if not _is_admin(profile):
            raise HTTPException(status_code=403, detail="Admin role required")
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            section_rows = conn.execute(
                "SELECT id, code, name, scope, sort_order FROM group_sections "
                "WHERE group_id = ? AND active = 1 ORDER BY scope, sort_order, name",
                (group_id,),
            ).fetchall()
            admin_rows = conn.execute(
                "SELECT id, code, name, parent_id, sort_order FROM group_roles "
                "WHERE group_id = ? AND scope = 'admin' AND active = 1 ORDER BY sort_order, name",
                (group_id,),
            ).fetchall()
            musical_rows = conn.execute(
                "SELECT id, code, name, parent_id, sort_order FROM group_roles "
                "WHERE group_id = ? AND scope = 'musical' AND active = 1 ORDER BY sort_order, name",
                (group_id,),
            ).fetchall()
        return {
            "group_id": group_id,
            "sections": [dict(row) for row in section_rows],
            "admin_roles": [dict(row) for row in admin_rows],
            "musical_roles": [dict(row) for row in musical_rows],
        }

    @app.post("/api/v1/admin/groups/{group_id}/members", status_code=201)
    def admin_add_group_member(
        group_id: str,
        body: AdminMemberCreateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Incorpora un usuario existente a un grupo como miembro ordinario.

        Es el contrato de alta administrativa para herramientas externas. Antes
        de crear la pertenencia se **verifica la identidad en osap-auth** mediante
        el contrato M2M: un ``user_sub`` que Auth no reconoce se rechaza y no
        genera ninguna fila. El nombre que se muestra es el canónico de Auth, no
        el que aporte el administrador.

        No acepta ``role``: el alta crea siempre un ``member``. La concesión de
        gestor corresponde sólo a un gestor del grupo.
        """
        if not _is_admin(profile):
            raise HTTPException(status_code=403, detail="Admin role required")
        actor_id = str(profile["user_id"])
        now = utcnow()

        with _connect(cfg) as conn:
            group = conn.execute("SELECT id, name FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            existing = conn.execute(
                "SELECT * FROM group_members WHERE group_id = ? AND user_sub = ?",
                (group_id, body.user_sub),
            ).fetchone()
            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="User is already a member of this group",
                )
            # Los catálogos deben pertenecer a este grupo
            _validate_group_catalog_refs(
                conn, group_id,
                admin_role_id=body.admin_role_id,
                musical_role_id=body.musical_role_id,
                section_id=body.section_id,
            )
            # Verificar la identidad del DESTINATARIO (no la del actor) antes de
            # cualquier escritura en group_members o activity_log.
            canonical_name = _verify_member_identity(body.user_sub)
            member_id = uuid.uuid4().hex
            # display_name es una instantánea del nombre canónico de Auth, no una
            # fuente de verdad alternativa: se rellena desde Auth y nunca se usa
            # para verificar identidades.
            conn.execute(
                "INSERT INTO group_members "
                "(id, group_id, user_sub, role, status, display_name, "
                " admin_role_id, musical_role_id, section_id, granted_by, joined_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    member_id, group_id, body.user_sub, ORDINARY_MEMBER_ROLE, "active",
                    canonical_name,
                    body.admin_role_id, body.musical_role_id, body.section_id,
                    actor_id, now, now,
                ),
            )
            conn.execute(
                "INSERT INTO activity_log "
                "(legacy_id, group_id, event_type, actor, from_status, to_status, detail_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    _activity_legacy_id("mem", body.user_sub), group_id,
                    "member_added", actor_id, None, "active",
                    json.dumps({
                        "source": "admin_onboarding",
                        "role": ORDINARY_MEMBER_ROLE,
                        "identity_verified_by": "osap-auth",
                        "admin_role_id": body.admin_role_id,
                        "musical_role_id": body.musical_role_id,
                        "section_id": body.section_id,
                    }),
                    now,
                ),
            )
            new_member = conn.execute(
                "SELECT * FROM group_members WHERE id = ?", (member_id,)
            ).fetchone()
        return dict(new_member)

    @app.get("/api/v1/groups/{group_id}/articles")
    def list_group_articles(
        group_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id=? AND user_sub=? AND status='active'",
                (group_id, user_id),
            ).fetchone()
            if member is None and not admin:
                raise HTTPException(status_code=403, detail="Active member required")
            role = member["role"] if member is not None else MANAGER_ROLE
            rows = conn.execute(
                "SELECT * FROM group_articles WHERE group_id=? "
                "AND (? = 'manager' OR status='published' OR author_user_id=?) "
                "ORDER BY COALESCE(event_date, created_at) DESC, created_at DESC",
                (group_id, role, user_id),
            ).fetchall()
            return [
                _article_dto(
                    conn, row,
                    can_edit=admin or role == MANAGER_ROLE
                    or str(row["author_user_id"]) == user_id,
                    can_publish=admin or role == "manager",
                )
                for row in rows
            ]

    @app.get("/api/v1/articles/{article_id}")
    def get_article(
        article_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            row = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Article not found")
            can_edit, can_publish = _article_permissions(conn, row, user_id, profile)
            if row["status"] != "published" and not can_edit:
                raise HTTPException(status_code=403, detail="Article not available")
            return _article_dto(conn, row, can_edit=can_edit, can_publish=can_publish)

    @app.post("/api/v1/groups/{group_id}/articles", status_code=201)
    def create_article(
        group_id: str,
        body: ArticleBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        now = utcnow()
        with _connect(cfg) as conn:
            member = conn.execute(
                "SELECT role FROM group_members WHERE group_id=? AND user_sub=? AND status='active'",
                (group_id, user_id),
            ).fetchone()
            role = member["role"] if member is not None else None
            if not admin and role != MANAGER_ROLE:
                raise HTTPException(status_code=403, detail="Editorial role required")
            article_id = uuid.uuid4().hex
            base_slug = _slugify(body.title)
            slug = base_slug
            suffix = 2
            while conn.execute(
                "SELECT 1 FROM group_articles WHERE group_id=? AND slug=?", (group_id, slug)
            ).fetchone() is not None:
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            status = body.status if (admin or role == "manager") else "draft"
            conn.execute(
                "INSERT INTO group_articles "
                "(id,group_id,title,slug,summary,body,cover_url,event_date,status,"
                "author_user_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    article_id, group_id, body.title.strip(), slug, body.summary,
                    body.body, body.cover_url, body.event_date, status, user_id, now, now,
                ),
            )
            _replace_article_media(conn, article_id, body.media, now)
            row = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            return _article_dto(
                conn, row, can_edit=True, can_publish=admin or role == "manager",
            )

    @app.patch("/api/v1/articles/{article_id}")
    def update_article(
        article_id: str,
        body: ArticleUpdateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        now = utcnow()
        with _connect(cfg) as conn:
            row = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Article not found")
            can_edit, can_publish = _article_permissions(conn, row, user_id, profile)
            if not can_edit:
                raise HTTPException(status_code=403, detail="No puedes editar este artículo")
            updates: list[str] = []
            values: list[Any] = []
            for column in ("title", "summary", "body", "cover_url", "event_date"):
                value = getattr(body, column)
                if value is not None:
                    updates.append(f"{column}=?")
                    values.append(value.strip() if isinstance(value, str) else value)
            if updates:
                values.extend([now, article_id])
                conn.execute(
                    f"UPDATE group_articles SET {', '.join(updates)}, updated_at=? WHERE id=?",
                    tuple(values),
                )
            if body.media is not None:
                _replace_article_media(conn, article_id, body.media, now)
                conn.execute(
                    "UPDATE group_articles SET updated_at=? WHERE id=?", (now, article_id)
                )
            updated = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            return _article_dto(conn, updated, can_edit=True, can_publish=can_publish)

    @app.post("/api/v1/articles/{article_id}/publish")
    def publish_article(
        article_id: str,
        body: ArticleReviewBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        now = utcnow()
        with _connect(cfg) as conn:
            row = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Article not found")
            _, can_publish = _article_permissions(conn, row, user_id, profile)
            if not can_publish:
                raise HTTPException(status_code=403, detail="Publisher role required")
            conn.execute(
                "UPDATE group_articles SET status='published', publisher_user_id=?, "
                "reviewed_by=?, reviewed_at=?, review_note=?, published_at=?, updated_at=? "
                "WHERE id=?",
                (user_id, user_id, now, body.review_note, now, now, article_id),
            )
            # Activity log
            conn.execute(
                "INSERT INTO activity_log (legacy_id, group_id, article_id, event_type, actor, from_status, to_status, detail_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"pub-{article_id[:8]}", row["group_id"], article_id, "article_publish", user_id, "draft", "published", json.dumps({"review_note": body.review_note}), now),
            )
            updated = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            return _article_dto(conn, updated, can_edit=True, can_publish=True)

    @app.post("/api/v1/articles/{article_id}/withdraw")
    def withdraw_article(
        article_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        now = utcnow()
        with _connect(cfg) as conn:
            row = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Article not found")
            can_edit, can_publish = _article_permissions(conn, row, user_id, profile)
            if not can_edit:
                raise HTTPException(status_code=403, detail="No puedes retirar este artículo")
            from_status = row["status"]
            conn.execute(
                "UPDATE group_articles SET status='withdrawn', updated_at=? WHERE id=?",
                (now, article_id),
            )
            # Activity log
            conn.execute(
                "INSERT INTO activity_log (legacy_id, group_id, article_id, event_type, actor, from_status, to_status, detail_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"wdr-{article_id[:8]}", row["group_id"], article_id, "article_withdraw", user_id, from_status, "withdrawn", None, now),
            )
            updated = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            return _article_dto(conn, updated, can_edit=True, can_publish=can_publish)

    @app.delete("/api/v1/articles/{article_id}")
    def delete_article(
        article_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            row = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Article not found")
            can_edit, _ = _article_permissions(conn, row, user_id, profile)
            if not can_edit:
                raise HTTPException(status_code=403, detail="No puedes borrar este artículo")
            if row["status"] == "published":
                raise HTTPException(status_code=409, detail="Retira el artículo antes de borrarlo")
            conn.execute("DELETE FROM group_article_media WHERE article_id=?", (article_id,))
            conn.execute("DELETE FROM group_articles WHERE id=?", (article_id,))
        return {"ok": True}
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
            with _connect(cfg) as conn:
                group = None
                role = None
                if body.scope != "personal":
                    if not body.group_id:
                        raise HTTPException(status_code=400, detail="Group is required")
                    group = conn.execute(
                        "SELECT * FROM groups WHERE id = ?", (body.group_id,)
                    ).fetchone()
                    if group is None:
                        raise HTTPException(status_code=404, detail="Group not found")
                    member = conn.execute(
                        "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? "
                        "AND status = 'active'",
                        (group["id"], user_id),
                    ).fetchone()
                    role = member["role"] if member is not None else None
                    if body.scope == "group" and not admin and role != "manager":
                        raise HTTPException(status_code=403, detail="Group manager role required")
                    if body.scope == "section" and not admin and member is None:
                        raise HTTPException(status_code=403, detail="Active group member required")
                    if body.scope == "section" and not body.section_id:
                        raise HTTPException(status_code=400, detail="Section is required")
                entity_id = group["entity_id"] if group is not None else user_id
                stored_scope = "global" if body.scope == "personal" else "groups"
                series_id = uuid.uuid4().hex if body.recurrence != "none" else None
                ids = _insert_event_rows(
                    conn,
                    body=body,
                    user_id=user_id,
                    group=group,
                    entity_id=entity_id,
                    stored_scope=stored_scope,
                    series_id=series_id,
                    badge=_creator_badge(body.scope, role, admin),
                )
                row = conn.execute(
                    "SELECT e.*, g.name AS group_name, "
                    "(SELECT target_value FROM event_targets t WHERE t.event_id = e.id AND t.target_type = 'section' LIMIT 1) AS section_id "
                    "FROM events e "
                    "LEFT JOIN groups g ON g.id = e.group_id WHERE e.id = ?",
                    (ids[0],),
                ).fetchone()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _event_dto(
            row, my_rsvp=None, group_name=row["group_name"], can_manage=True
        )
    @app.patch("/api/v1/events/{event_id}")
    def update_event(
        event_id: str,
        body: EventBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        try:
            with _connect(cfg) as conn:
                event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
                if event is None:
                    raise HTTPException(status_code=404, detail="Event not found")
                if not _can_manage_event(conn, event, user_id, profile):
                    raise HTTPException(status_code=403, detail="No puedes modificar esta cita")
                group = None
                role = None
                if body.scope != "personal":
                    if not body.group_id:
                        raise HTTPException(status_code=400, detail="Group is required")
                    group = conn.execute(
                        "SELECT * FROM groups WHERE id = ?", (body.group_id,)
                    ).fetchone()
                    if group is None:
                        raise HTTPException(status_code=404, detail="Group not found")
                    member = conn.execute(
                        "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ? "
                        "AND status = 'active'",
                        (group["id"], user_id),
                    ).fetchone()
                    role = member["role"] if member is not None else None
                    if body.scope == "group" and not admin and role != "manager":
                        raise HTTPException(status_code=403, detail="Group manager role required")
                    if body.scope == "section" and not admin and member is None:
                        raise HTTPException(status_code=403, detail="Active group member required")
                    if body.scope == "section" and not body.section_id:
                        raise HTTPException(status_code=400, detail="Section is required")
                entity_id = group["entity_id"] if group is not None else user_id
                stored_scope = "global" if body.scope == "personal" else "groups"
                badge = _creator_badge(body.scope, role, admin)
                if body.edit_scope == "series" and event["series_id"]:
                    conn.execute(
                        "DELETE FROM event_rsvps WHERE event_id IN "
                        "(SELECT id FROM events WHERE series_id = ?)",
                        (event["series_id"],),
                    )
                    conn.execute(
                        "DELETE FROM event_targets WHERE event_id IN "
                        "(SELECT id FROM events WHERE series_id = ?)",
                        (event["series_id"],),
                    )
                    conn.execute(
                        "DELETE FROM event_groups WHERE event_id IN "
                        "(SELECT id FROM events WHERE series_id = ?)",
                        (event["series_id"],),
                    )
                    conn.execute("DELETE FROM events WHERE series_id = ?", (event["series_id"],))
                    series_id = event["series_id"] if body.recurrence != "none" else None
                    ids = _insert_event_rows(
                        conn,
                        body=body,
                        user_id=user_id,
                        group=group,
                        entity_id=entity_id,
                        stored_scope=stored_scope,
                        series_id=series_id,
                        badge=badge,
                    )
                    updated_id = ids[0]
                else:
                    starts_at = _normalise_iso(body.starts_at)
                    ends_at = _normalise_iso(body.ends_at) if body.ends_at else None
                    conn.execute(
                        "UPDATE events SET group_id=?, entity_id=?, scope=?, kind=?, title=?, "
                        "starts_at=?, ends_at=?, location=?, notes=?, updated_at=?, "
                        "recurrence=?, recurrence_until=?, creator_badge=? WHERE id=?",
                        (
                            group["id"] if group is not None else None, entity_id, stored_scope,
                            body.kind, body.title.strip(), starts_at, ends_at, body.location,
                            body.notes, utcnow(), body.recurrence,
                            _normalise_iso(body.recurrence_until) if body.recurrence_until else None,
                            badge, event_id,
                        ),
                    )
                    conn.execute("DELETE FROM event_targets WHERE event_id = ?", (event_id,))
                    conn.execute("DELETE FROM event_groups WHERE event_id = ?", (event_id,))
                    if group is not None:
                        conn.execute(
                            "INSERT OR IGNORE INTO event_groups (event_id, group_id) VALUES (?,?)",
                            (event_id, group["id"]),
                        )
                    if body.scope == "section" and body.section_id:
                        conn.execute(
                            "INSERT OR IGNORE INTO event_targets "
                            "(event_id,target_type,target_value) VALUES (?,?,?)",
                            (event_id, "section", body.section_id),
                        )
                    if body.scope == "users":
                        for sub in body.recipient_subs:
                            conn.execute(
                                "INSERT OR IGNORE INTO event_targets "
                                "(event_id,target_type,target_value) VALUES (?,?,?)",
                                (event_id, "user", sub),
                            )
                    updated_id = event_id
                row = conn.execute(
                    "SELECT e.*, g.name AS group_name, "
                    "(SELECT target_value FROM event_targets t WHERE t.event_id = e.id AND t.target_type = 'section' LIMIT 1) AS section_id "
                    "FROM events e "
                    "LEFT JOIN groups g ON g.id = e.group_id WHERE e.id = ?",
                    (updated_id,),
                ).fetchone()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _event_dto(row, my_rsvp=None, group_name=row["group_name"], can_manage=True)

    @app.delete("/api/v1/events/{event_id}")
    def delete_event(
        event_id: str,
        scope: Literal["single", "series"] = "single",
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            if event is None:
                raise HTTPException(status_code=404, detail="Event not found")
            if not _can_manage_event(conn, event, user_id, profile):
                raise HTTPException(status_code=403, detail="No puedes borrar esta cita")
            if scope == "series" and event["series_id"]:
                ids = [
                    row["id"]
                    for row in conn.execute(
                        "SELECT id FROM events WHERE series_id = ?", (event["series_id"],)
                    ).fetchall()
                ]
            else:
                ids = [event_id]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                conn.execute(f"DELETE FROM event_rsvps WHERE event_id IN ({placeholders})", tuple(ids))
                conn.execute(f"DELETE FROM event_targets WHERE event_id IN ({placeholders})", tuple(ids))
                conn.execute(f"DELETE FROM event_groups WHERE event_id IN ({placeholders})", tuple(ids))
                conn.execute(f"DELETE FROM events WHERE id IN ({placeholders})", tuple(ids))
        return {"ok": True, "deleted": len(ids)}
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
                "VALUES (?,?,?,?,?) ON DUPLICATE KEY UPDATE "
                "status = VALUES(status), comment = VALUES(comment), "
                "updated_at = VALUES(updated_at)",
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

    def _material_folder(value: str | None) -> str | None:
        if not value:
            return None
        parts = [part for part in str(value).replace("\\", "/").split("/") if part and part not in (".", "..")]
        return "/".join(parts)[:900] or None

    def _material_display(name: str, original: str) -> str:
        suffix = Path(original).suffix.lower()
        if suffix in {".mxl", ".xml"}:
            return f"Partitura{suffix}"
        if suffix in {".mid", ".midi"}:
            return f"Partitura{suffix}"
        if suffix in {".mp3", ".wav", ".ogg", ".flac"}:
            return f"Audio{suffix}"
        if suffix == ".pdf":
            return "Partitura.pdf"
        return _safe_name(name)

    def _validate_material(name: str, data: bytes) -> str | None:
        suffix = Path(name).suffix.lower()
        allowed = {".pdf", ".xml", ".mxl", ".mid", ".midi", ".mp3", ".wav", ".ogg", ".flac"}
        if suffix not in allowed:
            return f"Formato no admitido: {suffix or 'sin extensión'}"
        if suffix == ".mxl":
            try:
                validate_mxl(data, name)
            except ValueError as exc:
                return str(exc)
        elif suffix == ".xml":
            try:
                root = ET.fromstring(data)
                if root.tag.rsplit("}", 1)[-1] not in {"score-partwise", "score-timewise"}:
                    return "El XML no es MusicXML"
            except ET.ParseError:
                return "XML no válido"
        elif suffix == ".pdf" and not data.startswith(b"%PDF"):
            return "El PDF no tiene cabecera válida"
        return None

    @app.get("/api/v1/material/tree")
    def material_tree(
        group_id: str | None = None,
        user: Principal = Depends(current_user),
    ) -> list[dict[str, Any]]:
        with _connect(cfg) as conn:
            if group_id:
                member = conn.execute(
                    "SELECT role, section_id FROM group_members WHERE group_id=? "
                    "AND user_sub=? AND status='active'", (group_id, user.sub)
                ).fetchone()
                if member is None:
                    raise HTTPException(status_code=403, detail="Not a member of this group")
                resources = conn.execute(
                    "SELECT r.id,r.work_id,r.version_label,r.part_label,r.material_status,"
                    "r.resource_type,w.title,w.subtitle,w.created_at,w.updated_at "
                    "FROM resources r JOIN works w ON w.id=r.work_id "
                    "WHERE r.group_id=? AND r.material_status='published' "
                    "AND (r.group_section_id IS NULL OR r.group_section_id=?) "
                    "ORDER BY w.title, r.created_at", (group_id, member["section_id"])
                ).fetchall()
                grouped: dict[str, dict[str, Any]] = {}
                for resource in resources:
                    item = grouped.setdefault(
                        str(resource["work_id"]),
                        {
                            "id": resource["work_id"],
                            "title": resource["title"],
                            "subtitle": resource["subtitle"],
                            "created_at": resource["created_at"],
                            "updated_at": resource["updated_at"],
                            "resources": [],
                        },
                    )
                    files = conn.execute(
                        "SELECT id,name,display_name,original_name,folder_path,mime_type,"
                        "size_bytes,sha256,status FROM files WHERE resource_id=? "
                        "ORDER BY folder_path, display_name, name", (resource["id"],)
                    ).fetchall()
                    res = {
                        "id": resource["id"],
                        "version_label": resource["version_label"],
                        "part_label": resource["part_label"],
                        "material_status": resource["material_status"],
                        "resource_type": resource["resource_type"],
                        "files": [dict(row) for row in files],
                    }
                    item["resources"].append(res)
                return list(grouped.values())

            works = conn.execute(
                "SELECT id,title,subtitle,created_at,updated_at FROM works "
                "WHERE owner_sub=? ORDER BY updated_at DESC", (user.sub,)
            ).fetchall()
            result = []
            for work in works:
                resources = conn.execute(
                    "SELECT id,version_label,part_label,material_status,resource_type "
                    "FROM resources WHERE work_id=? ORDER BY created_at, id", (work["id"],)
                ).fetchall()
                item = dict(work)
                item["resources"] = []
                for resource in resources:
                    files = conn.execute(
                        "SELECT id,name,display_name,original_name,folder_path,mime_type,"
                        "size_bytes,sha256,status FROM files WHERE resource_id=? "
                        "ORDER BY folder_path, display_name, name", (resource["id"],)
                    ).fetchall()
                    res = dict(resource)
                    res["files"] = [dict(row) for row in files]
                    item["resources"].append(res)
                result.append(item)
        return result

    @app.get("/api/v1/material/manifest")
    def material_manifest(
        group_id: str | None = None, user: Principal = Depends(current_user)
    ) -> dict[str, Any]:
        if not group_id:
            raise HTTPException(status_code=400, detail="group_id required")
        with _connect(cfg) as conn:
            member = conn.execute(
                "SELECT section_id FROM group_members WHERE group_id=? AND user_sub=? "
                "AND status='active'", (group_id, user.sub)
            ).fetchone()
            if member is None:
                raise HTTPException(status_code=403, detail="Not a member of this group")
            rows = conn.execute(
                "SELECT r.id,r.version_label,r.part_label,r.group_section_id,r.updated_at,"
                "w.id AS work_id,w.title,f.id AS file_id,f.display_name,f.name,"
                "f.folder_path,f.sha256,f.size_bytes,f.mime_type "
                "FROM resources r JOIN works w ON w.id=r.work_id "
                "JOIN files f ON f.resource_id=r.id "
                "WHERE r.group_id=? AND r.material_status='published' "
                "AND f.status='available' "
                "AND (r.group_section_id IS NULL OR r.group_section_id=?) "
                "ORDER BY w.title, r.version_label, f.folder_path, f.display_name",
                (group_id, member["section_id"]),
            ).fetchall()
        works: dict[str, dict[str, Any]] = {}
        for row in rows:
            work = works.setdefault(
                str(row["work_id"]),
                {"work_id": row["work_id"], "title": row["title"], "versions": {}},
            )
            version = work["versions"].setdefault(
                str(row["id"]),
                {
                    "resource_id": row["id"],
                    "version_label": row["version_label"],
                    "section_id": row["group_section_id"],
                    "updated_at": row["updated_at"],
                    "files": [],
                },
            )
            version["files"].append(
                {
                    "file_id": row["file_id"],
                    "path": f"{row['folder_path'] + '/' if row['folder_path'] else ''}{row['display_name'] or row['name']}",
                    "sha256": row["sha256"],
                    "size_bytes": row["size_bytes"],
                    "mime_type": row["mime_type"],
                    "download_url": f"/api/v1/material/files/{row['file_id']}/download",
                }
            )
        return {
            "group_id": group_id,
            "generated_at": utcnow(),
            "works": [
                {**work, "versions": list(work["versions"].values())}
                for work in works.values()
            ],
        }
    @app.post("/api/v1/material/import", status_code=201)
    async def material_import(
        metadata: str = Form(...),
        files: list[UploadFile] = File(...),
        user: Principal = Depends(current_user),
    ) -> dict[str, Any]:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="metadata no es JSON") from exc
        if not isinstance(meta, dict):
            raise HTTPException(status_code=400, detail="metadata inválida")
        version = str(meta.get("version_label") or "Original").strip() or "Original"
        part = _material_folder(meta.get("part_label"))
        preview = bool(meta.get("preview"))
        group_id = str(meta.get("group_id") or "") or None
        now = utcnow()
        if group_id:
            with _connect(cfg) as check:
                membership = check.execute(
                    "SELECT role FROM group_members WHERE group_id=? AND user_sub=? "
                    "AND status='active'", (group_id, user.sub)
                ).fetchone()
            if membership is None or membership["role"] != "manager":
                raise HTTPException(status_code=403, detail="Solo el gestor del grupo puede publicar material")
        prepared: list[dict[str, Any]] = []
        duplicates: list[str] = []
        for upload in files:
            relative = str(upload.filename or "archivo").replace("\\", "/")
            relative_parts = [
                item for item in relative.split("/") if item and item not in (".", "..")
            ]
            original = _safe_name(relative_parts[-1] if relative_parts else "archivo")
            folder = _material_folder("/".join(relative_parts[:-1])) or part
            data = await upload.read()
            if len(data) > 50 * 1024 * 1024:
                raise HTTPException(status_code=413, detail=f"{original}: supera 50 MB")
            error = _validate_material(original, data)
            if error:
                raise HTTPException(status_code=400, detail=f"{original}: {error}")
            sha = hashlib.sha256(data).hexdigest()
            with _connect(cfg) as conn:
                duplicate = conn.execute(
                    "SELECT f.id FROM files f JOIN resources r ON r.id=f.resource_id "
                    "JOIN works w ON w.id=r.work_id WHERE w.owner_sub=? AND f.sha256=? LIMIT 1",
                    (user.sub, sha),
                ).fetchone()
            if duplicate is not None:
                duplicates.append(original)
                continue
            if preview:
                prepared.append(
                    {
                        "original": original,
                        "sha": sha,
                        "mime": upload.content_type or "",
                        "folder": folder,
                        "display_name": _material_display(original, original),
                    }
                )
                continue
            pointer = _save_private(cfg, data, Path(original).suffix.lower())
            prepared.append(
                {"original": original, "data": data, "sha": sha, "pointer": pointer, "mime": upload.content_type or "", "folder": folder}
            )
        if preview:
            return {"status": "preview", "files": prepared, "duplicates": duplicates}
        if not prepared:
            return {"status": "duplicate", "files": [], "duplicates": duplicates}
        work_id = str(meta.get("work_id") or "")
        with _connect(cfg) as conn:
            if cfg.database_url:
                conn.execute("SET FOREIGN_KEY_CHECKS=0")
            else:
                conn.execute("PRAGMA foreign_keys=OFF")
            if work_id:
                work = conn.execute(
                    "SELECT * FROM works WHERE id=? AND owner_sub=?", (work_id, user.sub)
                ).fetchone()
                if work is None:
                    raise HTTPException(status_code=404, detail="Work not found")
                title = str(work["title"])
            else:
                title = str(meta.get("work_title") or meta.get("title") or "").strip()
                if not title:
                    raise HTTPException(status_code=400, detail="Falta work_title")
                work_id = uuid.uuid4().hex
                resource_id = uuid.uuid4().hex
                first_id = uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO works (id,title,subtitle,created_at,updated_at,"
                    "required_resource_id,owner_sub) VALUES (?,?,?,?,?,?,?)",
                    (work_id, title, meta.get("subtitle"), now, now, resource_id, user.sub),
                )
                conn.execute(
                    "INSERT INTO resources (id,work_id,resource_type,title,description,"
                    "provenance,rights_license,created_at,updated_at,required_file_id,"
                    "version_label,part_label,material_status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (resource_id, work_id, "score", version, None, None, None, now, now,
                     first_id, version, part, "draft"),
                )
            resource = conn.execute(
                "SELECT * FROM resources WHERE work_id=? AND version_label=? "
                "ORDER BY created_at LIMIT 1", (work_id, version)
            ).fetchone()
            if resource is None:
                resource_id = uuid.uuid4().hex
                first_id = uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO resources (id,work_id,resource_type,title,created_at,updated_at,"
                    "required_file_id,version_label,part_label,material_status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (resource_id, work_id, "score", version, now, now, first_id, version, part, "draft"),
                )
            else:
                resource_id = str(resource["id"])
                first_id = str(resource["required_file_id"])
            created = []
            for item in prepared:
                display = _material_display(item["original"], item["original"])
                existing = conn.execute(
                    "SELECT display_name FROM files WHERE resource_id=? AND COALESCE(folder_path,'')=?",
                    (resource_id, item["folder"] or ""),
                ).fetchall()
                used = {str(row["display_name"] or "") for row in existing}
                candidate = display
                n = 2
                while candidate in used:
                    stem = Path(display).stem
                    candidate = f"{stem}-{n}{Path(display).suffix}"
                    n += 1
                file_id = uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO files (id,resource_id,name,mime_type,size_bytes,status,sha256,"
                    "storage_pointer,created_at,updated_at,folder_path,display_name,original_name) "
                    "VALUES (?,?,?,?,?,'available',?,?,?,?,?,?,?)",
                    (file_id, resource_id, candidate, item["mime"], len(item["data"]),
                     item["sha"], item["pointer"], now, now, item["folder"], candidate, item["original"]),
                )
                created.append({"id": file_id, "name": candidate, "original": item["original"]})
            if created:
                conn.execute(
                    "INSERT OR IGNORE INTO library_items "
                    "(id,owner_sub,kind,work_id,title,created_at,updated_at) "
                    "VALUES (?,?,'local_work',?,?,?,?)",
                    (uuid.uuid4().hex, user.sub, work_id, title, now, now),
                )
        return {"status": "created", "work_id": work_id, "resource_id": resource_id,
                "files": created, "duplicates": duplicates}
    def _owned_resource(resource_id: str, user: Principal):
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT r.*, w.owner_sub FROM resources r JOIN works w ON w.id=r.work_id "
                "WHERE r.id=? AND w.owner_sub=?", (resource_id, user.sub)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Resource not found")
        return row

    @app.patch("/api/v1/material/resources/{resource_id}")
    def material_resource_update(
        resource_id: str,
        body: dict[str, Any],
        user: Principal = Depends(current_user),
    ) -> dict[str, Any]:
        _owned_resource(resource_id, user)
        allowed = {"version_label", "part_label", "material_status"}
        updates = {key: value for key, value in body.items() if key in allowed}
        if "material_status" in updates and updates["material_status"] not in {
            "draft", "reviewed", "published", "retired"
        }:
            raise HTTPException(status_code=400, detail="Estado no válido")
        if not updates:
            raise HTTPException(status_code=400, detail="Nada que actualizar")
        with _connect(cfg) as conn:
            columns = ", ".join(f"{key}=?" for key in updates)
            conn.execute(
                f"UPDATE resources SET {columns}, updated_at=? WHERE id=?",
                (*updates.values(), utcnow(), resource_id),
            )
            row = conn.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
        return dict(row)

    @app.get("/api/v1/material/files/{file_id}/download")
    def material_file_download(
        file_id: str, user: Principal = Depends(current_user)
    ) -> Response:
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT f.*, r.material_status FROM files f "
                "JOIN resources r ON r.id=f.resource_id JOIN works w ON w.id=r.work_id "
                "WHERE f.id=? AND w.owner_sub=?", (file_id, user.sub)
            ).fetchone()
        if row is None or row["status"] != "available":
            raise HTTPException(status_code=404, detail="File not found")
        raw = _read_private(cfg, str(row["storage_pointer"]))
        return Response(
            content=raw,
            media_type=str(row["mime_type"] or "application/octet-stream"),
            headers={
                "Content-Disposition": f'attachment; filename="{_safe_name(str(row["display_name"] or row["name"]))}"'
            },
        )
    @app.post("/api/v1/material/resources/{resource_id}/publish")
    def material_resource_publish(
        resource_id: str, user: Principal = Depends(current_user)
    ) -> dict[str, Any]:
        _owned_resource(resource_id, user)
        with _connect(cfg) as conn:
            conn.execute(
                "UPDATE resources SET material_status='published', updated_at=? WHERE id=?",
                (utcnow(), resource_id),
            )
            row = conn.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
        return dict(row)

    @app.patch("/api/v1/material/files/{file_id}")
    def material_file_update(
        file_id: str,
        body: dict[str, Any],
        user: Principal = Depends(current_user),
    ) -> dict[str, Any]:
        with _connect(cfg) as conn:
            row = conn.execute(
                "SELECT f.*, w.owner_sub FROM files f JOIN resources r ON r.id=f.resource_id "
                "JOIN works w ON w.id=r.work_id WHERE f.id=? AND w.owner_sub=?",
                (file_id, user.sub),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="File not found")
            allowed = {"display_name", "folder_path"}
            updates = {key: value for key, value in body.items() if key in allowed}
            if updates:
                columns = ", ".join(f"{key}=?" for key in updates)
                conn.execute(
                    f"UPDATE files SET {columns}, updated_at=? WHERE id=?",
                    (*updates.values(), utcnow(), file_id),
                )
            updated = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
        return dict(updated)


    # ===== spaces endpoints =====
    @app.get("/api/v1/spaces")
    def list_spaces(
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        """List all spaces accessible to the current user."""
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        with _connect(cfg) as conn:
            if admin:
                rows = conn.execute(
                    "SELECT * FROM spaces ORDER BY created_at DESC"
                ).fetchall()
            else:
                # owner_sub sólo concede visibilidad en espacios PERSONALES.
                # Los espacios de grupo/proyecto dependen exclusivamente de la
                # membresía activa: quien abandona o es expulsado deja de verlos.
                rows = conn.execute(
                    """
                    SELECT s.* FROM spaces s
                    WHERE (s.space_type = 'personal' AND s.owner_sub = ?)
                       OR (s.space_type IN ('group','project')
                           AND s.group_id IS NOT NULL
                           AND EXISTS (
                               SELECT 1 FROM group_members gm
                               WHERE gm.group_id = s.group_id
                                 AND gm.user_sub = ?
                                 AND gm.status = 'active'
                           ))
                    ORDER BY s.created_at DESC
                    """,
                    (user_id, user_id),
                ).fetchall()
        return [_space_dto(row) for row in rows]

    @app.post("/api/v1/spaces", status_code=201)
    def create_space(
        body: SpaceCreateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Create a new space."""
        user_id = str(profile["user_id"])
        now = utcnow()
        space_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            # Validate space_type constraints
            if body.space_type == "personal" and body.group_id:
                raise HTTPException(
                    status_code=400,
                    detail="Personal spaces cannot have a group_id"
                )
            if body.space_type in ("group", "project") and not body.group_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"{body.space_type} spaces must have a group_id"
                )
            # Validate group_id if provided
            if body.group_id:
                group = conn.execute(
                    "SELECT 1 FROM groups WHERE id = ?", (body.group_id,)
                ).fetchone()
                if group is None:
                    raise HTTPException(status_code=404, detail="Group not found")
                # Conocer el group_id no basta: hace falta ser manager del grupo
                # (o admin de plataforma) para crear un espacio compartido.
                if not _is_admin(profile):
                    member = _group_membership(conn, body.group_id, user_id)
                    if member is None or member["role"] != "manager":
                        raise HTTPException(
                            status_code=403,
                            detail="Only group managers can create spaces for this group"
                        )
            # owner_sub representa propietario PERSONAL: sólo aplica a espacios
            # personales. Un espacio de grupo/proyecto no pertenece a un usuario.
            owner_sub = user_id if body.space_type == "personal" else None
            conn.execute(
                "INSERT INTO spaces "
                "(id, space_type, owner_sub, group_id, name, description, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    space_id, body.space_type, owner_sub, body.group_id,
                    body.name.strip(), body.description, now, now,
                ),
            )
            row = conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()
        return _space_dto(row)

    @app.get("/api/v1/spaces/{space_id}")
    def get_space(
        space_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Get a space by ID."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            if not _can_view_space(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            row = conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Space not found")
        return _space_dto(row)

    @app.patch("/api/v1/spaces/{space_id}")
    def update_space(
        space_id: str,
        body: SpaceUpdateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Update a space."""
        user_id = str(profile["user_id"])
        now = utcnow()
        with _connect(cfg) as conn:
            _require_space(conn, space_id)
            if not _can_manage_space(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            updates, values = _apply_patch_fields(
                body,
                ("name", "description"),
                frozenset({"name"}),
                transform={"name": lambda v: v.strip()},
            )
            if not updates:
                return _space_dto(_require_space(conn, space_id))
            updates.append("updated_at = ?")
            values.append(now)
            values.append(space_id)
            conn.execute(
                f"UPDATE spaces SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            return _space_dto(_require_space(conn, space_id))

    @app.post("/api/v1/spaces/{space_id}/convert", status_code=201)
    def convert_space(
        space_id: str,
        body: SpaceConvertBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Convert a personal space to a group or project space.
        This is a transactional operation."""
        user_id = str(profile["user_id"])
        now = utcnow()
        with _connect(cfg) as conn:
            space = conn.execute(
                "SELECT * FROM spaces WHERE id = ? AND space_type = 'personal'", (space_id,)
            ).fetchone()
            if space is None:
                raise HTTPException(status_code=404, detail="Personal space not found")
            if space["owner_sub"] != user_id:
                raise HTTPException(status_code=403, detail="Only the owner can convert their space")

            # Validate target_type
            if body.target_type not in ("group", "project"):
                raise HTTPException(status_code=400, detail="target_type must be 'group' or 'project'")

            # Create group or project
            group_id = uuid.uuid4().hex
            group_name = body.name or space["name"]
            group_description = body.description or space["description"] or ""

            conn.execute(
                "INSERT INTO groups "
                "(id, entity_id, name, timezone, created_by, join_code, created_at, updated_at, kind, description) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    group_id, user_id, group_name, "Europe/Madrid", user_id,
                    secrets.token_urlsafe(8).upper()[:12], now, now,
                    "project" if body.target_type == "project" else "grupo",
                    group_description,
                ),
            )

            # Create membership for owner
            member_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO group_members "
                "(id, group_id, user_sub, role, status, display_name, joined_at, updated_at) "
                "VALUES (?,?,?, 'manager', 'active', ?, ?, ?)",
                (member_id, group_id, user_id, "", now, now),
            )

            # Update space
            # Al convertirse en colectivo deja de ser un espacio personal: la
            # gestión pasa a derivar de la membresía de manager del nuevo grupo,
            # por lo que owner_sub se limpia.
            conn.execute(
                "UPDATE spaces SET space_type = ?, group_id = ?, owner_sub = NULL, updated_at = ? WHERE id = ?",
                (body.target_type, group_id, now, space_id),
            )

            # Activity log
            conn.execute(
                "INSERT INTO activity_log (legacy_id, group_id, event_type, actor, from_status, to_status, detail_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    f"conv-{user_id[:8]}-{int(time.time())}",
                    group_id, "space_converted", user_id, "personal", body.target_type,
                    json.dumps({"space_id": space_id, "target_type": body.target_type}),
                    now,
                ),
            )

            row = conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()
        return _space_dto(row)

    def _space_dto(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "space_type": row["space_type"],
            "owner_sub": row["owner_sub"],
            "group_id": row["group_id"],
            "name": row["name"],
            "description": row["description"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ===== preparation_works helpers =====
    def _group_space(conn, group_id: str) -> dict[str, Any] | None:
        """Espacio **general** de un grupo (space_type='group').

        Un grupo tiene un único espacio general y puede tener varios espacios de
        proyecto; por eso la resolución no admite 'project' ni depende del orden
        de la consulta: el índice único ``uq_spaces_general_group`` lo garantiza.

        Devuelve None si el grupo no existe.
        """
        group = conn.execute("SELECT id, name FROM groups WHERE id = ?", (group_id,)).fetchone()
        if group is None:
            return None
        space = conn.execute(
            "SELECT * FROM spaces WHERE group_id = ? AND space_type = 'group'",
            (group_id,),
        ).fetchone()
        if space is not None:
            return dict(space)

        # Creación idempotente: si otra petición la creó a la vez, el índice
        # único hace fallar el INSERT y se relee el espacio ya existente.
        space_id = uuid.uuid4().hex
        now = utcnow()
        try:
            conn.execute(
                "INSERT INTO spaces "
                "(id, space_type, owner_sub, group_id, name, description, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (space_id, "group", None, group_id, group["name"], None, now, now),
            )
        except Exception:
            conn.execute("SELECT 1")  # la transacción sigue utilizable
            existing = conn.execute(
                "SELECT * FROM spaces WHERE group_id = ? AND space_type = 'group'",
                (group_id,),
            ).fetchone()
            if existing is None:
                raise HTTPException(
                    status_code=409,
                    detail="No se pudo resolver el espacio general del grupo",
                )
            return dict(existing)

        row = conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()
        return dict(row)

    def _require_space(conn, space_id: str) -> dict[str, Any]:
        """Devuelve el espacio o lanza 404."""
        space = _get_space(conn, space_id)
        if space is None:
            raise HTTPException(status_code=404, detail="Space not found")
        return space

    def _preparation_work_dto(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "space_id": row["space_id"],
            "title": row["title"],
            "composer": row["composer"],
            "folder_path": row["folder_path"],
            "status": row["status"],
            "destination_type": row["destination_type"],
            "event_name": row["event_name"],
            "event_date": row["event_date"],
            "notes": row["notes"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _get_prep_work(conn, space_id: str, work_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM preparation_works WHERE id = ? AND space_id = ?",
            (work_id, space_id),
        ).fetchone()
        return dict(row) if row is not None else None

    def _require_prep_work(conn, space_id: str, work_id: str) -> dict[str, Any]:
        """Devuelve el trabajo del espacio indicado o lanza 404.

        La comprobación de espacio impide accesos cruzados: un trabajo de otro
        espacio responde 404 aunque el identificador exista.
        """
        work = _get_prep_work(conn, space_id, work_id)
        if work is None:
            raise HTTPException(status_code=404, detail="Preparation work not found")
        return work

    def _insert_prep_work(conn, space: dict[str, Any], body: PreparationWorkBody,
                          user_id: str) -> dict[str, Any]:
        """Crea un trabajo dentro de un espacio (modelo único para personal/grupo/proyecto)."""
        now = utcnow()
        work_id = uuid.uuid4().hex
        folder_path = f"preparation/{space['id']}/{work_id}"
        conn.execute(
            "INSERT INTO preparation_works "
            "(id, space_id, title, composer, folder_path, status, destination_type, "
            "event_name, event_date, notes, created_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                work_id, space["id"], body.title.strip(), body.composer, folder_path,
                "preparing", body.destination_type, body.event_name, body.event_date,
                body.notes, user_id, now, now,
            ),
        )
        return _require_prep_work(conn, space["id"], work_id)

    def _update_prep_work(conn, space_id: str, work_id: str,
                          body: PreparationWorkUpdateBody) -> dict[str, Any]:
        """Actualiza un trabajo aplicando semántica PATCH estricta.

        - Campo omitido por el cliente: conserva su valor actual.
        - Campo enviado con valor: se actualiza.
        - Campo enviado explícitamente como null: se limpia (si el campo admite
          null, que es el caso de todos los opcionales de este modelo).
        """
        work = _require_prep_work(conn, space_id, work_id)
        # model_fields_set distingue "omitido" de "enviado como null".
        updates, values = _apply_patch_fields(
            body, _PREP_WORK_UPDATABLE_COLUMNS, _PREP_WORK_NON_NULL_COLUMNS
        )
        if not updates:
            # Petición vacía: operación sin efecto, respuesta estable.
            return work
        values.append(utcnow())
        values.append(work_id)
        conn.execute(
            f"UPDATE preparation_works SET {', '.join(updates)}, updated_at=? WHERE id=?",
            tuple(values),
        )
        return _require_prep_work(conn, space_id, work_id)

    def _list_prep_works(conn, space_id: str, status: str | None,
                         destination_type: str | None) -> list[dict[str, Any]]:
        where = ["space_id = ?"]
        params: list[Any] = [space_id]
        if status:
            where.append("status = ?")
            params.append(status)
        if destination_type:
            where.append("destination_type = ?")
            params.append(destination_type)
        rows = conn.execute(
            f"SELECT * FROM preparation_works WHERE {' AND '.join(where)} ORDER BY created_at DESC",
            tuple(params),
        ).fetchall()
        return [_preparation_work_dto(row) for row in rows]

    # ===== preparation_works endpoints (espacios) =====
    @app.get("/api/v1/spaces/{space_id}/preparation-works")
    def list_space_preparation_works(
        space_id: str,
        status: str | None = None,
        destination_type: str | None = None,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        """Lista los trabajos de preparación de un espacio."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            _require_space(conn, space_id)
            if not _can_view_space(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            return _list_prep_works(conn, space_id, status, destination_type)

    @app.post("/api/v1/spaces/{space_id}/preparation-works", status_code=201)
    def create_space_preparation_work(
        space_id: str,
        body: PreparationWorkBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Crea un trabajo de preparación en un espacio personal, de grupo o de proyecto."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _require_space(conn, space_id)
            if not _can_manage_space_preparation(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            return _preparation_work_dto(_insert_prep_work(conn, space, body, user_id))

    @app.get("/api/v1/spaces/{space_id}/preparation-works/{work_id}")
    def get_space_preparation_work(
        space_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Consulta un trabajo de preparación de un espacio."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            _require_space(conn, space_id)
            if not _can_view_space(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            return _preparation_work_dto(_require_prep_work(conn, space_id, work_id))

    @app.patch("/api/v1/spaces/{space_id}/preparation-works/{work_id}")
    def update_space_preparation_work(
        space_id: str,
        work_id: str,
        body: PreparationWorkUpdateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Modifica un trabajo de preparación de un espacio."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            _require_space(conn, space_id)
            if not _can_manage_space_preparation(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            return _preparation_work_dto(_update_prep_work(conn, space_id, work_id, body))

    @app.delete("/api/v1/spaces/{space_id}/preparation-works/{work_id}")
    def delete_space_preparation_work(
        space_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Elimina un trabajo de preparación y sus referencias.

        No elimina Works, Resources ni Files: sólo el trabajo y sus filas hijas.
        """
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            _require_space(conn, space_id)
            if not _can_manage_space_preparation(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space_id, work_id)
            conn.execute("DELETE FROM preparation_works WHERE id = ? AND space_id = ?",
                         (work_id, space_id))
        return {"ok": True}

    # ===== preparation_works endpoints (compatibilidad: rutas de grupo) =====
    @app.get("/api/v1/groups/{group_id}/preparation-works/{work_id}")
    def get_preparation_work(
        group_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _group_space(conn, group_id)
            if space is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_view_space(conn, space["id"], user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            return _preparation_work_dto(_require_prep_work(conn, space["id"], work_id))

    @app.get("/api/v1/groups/{group_id}/preparation-works")
    def list_preparation_works(
        group_id: str,
        status: str | None = None,
        destination_type: str | None = None,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _group_space(conn, group_id)
            if space is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_view_space(conn, space["id"], user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            return _list_prep_works(conn, space["id"], status, destination_type)

    @app.post("/api/v1/groups/{group_id}/preparation-works", status_code=201)
    def create_preparation_work(
        group_id: str,
        body: PreparationWorkBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _group_space(conn, group_id)
            if space is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_space_preparation(conn, space["id"], user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            return _preparation_work_dto(_insert_prep_work(conn, space, body, user_id))

    @app.patch("/api/v1/groups/{group_id}/preparation-works/{work_id}")
    def update_preparation_work(
        group_id: str,
        work_id: str,
        body: PreparationWorkUpdateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _group_space(conn, group_id)
            if space is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_space_preparation(conn, space["id"], user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            return _preparation_work_dto(_update_prep_work(conn, space["id"], work_id, body))

    @app.delete("/api/v1/groups/{group_id}/preparation-works/{work_id}")
    def delete_preparation_work(
        group_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _group_space(conn, group_id)
            if space is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_space_preparation(conn, space["id"], user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space["id"], work_id)
            conn.execute("DELETE FROM preparation_works WHERE id = ? AND space_id = ?",
                         (work_id, space["id"]))
        return {"ok": True}


    # ===== preparation_work files: helpers comunes =====
    def _prep_file_container_work_id(work_id: str) -> str:
        """Id determinista de la Work contenedora de los archivos del trabajo.

        Al ser determinista, la creación es idempotente aunque se repita.
        """
        return f"pw-{work_id}"

    def _stream_stored_file(row: dict[str, Any], download_name: str) -> Response:
        """Sirve un archivo a partir de su registro en ``files``.

        La autorización se comprueba siempre antes de llamar aquí.
        """
        pointer = str(row["storage_pointer"] or "")
        if not pointer:
            raise HTTPException(status_code=404, detail="File has no storage pointer")

        candidate = Path(pointer)
        if not candidate.is_absolute():
            candidate = Path(cfg.storage_root).resolve() / pointer
        resolved = candidate.resolve()

        root = Path(cfg.storage_root).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Invalid file path")
        if not resolved.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        mime_type = row["mime_type"] if "mime_type" in row.keys() else None
        return Response(
            content=resolved.read_bytes(),
            media_type=mime_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )

    def _ensure_prep_file_container(conn, work: dict[str, Any], user_id: str) -> str:
        """Devuelve la Work que agrupa los archivos adjuntos al trabajo."""
        container_id = _prep_file_container_work_id(work["id"])
        existing = conn.execute("SELECT id FROM works WHERE id = ?", (container_id,)).fetchone()
        if existing is not None:
            return container_id
        now = utcnow()
        conn.execute(
            "INSERT INTO works (id, title, created_at, updated_at, required_resource_id, owner_sub) "
            "VALUES (?,?,?,?,?,?)",
            (container_id, f"Archivos de {work['title']}", now, now, container_id, user_id),
        )
        return container_id

    def _register_prep_file(
        conn,
        space: dict[str, Any],
        work: dict[str, Any],
        user_id: str,
        *,
        data: bytes,
        original_name: str,
        mime_type: str,
        purpose: str,
        sort_order: int = 0,
        part_label: str | None = None,
    ) -> dict[str, Any]:
        """Registra un archivo en el modelo unificado.

        Crea la cadena Work(contenedora) -> Resource -> File y la referencia
        preparation_work_files. Devuelve un DTO estable con ``id`` (referencia)
        y ``file_id`` (File de Chorus).
        """
        now = utcnow()
        container_id = _ensure_prep_file_container(conn, work, user_id)

        resource_id = uuid.uuid4().hex
        file_id = uuid.uuid4().hex
        suffix = Path(original_name).suffix.lower()
        pointer = _save_private(cfg, data, suffix, Path(work["folder_path"]))
        digest = hashlib.sha256(data).hexdigest()

        group_id = space.get("group_id")

        conn.execute(
            "INSERT INTO resources "
            "(id, work_id, resource_type, created_at, updated_at, required_file_id, "
            " part_label, material_status, group_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                resource_id, container_id, "preparation_file", now, now, file_id,
                part_label, "registered", group_id,
            ),
        )
        conn.execute(
            "INSERT INTO files "
            "(id, resource_id, name, mime_type, size_bytes, status, sha256, "
            " storage_pointer, created_at, updated_at, folder_path, display_name, original_name) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                file_id, resource_id, original_name, mime_type, len(data), "registered",
                digest, pointer, now, now, work["folder_path"], original_name, original_name,
            ),
        )
        # La Work contenedora apunta a su recurso (columna única por Work)
        conn.execute(
            "UPDATE works SET required_resource_id = ?, updated_at = ? WHERE id = ?",
            (resource_id, now, container_id),
        )

        ref_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO preparation_work_files "
            "(id, preparation_work_id, file_id, purpose, sort_order, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (ref_id, work["id"], file_id, purpose, sort_order, now),
        )
        return _prep_file_ref_by_id(conn, ref_id)

    def _prep_file_ref_by_id(conn, ref_id: str) -> dict[str, Any]:
        """DTO completo de una referencia (incluye metadatos del File y la Resource)."""
        row = conn.execute(
            "SELECT pwf.id AS id, pwf.preparation_work_id AS preparation_work_id, "
            "       pwf.file_id AS file_id, pwf.purpose AS purpose, "
            "       pwf.sort_order AS sort_order, pwf.created_at AS created_at, "
            "       f.name AS name, f.original_name AS original_name, "
            "       f.display_name AS display_name, f.mime_type AS mime_type, "
            "       f.size_bytes AS size_bytes, f.sha256 AS sha256, "
            "       r.part_label AS part_label "
            "FROM preparation_work_files pwf "
            "JOIN files f ON f.id = pwf.file_id "
            "LEFT JOIN resources r ON r.id = f.resource_id "
            "WHERE pwf.id = ?",
            (ref_id,),
        ).fetchone()
        return _preparation_work_file_dto(row)

    def _prep_file_section_allowed(conn, space: dict[str, Any], user_id: str,
                                   profile: dict[str, Any], *,
                                   resource_group_id: str | None,
                                   resource_section_id: str | None) -> bool:
        """Autorización de un archivo concreto según su restricción de sección.

        Punto único de decisión para listar, descargar y consultar archivos de
        una preparación. No delega en que el archivo se autorizara al
        incorporarlo: la restricción se comprueba en cada acceso.

        - Admin de plataforma: sí.
        - Sin `group_section_id`: sin restricción adicional (la visibilidad del
          espacio ya se validó antes).
        - Con `group_section_id`: sólo manager del grupo correspondiente o
          miembro de esa sección.
        """
        if _is_admin(profile):
            return True
        if not resource_section_id:
            return True
        group_id = resource_group_id or space.get("group_id")
        return _resource_section_allowed(conn, group_id, resource_section_id, user_id)

    def _list_prep_files(conn, space: dict[str, Any], work_id: str, user_id: str,
                         profile: dict[str, Any]) -> list[dict[str, Any]]:
        """Lista los archivos del trabajo filtrando por autorización de sección."""
        rows = conn.execute(
            "SELECT pwf.id AS id, pwf.file_id AS file_id, pwf.purpose AS purpose, "
            "       pwf.sort_order AS sort_order, pwf.created_at AS created_at, "
            "       f.name AS name, f.original_name AS original_name, "
            "       f.display_name AS display_name, f.mime_type AS mime_type, "
            "       f.size_bytes AS size_bytes, f.sha256 AS sha256, "
            "       r.part_label AS part_label, "
            "       r.group_id AS resource_group_id, "
            "       r.group_section_id AS resource_section_id "
            "FROM preparation_work_files pwf "
            "JOIN files f ON f.id = pwf.file_id "
            "LEFT JOIN resources r ON r.id = f.resource_id "
            "WHERE pwf.preparation_work_id = ? "
            "ORDER BY pwf.sort_order, pwf.id",
            (work_id,),
        ).fetchall()
        return [
            _preparation_work_file_dto(row)
            for row in rows
            if _prep_file_section_allowed(
                conn, space, user_id, profile,
                resource_group_id=row["resource_group_id"],
                resource_section_id=row["resource_section_id"],
            )
        ]

    def _stream_prep_file(conn, space: dict[str, Any], work_id: str, user_id: str,
                          profile: dict[str, Any], *, file_id: str | None = None,
                          file_name: str | None = None) -> Response:
        """Descarga un archivo de una preparación revalidando la autorización.

        Se usa tanto por id estable (ruta canónica) como por nombre (ruta
        histórica): la restricción de sección se comprueba en el momento de la
        descarga, no cuando el archivo se incorporó al trabajo.
        """
        if file_id is not None:
            row = conn.execute(
                "SELECT f.name AS name, f.storage_pointer AS storage_pointer, "
                "       f.mime_type AS mime_type, r.group_id AS resource_group_id, "
                "       r.group_section_id AS resource_section_id "
                "FROM preparation_work_files pwf "
                "JOIN files f ON f.id = pwf.file_id "
                "LEFT JOIN resources r ON r.id = f.resource_id "
                "WHERE pwf.preparation_work_id = ? AND pwf.file_id = ? LIMIT 1",
                (work_id, file_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT f.name AS name, f.storage_pointer AS storage_pointer, "
                "       f.mime_type AS mime_type, r.group_id AS resource_group_id, "
                "       r.group_section_id AS resource_section_id "
                "FROM preparation_work_files pwf "
                "JOIN files f ON f.id = pwf.file_id "
                "LEFT JOIN resources r ON r.id = f.resource_id "
                "WHERE pwf.preparation_work_id = ? "
                "  AND (f.name = ? OR f.original_name = ? OR f.display_name = ?) "
                "LIMIT 1",
                (work_id, file_name, file_name, file_name),
            ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="File not found")
        if not _prep_file_section_allowed(
            conn, space, user_id, profile,
            resource_group_id=row["resource_group_id"],
            resource_section_id=row["resource_section_id"],
        ):
            raise HTTPException(status_code=403, detail="Access denied")
        return _stream_stored_file(row, download_name=row["name"])

    @app.post("/api/v1/groups/{group_id}/preparation-works/{work_id}/files", status_code=201)
    async def upload_preparation_files(
        group_id: str,
        work_id: str,
        files: list[UploadFile] = File(...),
        parts: str = Form(default="[]"),
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Sube uno o más archivos a un trabajo (ruta histórica compatible).

        delega en el modelo unificado: cada archivo queda en el almacenamiento
        privado, con registro ``files`` y referencia ``preparation_work_files``.
        parts: JSON con {part_label, purpose} por archivo (misma longitud).
        """
        import json as json_std
        user_id = str(profile["user_id"])
        try:
            parts_list = json_std.loads(parts)
        except json_std.JSONDecodeError:
            raise HTTPException(status_code=400, detail="parts must be valid JSON array")
        if not isinstance(parts_list, list):
            raise HTTPException(status_code=400, detail="parts must be an array")
        if parts_list and len(parts_list) != len(files):
            raise HTTPException(status_code=400, detail="parts array length must match files count")

        with _connect(cfg) as conn:
            space = _group_space(conn, group_id)
            if space is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_space_preparation(conn, space["id"], user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            work = _require_prep_work(conn, space["id"], work_id)

            uploaded: list[dict[str, Any]] = []
            for i, upload in enumerate(files):
                relative = str(upload.filename or "archivo").replace("\\", "/")
                original = relative.split("/")[-1]
                data = await upload.read()
                if len(data) > cfg.max_upload_bytes:
                    raise HTTPException(
                        status_code=413, detail=f"{original}: exceeds max upload size"
                    )
                part_info = parts_list[i] if i < len(parts_list) else {}
                purpose = part_info.get("purpose") or "other"
                if purpose not in ("score", "part", "audio", "video", "other"):
                    purpose = "other"
                dto = _register_prep_file(
                    conn, space, work, user_id,
                    data=data,
                    original_name=original,
                    mime_type=upload.content_type or "",
                    purpose=purpose,
                    sort_order=i,
                    part_label=part_info.get("part_label"),
                )
                uploaded.append(dto)

        return {
            "work_id": work_id,
            "space_id": space["id"],
            "folder_path": work["folder_path"],
            "files": uploaded,
        }


    @app.get("/api/v1/groups/{group_id}/preparation-works/{work_id}/files")
    def list_preparation_files(
        group_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        """Lista los archivos del trabajo desde el modelo unificado."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _group_space(conn, group_id)
            if space is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_view_space(conn, space["id"], user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space["id"], work_id)
            return _list_prep_files(conn, space, work_id, user_id, profile)


    @app.get("/api/v1/groups/{group_id}/preparation-works/{work_id}/files/{file_name}/download")
    def download_preparation_file(
        group_id: str,
        work_id: str,
        file_name: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> Response:
        """Descarga por nombre (ruta histórica). Resuelve el File canónico.

        Misma autorización que la ruta canónica: la restricción de sección se
        revalida aquí, no se hereda del momento de la incorporación.
        """
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _group_space(conn, group_id)
            if space is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_view_space(conn, space["id"], user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space["id"], work_id)
            return _stream_prep_file(
                conn, space, work_id, user_id, profile, file_name=file_name
            )


    @app.get("/api/v1/spaces/{space_id}/preparation-works/{work_id}/files/{file_id}/download")
    def download_prep_file_by_id(
        space_id: str,
        work_id: str,
        file_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> Response:
        """Descarga por identificador estable de File (modelo unificado)."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _require_space(conn, space_id)
            if not _can_view_space(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space_id, work_id)
            return _stream_prep_file(
                conn, space, work_id, user_id, profile, file_id=file_id
            )


    @app.delete("/api/v1/groups/{group_id}/preparation-works/{work_id}/files/{file_name}")
    def delete_preparation_file(
        group_id: str,
        work_id: str,
        file_name: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Retira la referencia (ruta histórica por nombre).

        No borra el archivo físico ni el registro ``files``: sólo la relación
        con este trabajo.
        """
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _group_space(conn, group_id)
            if space is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_space_preparation(conn, space["id"], user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space["id"], work_id)
            row = conn.execute(
                "SELECT pwf.id AS ref_id "
                "FROM preparation_work_files pwf "
                "JOIN files f ON f.id = pwf.file_id "
                "WHERE pwf.preparation_work_id = ? "
                "  AND (f.name = ? OR f.original_name = ? OR f.display_name = ?) "
                "LIMIT 1",
                (work_id, file_name, file_name, file_name),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="File not found")
            conn.execute("DELETE FROM preparation_work_files WHERE id = ?", (row["ref_id"],))
        return {"ok": True}


    # ===== preparation_work_items endpoints =====
    @app.get("/api/v1/spaces/{space_id}/preparation-works/{work_id}/items")
    def list_preparation_work_items(
        space_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        """List all items in a preparation work."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            _require_space(conn, space_id)
            if not _can_view_space(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space_id, work_id)
            rows = conn.execute(
                "SELECT * FROM preparation_work_items WHERE preparation_work_id = ? ORDER BY sort_order, id",
                (work_id,),
            ).fetchall()
        return [_preparation_work_item_dto(row) for row in rows]

    @app.post("/api/v1/spaces/{space_id}/preparation-works/{work_id}/items", status_code=201)
    def create_preparation_work_item(
        space_id: str,
        work_id: str,
        body: PreparationWorkItemBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Add an item (work + resource) to a preparation work."""
        user_id = str(profile["user_id"])
        now = utcnow()
        item_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            space = _require_space(conn, space_id)
            if not _can_manage_space_preparation(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space_id, work_id)
            # Coherencia Work -> Resource (además de la FK compuesta de la BD).
            resource = conn.execute(
                "SELECT work_id FROM resources WHERE id = ?", (body.resource_id,)
            ).fetchone()
            if resource is None:
                raise HTTPException(status_code=404, detail="Resource not found")
            if resource["work_id"] != body.work_id:
                raise HTTPException(
                    status_code=400,
                    detail="Resource does not belong to the specified Work"
                )
            # El usuario debe poder usar la Work/Resource en este espacio: no basta
            # con conocer los identificadores.
            if not _can_use_work_in_space(conn, space, user_id, profile,
                                          body.work_id, body.resource_id):
                raise HTTPException(
                    status_code=403,
                    detail="Not allowed to use this work/resource in this space"
                )
            conn.execute(
                "INSERT INTO preparation_work_items "
                "(id, preparation_work_id, work_id, resource_id, voice_label, instrument, custom_title, sort_order, status, notes, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item_id, work_id, body.work_id, body.resource_id,
                    body.voice_label, body.instrument, body.custom_title,
                    body.sort_order, "pending", body.notes, now, now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM preparation_work_items WHERE id = ?", (item_id,)
            ).fetchone()
        return _preparation_work_item_dto(row)

    @app.patch("/api/v1/spaces/{space_id}/preparation-works/{work_id}/items/{item_id}")
    def update_preparation_work_item(
        space_id: str,
        work_id: str,
        item_id: str,
        body: PreparationWorkItemUpdateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Update an item in a preparation work."""
        user_id = str(profile["user_id"])
        now = utcnow()
        with _connect(cfg) as conn:
            _require_space(conn, space_id)
            if not _can_manage_space_preparation(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space_id, work_id)
            item = conn.execute(
                "SELECT * FROM preparation_work_items WHERE id = ? AND preparation_work_id = ?",
                (item_id, work_id),
            ).fetchone()
            if item is None:
                raise HTTPException(status_code=404, detail="Preparation work item not found")
            updates, values = _apply_patch_fields(
                body, _PREP_ITEM_UPDATABLE_COLUMNS, _PREP_ITEM_NON_NULL_COLUMNS
            )
            if not updates:
                return _preparation_work_item_dto(item)
            updates.append("updated_at = ?")
            values.append(now)
            values.append(item_id)
            conn.execute(
                f"UPDATE preparation_work_items SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            row = conn.execute(
                "SELECT * FROM preparation_work_items WHERE id = ?", (item_id,)
            ).fetchone()
        return _preparation_work_item_dto(row)

    @app.delete("/api/v1/spaces/{space_id}/preparation-works/{work_id}/items/{item_id}")
    def delete_preparation_work_item(
        space_id: str,
        work_id: str,
        item_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Remove an item from a preparation work."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            _require_space(conn, space_id)
            if not _can_manage_space_preparation(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space_id, work_id)
            item = conn.execute(
                "SELECT 1 FROM preparation_work_items WHERE id = ? AND preparation_work_id = ?",
                (item_id, work_id),
            ).fetchone()
            if item is None:
                raise HTTPException(status_code=404, detail="Preparation work item not found")
            conn.execute(
                "DELETE FROM preparation_work_items WHERE id = ?", (item_id,)
            )
        return {"ok": True}

    def _preparation_work_item_dto(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "preparation_work_id": row["preparation_work_id"],
            "work_id": row["work_id"],
            "resource_id": row["resource_id"],
            "voice_label": row["voice_label"],
            "instrument": row["instrument"],
            "custom_title": row["custom_title"],
            "sort_order": row["sort_order"],
            "status": row["status"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ===== preparation_work_files endpoints =====
    @app.get("/api/v1/spaces/{space_id}/preparation-works/{work_id}/files")
    def list_preparation_work_files(
        space_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        """List all files attached to a preparation work."""
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            space = _require_space(conn, space_id)
            if not _can_view_space(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space_id, work_id)
            return _list_prep_files(conn, space, work_id, user_id, profile)

    @app.post("/api/v1/spaces/{space_id}/preparation-works/{work_id}/files", status_code=201)
    def add_preparation_work_file(
        space_id: str,
        work_id: str,
        body: PreparationWorkFileBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Attach an existing file to a preparation work.

        No basta con que el archivo exista: el usuario debe poder utilizarlo
        (Work propia, o Resource compartida con el grupo del espacio y, si está
        restringida a una sección, ser miembro de ella).
        La referencia no altera el archivo físico ni su propiedad.
        """
        user_id = str(profile["user_id"])
        now = utcnow()
        file_ref_id = uuid.uuid4().hex
        with _connect(cfg) as conn:
            space = _require_space(conn, space_id)
            if not _can_manage_space_preparation(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            work = _require_prep_work(conn, space_id, work_id)
            # Validar existencia y acceso al archivo
            file = conn.execute(
                "SELECT id FROM files WHERE id = ?", (body.file_id,)
            ).fetchone()
            if file is None:
                raise HTTPException(status_code=404, detail="File not found")
            if not _can_use_file_in_space(conn, space, user_id, profile, body.file_id):
                raise HTTPException(
                    status_code=403,
                    detail="Not allowed to attach this file to this space"
                )
            conn.execute(
                "INSERT INTO preparation_work_files "
                "(id, preparation_work_id, file_id, purpose, sort_order, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (file_ref_id, work_id, body.file_id, body.purpose, body.sort_order, now),
            )
            row = conn.execute(
                "SELECT pwf.id AS id, pwf.preparation_work_id AS preparation_work_id, "
                "       pwf.file_id AS file_id, pwf.purpose AS purpose, "
                "       pwf.sort_order AS sort_order, pwf.created_at AS created_at, "
                "       f.name AS name, f.original_name AS original_name, "
                "       f.display_name AS display_name, f.mime_type AS mime_type, "
                "       f.size_bytes AS size_bytes, r.part_label AS part_label "
                "FROM preparation_work_files pwf "
                "JOIN files f ON f.id = pwf.file_id "
                "LEFT JOIN resources r ON r.id = f.resource_id "
                "WHERE pwf.id = ?",
                (file_ref_id,),
            ).fetchone()
        return _preparation_work_file_dto(row)

    @app.delete("/api/v1/spaces/{space_id}/preparation-works/{work_id}/files/{file_ref_id}")
    def remove_preparation_work_file(
        space_id: str,
        work_id: str,
        file_ref_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Remove a file reference from a preparation work.

        Sólo elimina la referencia: el archivo físico permanece intacto.
        """
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            _require_space(conn, space_id)
            if not _can_manage_space_preparation(conn, space_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Access denied")
            _require_prep_work(conn, space_id, work_id)
            file_ref = conn.execute(
                "SELECT 1 FROM preparation_work_files WHERE id = ? AND preparation_work_id = ?",
                (file_ref_id, work_id),
            ).fetchone()
            if file_ref is None:
                raise HTTPException(status_code=404, detail="File reference not found")
            conn.execute(
                "DELETE FROM preparation_work_files WHERE id = ?", (file_ref_id,)
            )
        return {"ok": True}

    def _preparation_work_file_dto(row: dict[str, Any]) -> dict[str, Any]:
        keys = row.keys()
        return {
            "id": row["id"],
            "preparation_work_id": row["preparation_work_id"] if "preparation_work_id" in keys else None,
            "file_id": row["file_id"],
            # Compatibilidad con el contrato histórico (name/original_name)
            "name": row["name"] if "name" in keys else None,
            "original_name": row["original_name"] if "original_name" in keys else None,
            "display_name": row["display_name"] if "display_name" in keys else None,
            "mime_type": row["mime_type"] if "mime_type" in keys else None,
            "size_bytes": row["size_bytes"] if "size_bytes" in keys else None,
            "part_label": row["part_label"] if "part_label" in keys else None,
            "purpose": row["purpose"],
            "sort_order": row["sort_order"],
            "created_at": row["created_at"],
        }

    return app


app = create_app()
