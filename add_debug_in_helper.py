with open('app/main.py', 'r') as f:
    content = f.read()

# Add debug print at the start of _can_manage_preparation_work
old = '''def _can_manage_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
    """Check if user can manage preparation works in a group.
    Returns True for:
    - Platform admin
    - Group manager (role='manager')
    - User with musical_role_id assigned that has scope='musical' in group_roles
    """
    admin = _is_admin(profile)'''

new = '''def _can_manage_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:
    print("DEBUG: _can_manage_preparation_work defined")
    """Check if user can manage preparation works in a group.
    Returns True for:
    - Platform admin
    - Group manager (role='manager')
    - User with musical_role_id assigned that has scope='musical' in group_roles
    """
    admin = _is_admin(profile)'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)
print('Added debug in helper')