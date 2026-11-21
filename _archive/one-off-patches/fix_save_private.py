with open('app/main.py', 'r') as f:
    content = f.read()

# Update _save_private to accept optional subfolder
old_save = '''def _save_private(settings: Settings, data: bytes, suffix: str) -> str:
    root = Path(settings.storage_root).resolve()
    (root / "objects").mkdir(parents=True, exist_ok=True)
    object_id = uuid.uuid4().hex
    target = root / "objects" / f"{object_id}{suffix}"
    target.write_bytes(data)
    return f"objects/{object_id}{suffix}"'''

new_save = '''def _save_private(settings: Settings, data: bytes, suffix: str, subfolder: Path | None = None) -> str:
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
        return f"objects/{object_id}{suffix}"'''

content = content.replace(old_save, new_save)

with open('app/main.py', 'w') as f:
    f.write(content)

print('Updated _save_private')