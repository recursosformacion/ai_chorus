with open('web/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the setActiveGroup function where renderGroupCard is called
insert_idx = None
for i, line in enumerate(lines):
    if 'renderGroupCard();' in line and i > 230 and i < 240:
        insert_idx = i + 1
        break

if insert_idx is None:
    print("Could not find insertion point")
    exit(1)

new_code = [
    '    void loadPreparationWorks();\n',
]

lines = lines[:insert_idx] + new_code + lines[insert_idx:]

with open('web/app.js', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Added loadPreparationWorks call')