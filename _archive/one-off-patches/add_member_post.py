with open('app/main.py', 'r') as f:
    content = f.read()

# Add POST endpoint before GET /api/v1/groups/{group_id}/members
old = '''        return _group_dto(group, role, role == "manager")

    @app.get("/api/v1/groups/{group_id}/members")
    def group_members('''

new = '''        return _group_dto(group, role, role == "manager")

    @app.post("/api/v1/groups/{group_id}/members", status_code=201)
    def add_group_member(
        group_id: str,
        body: MemberCreateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        admin = _is_admin(profile)
        now = utcnow()
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            actor = conn.execute(
                "SELECT role FROM group_members WHERE group_id=? AND user_sub=? "
                "AND status='active'", (group_id, user_id)
            ).fetchone()
            if not admin and (actor is None or actor["role"] != "manager"):
                raise HTTPException(status_code=403, detail="Only group managers can add members")
            # Check if user already has a membership in this group
            existing = conn.execute(
                "SELECT * FROM group_members WHERE group_id=? AND user_sub=?", (group_id, body.user_sub)
            ).fetchone()
            if existing is not None:
                # Reactivate if removed
                if existing["status"] == "removed":
                    conn.execute(
                        "UPDATE group_members SET status='active', role=?, admin_role_id=?, musical_role_id=?, section_id=?, display_name=?, updated_at=?, granted_by=? "
                        "WHERE group_id=? AND user_sub=?",
                        (body.role, body.admin_role_id, body.musical_role_id, body.section_id, body.display_name, now, user_id, group_id, body.user_sub),
                    )
                else:
                    raise HTTPException(status_code=409, detail="User is already a member of this group")
            else:
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
                if body.section_id is not None:
                    section = conn.execute(
                        "SELECT 1 FROM group_sections WHERE id = ? AND group_id = ? AND active = 1",
                        (body.section_id, group_id),
                    ).fetchone()
                    if section is None:
                        raise HTTPException(status_code=400, detail="Section not found in this group")
                conn.execute(
                    "INSERT INTO group_members "
                    "(id, group_id, user_sub, role, status, display_name, joined_at, updated_at, admin_role_id, musical_role_id, section_id, granted_by) "
                    "VALUES (?,?,?,?, 'active', ?, ?, ?, ?, ?, ?, ?)",
                    (uuid.uuid4().hex, group_id, body.user_sub, body.role, body.display_name, now, now,
                     body.admin_role_id, body.musical_role_id, body.section_id, user_id),
                )
            # Activity log
            conn.execute(
                "INSERT INTO activity_log (legacy_id, group_id, event_type, actor, from_status, to_status, detail_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (f"mem-{body.user_sub[:8]}-{int(time.time())}", group_id, "member_added", user_id, None, body.role, None, now),
            )
            # Return updated member list
            rows = conn.execute(
                "SELECT user_sub, role, display_name, voice_label, section, "
                "admin_role_id, musical_role_id, section_id FROM group_members WHERE group_id = ? AND status = 'active' "
                "ORDER BY role DESC, display_name, user_sub", (group_id,)
            ).fetchall()
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
            members = [
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
            ]
        return {"ok": True, "members": members}

    @app.get("/api/v1/groups/{group_id}/members")
    def group_members('''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)

print('Added POST /api/v1/groups/{group_id}/members endpoint')