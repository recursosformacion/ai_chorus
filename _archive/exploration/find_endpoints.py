import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find all preparation_works endpoints
import re
pattern = r'@app\.(get|post|patch|delete)\(\"/api/v1/groups/\{group_id\}/preparation-works'
for m in re.finditer(pattern, content):
    start = m.start()
    # Find next @app. or end of preparation section
    next_app = content.find('@app.', start + 50)
    if next_app == -1:
        next_app = start + 5000
    print(f'--- Found at {start} ---')
    print(content[start:next_app])
    print()