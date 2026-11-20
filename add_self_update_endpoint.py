with open('app/main.py', 'r') as f:
    content = f.read()

# Add self-update endpoint after group_members GET and before group_roles CRUD
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

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)

print('Added self-update endpoint')