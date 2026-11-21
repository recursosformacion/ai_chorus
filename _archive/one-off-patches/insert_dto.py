with open('app/main.py', 'r') as f:
    lines = f.readlines()

# Insert after line 639 (index 639) - after the closing brace of _activity_log_dto
new_lines = [
    '\n',
    'def _preparation_work_dto(row: dict[str, Any]) -> dict[str, Any]:\n',
    '    return {\n',
    '        "id": row["id"],\n',
    '        "group_id": row["group_id"],\n',
    '        "title": row["title"],\n',
    '        "composer": row["composer"],\n',
    '        "folder_path": row["folder_path"],\n',
    '        "status": row["status"],\n',
    '        "destination_type": row["destination_type"],\n',
    '        "event_name": row["event_name"],\n',
    '        "event_date": row["event_date"],\n',
    '        "notes": row["notes"],\n',
    '        "created_by": row["created_by"],\n',
    '        "created_at": row["created_at"],\n',
    '        "updated_at": row["updated_at"],\n',
    '    }\n',
    '\n',
]

# Insert at line 640 (after the closing brace of _activity_log_dto)
lines = lines[:640] + new_lines + lines[640:]

with open('app/main.py', 'w') as f:
    f.writelines(lines)
print('Inserted _preparation_work_dto')