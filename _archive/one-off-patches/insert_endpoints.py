with open('app/main.py', 'r') as f:
    content = f.read()

# Find the location to insert - after list_admin_activity_log and before unread-count
insert_marker = '''        return [_activity_log_dto(row) for row in rows]

    @app.get("/api/v1/messages/unread-count")'''

new_endpoints = '''        return [_activity_log_dto(row) for row in rows]


def _can_manage_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
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
    return False


def _can_view_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
    """Check if user can view preparation works in a group.
    All active members can view, plus platform admin.
    """
    admin = _is_admin(profile)
    if admin:
        return True
    member = conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_sub = ? AND status = 'active'",
        (group_id, user_id),
    ).fetchone()
    return member is not None


    @app.get("/api/v1/groups/{group_id}/preparation-works")
    def list_preparation_works(
        group_id: str,
        status: str | None = None,
        destination_type: str | None = None,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_view_preparation_work(conn, group_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Not a member of this group")
            where = ["group_id = ?"]
            params: list[Any] = [group_id]
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


    @app.post("/api/v1/groups/{group_id}/preparation-works", status_code=201)
    def create_preparation_work(
        group_id: str,
        body: PreparationWorkBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_preparation_work(conn, group_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Only group managers or musical directors can create preparation works")
            now = utcnow()
            work_id = uuid.uuid4().hex
            # Create folder path: preparation/{group_id}/{work_id}
            folder_path = f"preparation/{group_id}/{work_id}"
            conn.execute(
                "INSERT INTO preparation_works "
                "(id, group_id, title, composer, folder_path, status, destination_type, event_name, event_date, notes, created_by, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    work_id, group_id, body.title.strip(), body.composer, folder_path,
                    "preparing", body.destination_type, body.event_name, body.event_date, body.notes,
                    user_id, now, now,
                ),
            )
            row = conn.execute("SELECT * FROM preparation_works WHERE id = ?", (work_id,)).fetchone()
        return _preparation_work_dto(row)


    @app.patch("/api/v1/groups/{group_id}/preparation-works/{work_id}")
    def update_preparation_work(
        group_id: str,
        work_id: str,
        body: PreparationWorkUpdateBody,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_preparation_work(conn, group_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Only group managers or musical directors can update preparation works")
            work = conn.execute(
                "SELECT * FROM preparation_works WHERE id = ? AND group_id = ?",
                (work_id, group_id),
            ).fetchone()
            if work is None:
                raise HTTPException(status_code=404, detail="Preparation work not found")
            updates = []
            values: list[Any] = []
            for column in ("title", "composer", "destination_type", "event_name", "event_date", "notes", "status"):
                value = getattr(body, column)
                if value is not None:
                    updates.append(f"{column}=?")
                    values.append(value)
            if not updates:
                return _preparation_work_dto(work)
            values.append(utcnow())
            values.append(work_id)
            conn.execute(
                f"UPDATE preparation_works SET {', '.join(updates)}, updated_at=? WHERE id=?",
                tuple(values),
            )
            row = conn.execute("SELECT * FROM preparation_works WHERE id = ?", (work_id,)).fetchone()
        return _preparation_work_dto(row)


    @app.delete("/api/v1/groups/{group_id}/preparation-works/{work_id}")
    def delete_preparation_work(
        group_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_preparation_work(conn, group_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Only group managers or musical directors can delete preparation works")
            work = conn.execute(
                "SELECT * FROM preparation_works WHERE id = ? AND group_id = ?",
                (work_id, group_id),
            ).fetchone()
            if work is None:
                raise HTTPException(status_code=404, detail="Preparation work not found")
            conn.execute("DELETE FROM preparation_works WHERE id = ?", (work_id,))
        return {"ok": True}


    @app.post("/api/v1/groups/{group_id}/preparation-works/{work_id}/files", status_code=201)
    async def upload_preparation_files(
        group_id: str,
        work_id: str,
        files: list[UploadFile] = File(...),
        parts: str = Form(default="[]"),
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        """Upload one or more files to a preparation work.
        parts: JSON array of {part_label, purpose} for each file (optional, same length as files).
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
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_preparation_work(conn, group_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Only group managers or musical directors can upload files")
            work = conn.execute(
                "SELECT * FROM preparation_works WHERE id = ? AND group_id = ?",
                (work_id, group_id),
            ).fetchone()
            if work is None:
                raise HTTPException(status_code=404, detail="Preparation work not found")
            folder_path = work["folder_path"]

        now = utcnow()
        uploaded = []
        for i, upload in enumerate(files):
            relative = str(upload.filename or "archivo").replace("\\", "/")
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
        return {"work_id": work_id, "folder_path": folder_path, "files": uploaded}


    @app.get("/api/v1/groups/{group_id}/preparation-works/{work_id}/files")
    def list_preparation_files(
        group_id: str,
        work_id: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> list[dict[str, Any]]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_view_preparation_work(conn, group_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Not a member of this group")
            work = conn.execute(
                "SELECT folder_path FROM preparation_works WHERE id = ? AND group_id = ?",
                (work_id, group_id),
            ).fetchone()
            if work is None:
                raise HTTPException(status_code=404, detail="Preparation work not found")
            folder_path = work["folder_path"]

        # List files in the folder using storage_root
        root = Path(cfg.storage_root).resolve()
        folder = (root / folder_path).resolve()
        if root not in folder.parents and root != folder:
            raise HTTPException(status_code=403, detail="Invalid folder path")
        if not folder.exists():
            return []

        files = []
        for file_path in sorted(folder.iterdir()):
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
        return files


    @app.get("/api/v1/groups/{group_id}/preparation-works/{work_id}/files/{file_name}/download")
    def download_preparation_file(
        group_id: str,
        work_id: str,
        file_name: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> Response:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_view_preparation_work(conn, group_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Not a member of this group")
            work = conn.execute(
                "SELECT folder_path FROM preparation_works WHERE id = ? AND group_id = ?",
                (work_id, group_id),
            ).fetchone()
            if work is None:
                raise HTTPException(status_code=404, detail="Preparation work not found")
            folder_path = work["folder_path"]

        root = Path(cfg.storage_root).resolve()
        file_path = (root / folder_path / file_name).resolve()
        if root not in file_path.parents:
            raise HTTPException(status_code=403, detail="Invalid file path")
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        data = file_path.read_bytes()
        mime_type = "application/octet-stream"
        return Response(
            content=data,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'}
        )


    @app.delete("/api/v1/groups/{group_id}/preparation-works/{work_id}/files/{file_name}")
    def delete_preparation_file(
        group_id: str,
        work_id: str,
        file_name: str,
        profile: dict[str, Any] = Depends(current_profile),
    ) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        with _connect(cfg) as conn:
            group = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            if not _can_manage_preparation_work(conn, group_id, user_id, profile):
                raise HTTPException(status_code=403, detail="Only group managers or musical directors can delete files")
            work = conn.execute(
                "SELECT folder_path FROM preparation_works WHERE id = ? AND group_id = ?",
                (work_id, group_id),
            ).fetchone()
            if work is None:
                raise HTTPException(status_code=404, detail="Preparation work not found")
            folder_path = work["folder_path"]

        root = Path(cfg.storage_root).resolve()
        file_path = (root / folder_path / file_name).resolve()
        if root not in file_path.parents:
            raise HTTPException(status_code=403, detail="Invalid file path")
        if file_path.is_file():
            file_path.unlink()
        return {"ok": True}


    @app.get("/api/v1/messages/unread-count")'''

content = content.replace(insert_marker, new_endpoints)

with open('app/main.py', 'w') as f:
    f.write(content)
print("Inserted preparation_works endpoints")