with open('app/main.py', 'r') as f:
    content = f.read()

# Add debug print after each major section
# First, let's add a print after the helper functions
old = '''def _can_view_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
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


    @app.get("/api/v1/groups/{group_id}/preparation-works")'''

new = '''def _can_view_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
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

    print("DEBUG: helpers done, starting endpoints")


    @app.get("/api/v1/groups/{group_id}/preparation-works")'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)
print('Added debug print after helpers')