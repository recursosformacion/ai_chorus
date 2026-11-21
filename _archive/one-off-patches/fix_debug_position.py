with open('app/main.py', 'r') as f:
    content = f.read()

# Fix the debug print position - move it before return
old = '''def _is_representative(profile: dict[str, Any], entity_id: str) -> bool:
    return _is_admin(profile) or any(
        membership.get("entity_id") == entity_id
        and membership.get("is_representative") is True
        for membership in _approved_memberships(profile)
    )
    print("DEBUG: base helpers done")

def _normalise_iso'''

new = '''def _is_representative(profile: dict[str, Any], entity_id: str) -> bool:
    return _is_admin(profile) or any(
        membership.get("entity_id") == entity_id
        and membership.get("is_representative") is True
        for membership in _approved_memberships(profile)
    )

print("DEBUG: base helpers done")

def _normalise_iso'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)
print('Fixed debug print position')