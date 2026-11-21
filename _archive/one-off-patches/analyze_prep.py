with open('app/main.py', 'r') as f:
    content = f.read()

# Find the preparation_works section (module level)
prep_start = content.find('def _can_manage_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:')
# Find the end - next module-level def or app = create_app()
prep_end = content.find('\napp = create_app()')
if prep_end == -1:
    prep_end = content.find('\nif __name__ == "__main__":')
if prep_end == -1:
    prep_end = len(content)

print(f"Prep section: {prep_start} to {prep_end}")

# Extract the section
prep_section = content[prep_start:prep_end]
print(f"Length: {len(prep_section)}")

# Find where to insert inside create_app (before "DEBUG: about to return app")
insert_point = content.find('    print("DEBUG: about to return app")')
print(f"Insert point: {insert_point}")

# Verify the prep section ends with the last endpoint
print("Last 200 chars of prep section:")
print(prep_section[-200:])