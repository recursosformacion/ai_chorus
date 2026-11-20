#!/usr/bin/env python3
"""Apply all API endpoint changes to main.py in one atomic operation."""

import re

# Read the original file
with open("app/main.py", "r") as f:
    content = f.read()

# 1. Add Pydantic models after MemberUpdateBody
models_insert = '''
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
'''

content = content.replace(
    '''class MemberUpdateBody(BaseModel):
    role: Literal["manager", "member"] | None = None
    admin_role_id: str | None = None
    musical_role_id: str | None = None
    section_id: str | None = None
    status: Literal["active", "removed"] | None = None


class MessageReplyBody(BaseModel):''',
    '''class MemberUpdateBody(BaseModel):
    role: Literal["manager", "member"] | None = None
    admin_role_id: str | None = None
    musical_role_id: str | None = None
    section_id: str | None = None
    status: Literal["active", "removed"] | None = None
''' + models_insert + '''
class MessageReplyBody(BaseModel):'''
)

# 2. Add DTO helpers after _event_dto
dto_helpers = '''

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
'''

content = content.replace(
    '''        "section_id": row["section_id"],
        "is_series": bool(row["series_id"]),
    }


def _connect(settings: Settings):''',
    '''        "section_id": row["section_id"],
        "is_series": bool(row["series_id"]),
    }
''' + dto_helpers + '''
def _connect(settings: Settings):'''
)

# 3. Update group_members endpoint to resolve role details
old_group_members = '''    @app.get("/api/v1/groups/{group_id}/members")
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
        ]'''

new_group_members = '''    @app.get("/api/v1/groups/{group_id}/members")
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
        return [
            {
                "user_sub": row["user_sub"],
                "role": row["role"],
                "name": row["display_name"] or row["user_sub"][:8],
                "voice_label": row["voice_label"],
                "section": row["section"],
                "admin_role_id": row["admin_role_id"],
                "admin_role": role_map.get(row["admin_role_id"]) if row["admin_role_id"] else None,
                "musical_role_id": row["musical_role_id"],
                "musical_role": role_map.get(row["musical_role_id"]) if row["musical_role_id"] else None,
                "section_id": row["section_id"],
            }
            for row in rows
        ]'''

content = content.replace(old_group_members, new_group_members)

# 4. Update update_group_member to validate role scopes
old_update_member = '''    @app.patch("/api/v1/groups/{group_id}/members/{user_sub}")
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
        return {"ok": True}'''

new_update_member = '''    @app.patch("/api/v1/groups/{group_id}/members/{user_sub}")
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
            # Validate role scopes if provided
            if body.admin_role_id is not None:
                role = conn.execute(
                    "SELECT scope FROM group_roles WHERE id = ? AND group_id = ?",
                    (body.admin_role_id, group_id),
                ).fetchone()
                if role is None:
                    raise HTTPException(status_code=400, detail="Admin role not found in this group")
                if role["scope"] != "admin":
                    raise HTTPException(status_code=400, detail="Admin role must have scope 'admin'")
            if body.musical_role_id is not None:
                role = conn.execute(
                    "SELECT scope FROM group_roles WHERE id = ? AND group_id = ?",
                    (body.musical_role_id, group_id),
                ).fetchone()
                if role is None:
                    raise HTTPException(status_code=400, detail="Musical role not found in this group")
                if role["scope"] != "musical":
                    raise HTTPException(status_code=400, detail="Musical role must have scope 'musical'")
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
                    (f"mem-{user_sub[:8]}-{int(time.time())}", group_id, "member_role_change", user_id, before_role, body.role or before_role, json.dumps(detail) if detail else None, now),
                )
        return {"ok": True}'''

content = content.replace(old_update_member, new_update_member)

# 5. Add new endpoints after group_members and before messages
# Find the end of group_members function and insert before messages
new_endpoints = '''
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
                    role_id, "", group_id, body.scope, body.code.strip(), body.name.strip(),
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
                    link_id, "", group_id, body.kind, body.label, body.url.strip(),
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

'''

# Find the end of group_members function (before messages)
content = content.replace(
    '''        ]
    @app.get("/api/v1/messages/unread-count")''',
    '''        ]
''' + new_endpoints + '''    @app.get("/api/v1/messages/unread-count")'''
)

# 6. Add activity log trigger to publish_article
old_publish = '''    @app.post("/api/v1/articles/{article_id}/publish")
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
            updated = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
        return _article_dto(conn, updated, can_edit=True, can_publish=True)'''

new_publish = '''    @app.post("/api/v1/articles/{article_id}/publish")
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
        return _article_dto(conn, updated, can_edit=True, can_publish=True)'''

content = content.replace(old_publish, new_publish)

# 7. Add activity log trigger to withdraw_article
old_withdraw = '''    @app.post("/api/v1/articles/{article_id}/withdraw")
    def withdraw_article(
        article_id: str, profile: dict[str, Any] = Depends(current_profile)
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            row = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Article not found")
            can_edit, can_publish = _article_permissions(conn, row, user_id, profile)
            if not can_edit:
                raise HTTPException(status_code=403, detail="No puedes retirar este artículo")
            conn.execute(
                "UPDATE group_articles SET status='withdrawn', updated_at=? WHERE id=?",
                (utcnow(), article_id),
            )
            updated = conn.execute("SELECT * FROM group_articles WHERE id=?", (article_id,)).fetchone()
        return _article_dto(conn, updated, can_edit=True, can_publish=can_publish)'''

new_withdraw = '''    @app.post("/api/v1/articles/{article_id}/withdraw")
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
        return _article_dto(conn, updated, can_edit=True, can_publish=can_publish)'''

content = content.replace(old_withdraw, new_withdraw)

# Write the modified content
with open("app/main.py", "w") as f:
    f.write(content)

print("All changes applied successfully!")