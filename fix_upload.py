with open('app/main.py', 'r') as f:
    content = f.read()

# Fix the upload endpoint to save files directly in folder_path, not in subfolder named after original file
old_upload = '''        now = utcnow()
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

new_upload = '''        now = utcnow()
        uploaded = []
        for i, upload in enumerate(files):
            relative = str(upload.filename or "archivo").replace("\\\\", "/")
            original = relative.split("/")[-1]
            suffix = Path(original).suffix.lower()
            data = await upload.read()
            if len(data) > cfg.max_upload_bytes:
                raise HTTPException(status_code=413, detail=f"{original}: exceeds max upload size")
            # Save file in the preparation work's folder (folder_path)
            pointer = _save_private(cfg, data, suffix, Path(folder_path))
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

with open('app/main.py', 'w') as f:
    f.write(content)

print('Fixed upload endpoint')