import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find the group_members GET endpoint
idx = content.find('@app.get("/api/v1/groups/{group_id}/members")\n    def group_members(')
if idx >= 0:
    # Find the end of this function - look for return statement followed by blank line and @app.
    search_area = content[idx:idx+2000]
    lines = search_area.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == 'return [' and i > 10:
            print(f'Line {i}: {line.strip()}')
        if i > 10 and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
            if i > 20:
                print(f'Possible end at line {i}: {line[:50]}')
                break
    print('---')
    # Print last 50 lines of the function
    for i in range(max(0, len(lines)-60), len(lines)):
        print(f'{i}: {lines[i]}')