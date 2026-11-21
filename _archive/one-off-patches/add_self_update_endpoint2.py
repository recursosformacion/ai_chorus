with open('app/main.py', 'r') as f:
    content = f.read()

# Find the exact text to replace - between group_members GET and group_roles CRUD
old = '''        ]
    
    # ===== group_roles CRUD ====='''

new = '''        ]
    
    @app.patch("/api/v1/groups/{group_id}/members/me")
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
                (f"mem-{user_id[:8]}-{int(time.time())}", group_id, "member_self_update", user_id, None, None, None, now),
            )
            updated = conn.execute(
                "SELECT * FROM group_members WHERE group_id = ? AND user_sub = ?", (group_id, user_id)
            ).fetchone()
        return dict(updated)

    # ===== group_roles CRUD ====='''

if old in content:
    content = content.replace(old, new)
    with open('app/main.py', 'w') as f:
        f.write(content)
    print('Replaced successfully')
else:
    print('Pattern not found, trying alternative...')
    # Try with different whitespace
    import re
    content = re.sub(r'\]\s*\n\s*# ===== group_roles CRUD =====', 
                     ']\n\n    @app.patch("/api/v1/groups/{group_id}/members/me")\n    def update_own_membership(\n        group_id: str,\n        body: MemberSelfUpdateBody,\n        profile: dict[str, Any] = Depends(current_profile),\n    ) -> dict[str, Any]:\n        """Allow a user to update their own membership profile (voice, section, notifications)."""\n        user_id = str(profile["user_id"])\n        now = utcnow()\n        with _connect(cfg) as conn:\n            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()\n            if group is None:\n                raise HTTPException(status_code=404, detail="Group not found")\n            member = conn.execute(\n                "SELECT * FROM group_members WHERE group_id = ? AND user_sub = ? AND status = \'active\'",\n                (group_id, user_id),\n            ).fetchone()\n            if member is None:\n                raise HTTPException(status_code=403, detail="Not an active member of this group")\n            # Validate section_id if provided\n            if body.section_id is not None:\n                section = conn.execute(\n                    "SELECT 1 FROM group_sections WHERE id = ? AND group_id = ? AND active = 1",\n                    (body.section_id, group_id),\n                ).fetchone()\n                if section is None:\n                    raise HTTPException(status_code=400, detail="Section not found in this group")\n            updates = []\n            values: list[Any] = []\n            for column in ("voice_code", "voice_label", "section_id", "notify_email", "notify_osap", "notify_whatsapp", "notify_sms"):\n                value = getattr(body, column)\n                if value is not None:\n                    updates.append(f"{column}=?")\n                    values.append(value)\n            if not updates:\n                return {"ok": True, "message": "No changes"}\n            values.append(now)\n            values.extend([group_id, user_id])\n            conn.execute(\n                f"UPDATE group_members SET {', '.join(updates)}, updated_at=? WHERE group_id=? AND user_sub=?",\n                tuple(values),\n            )\n            # Activity log\n            conn.execute(\n                "INSERT INTO activity_log (legacy_id, group_id, event_type, actor, from_status, to_status, detail_json, created_at) "\n                "VALUES (?,?,?,?,?,?,?,?)",\n                (f"mem-{user_id[:8]}-{int(time.time())}", group_id, "member_self_update", user_id, None, None, None, now),\n            )\n            updated = conn.execute(\n                "SELECT * FROM group_members WHERE group_id = ? AND user_sub = ?", (group_id, user_id)\n            ).fetchone()\n        return dict(updated)\n\n    # ===== group_roles CRUD =====', content)
    with open('app/main.py', 'w') as f:
        f.write(content)
    print('Replaced with regex')