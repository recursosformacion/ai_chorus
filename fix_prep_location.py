with open('app/main.py', 'r') as f:
    content = f.read()

# Find the preparation_works section (module level)
prep_start = content.find('def _can_manage_preparation_work(conn, group_id: str, user_id: str, profile: dict[str, Any]) -> bool:')
prep_end = content.find('\napp = create_app()')

print(f"Prep section: {prep_start} to {prep_end}")

# Extract the section
prep_section = content[prep_start:prep_end]

# Remove the trailing "DEBUG: about to return app" and "return app" from prep section
# Find the last occurrence of "DEBUG: about to return app" in prep_section
last_debug = prep_section.rfind('DEBUG: about to return app')
if last_debug >= 0:
    # Keep everything before this
    prep_section_clean = prep_section[:last_debug].rstrip()
    print("Cleaned prep section, removed trailing return app")
else:
    prep_section_clean = prep_section
    print("No trailing return app found in prep section")

# Find where to insert inside create_app (before "DEBUG: about to return app")
insert_point = content.find('    print("DEBUG: about to return app")')
print(f"Insert point: {insert_point}")

# Now reconstruct the file:
# 1. Content before prep section (up to prep_start)
# 2. Content from prep_start to insert_point (inside create_app)
# 3. Insert prep_section_clean
# 4. Content from insert_point onwards (the original return app)
# 5. Content after prep_end (app = create_app())

before_prep = content[:prep_start]
after_prep = content[prep_end:]

# The content between prep_start and insert_point is the end of create_app
# We need to insert prep_section_clean before insert_point
middle = content[prep_start:insert_point]

new_content = before_prep + middle + '\n\n' + prep_section_clean + '\n\n' + content[insert_point:] + after_prep

with open('app/main.py', 'w') as f:
    f.write(new_content)

print('File restructured successfully')