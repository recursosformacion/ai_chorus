with open('app/main.py', 'r') as f:
    content = f.read()

# Fix 1: Update endpoint should handle null values for event_name and event_date
old = '''            for column in ("title", "composer", "destination_type", "event_name", "event_date", "notes", "status"):
                value = getattr(body, column)
                if value is not None:
                    updates.append(f"{column}=?")
                    values.append(value)'''

new = '''            for column in ("title", "composer", "destination_type", "event_name", "event_date", "notes", "status"):
                value = getattr(body, column)
                # Allow explicit None for event_name and event_date to clear them
                if value is not None or column in ("event_name", "event_date"):
                    updates.append(f"{column}=?")
                    values.append(value)'''

content = content.replace(old, new)

# Fix 2: File upload should save files to the correct folder path
# The upload_preparation_files function saves files with _save_private but doesn't put them in the folder_path
# Need to modify to save files in the correct subfolder
old_upload = '''        now = utcnow()
        uploaded = []
        for i, upload in enumerate(files):
            relative = str(upload.filename or "archivo").replace("\\\\", "/")
            original = relative.split("/")[-1]
            suffix = Path(original).suffix.lower()
            data = await upload.read()
            if len(data) > cfg.max_upload_bytes:
                raise HTTPException(status_code=413, detail=f"{original}: exceeds max upload size")
            pointer = _save_private(cfg, data, suffix)
            part_info = parts_list[i] if i < len(parts_list) else {}
            file_id = uuid.uuid4().hex
            # Store file metadata in a simple way - we could extend with a preparation_files table later
            # For now, store as part of the folder structure with metadata in filename or separate tracking
            # We'll use the existing storage infrastructure
            uploaded.append({
                "id": file_id,
                "original_name": original,
                "storage_pointer": pointer,
                "mime_type": upload.content_type or "",
                "size_bytes": len(data),
                "part_label": part_info.get("part_label"),
                "purpose": part_info.get("purpose"),
            })
        return {"work_id": work_id, "folder_path": folder_path, "files": uploaded}'''

new_upload = '''        now = utcnow()
        uploaded = []
        for i, upload in enumerate(files):
            relative = str(upload.filename or "archivo").replace("\\\\", "/")
            original = relative.split("/")[-1]
            suffix = Path(original).suffix.lower()
            data = await upload.read()
            if len(data) > cfg.max_upload_bytes:
                raise HTTPException(status_code=413, detail=f"{original}: exceeds max upload size")
            # Save file in the preparation work's folder
            folder_for_file = Path(folder_path) / original
            # Use _save_private with the folder path
            pointer = _save_private(cfg, data, suffix, folder_for_file)
            part_info = parts_list[i] if i < len(parts_list) else {}
            file_id = uuid.uuid4().hex
            uploaded.append({
                "id": file_id,
                "original_name": original,
                "storage_pointer": pointer,
                "mime_type": upload.content_type or "",
                "size_bytes": len(data),
                "part_label": part_info.get("part_label"),
                "purpose": part_info.get("purpose"),
            })
        return {"work_id": work_id, "folder_path": folder_path, "files": uploaded}'''

content = content.replace(old_upload, new_upload)

# Fix 3: Permission check should only allow specific director roles, not any musical role
# Change _can_manage_preparation_work to check for specific role codes
old_perm = '''    def _can_manage_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
        """Check if user can manage preparation works in a group.
        Returns True for:
        - Platform admin
        - Group manager (role='manager')
        - User with musical_role_id assigned that has scope='musical' in group_roles
        """
        admin = _is_admin(profile)
        if admin:
            return True
        member = conn.execute(
            "SELECT role, musical_role_id FROM group_members "
            "WHERE group_id = ? AND user_sub = ? AND status = 'active'",
            (group_id, user_id),
        ).fetchone()
        if member is None:
            return False
        if member["role"] == "manager":
            return True
        # Check if user has a musical_role_id that points to a role with scope='musical'
        musical_role_id = member["musical_role_id"]
        if musical_role_id:
            role = conn.execute(
                "SELECT scope FROM group_roles WHERE id = ? AND group_id = ?",
                (musical_role_id, group_id),
            ).fetchone()
            if role and role["scope"] == "musical":
                return True
        return False'''

new_perm = '''    def _can_manage_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
        """Check if user can manage preparation works in a group.
        Returns True for:
        - Platform admin
        - Group manager (role='manager')
        - User with musical_role_id assigned that has code='director' or name containing 'director' (case-insensitive)
        """
        admin = _is_admin(profile)
        if admin:
            return True
        member = conn.execute(
            "SELECT role, musical_role_id FROM group_members "
            "WHERE group_id = ? AND user_sub = ? AND status = 'active'",
            (group_id, user_id),
        ).fetchone()
        if member is None:
            return False
        if member["role"] == "manager":
            return True
        # Check if user has a musical_role_id that points to a director role
        musical_role_id = member["musical_role_id"]
        if musical_role_id:
            role = conn.execute(
                "SELECT scope, code, name FROM group_roles WHERE id = ? AND group_id = ?",
                (musical_role_id, group_id),
            ).fetchone()
            if role and role["scope"] == "musical":
                code = (role["code"] or "").lower()
                name = (role["name"] or "").lower()
                if code == "director" or "director" in name:
                    return True
        return False'''

content = content.replace(old_perm, new_perm)

# Fix 4: Add GET endpoint for single preparation work
# Add after list_preparation_works endpoint
old_get_single = '''    @app.get("/api/v1/groups/{group_id}/preparation-works")
    def list_preparation_works('''

new_get_single = '''    @app.get("/api/v1/groups/{group_id}/preparation-works/{work_id}")
    def get_preparation_work(
        group_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_view_preparation_work(conn, group_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Not a member of this group")
            work = conn.execute(
                "SELECT * FROM preparation_works WHERE id = ? AND group_id = ?",
                (work_id, group_id),
            ).fetchone()
            if work is None:
                raise HTTPException(status_code=404, detail="Preparation work not found")
        return _preparation_work_dto(work)

    @app.get("/api/v1/groups/{group_id}/preparation-works")
    def list_preparation_works('''

content = content.replace(old_get_single, new_get_single)

with open('app/main.py', 'w') as f:
    f.write(content)

print('Applied fixes')