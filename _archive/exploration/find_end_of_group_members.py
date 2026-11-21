import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find the group_members GET endpoint (the one that lists members)
# It should be around line 90412 based on earlier search
idx = content.find('@app.get("/api/v1/groups/{group_id}/members")\n    def group_members(')
if idx >= 0:
    print(f'Found at {idx}')
    # Find the end of this function
    # Look for the next @app. or def at the same indentation level
    func_start = idx
    lines = content[func_start:].split('\n')
    indent = 4  # function body indent
    for i, line in enumerate(lines[1:], 1):  # skip the @app.get line
        stripped = line.lstrip()
        if stripped.startswith('@app.') or (stripped.startswith('def ') and len(line) - len(stripped) == 4):
            print(f'Next function at relative line {i}: {stripped[:50]}')
            break
        if i > 200:
            print('Reached 200 lines without finding next function')
            break