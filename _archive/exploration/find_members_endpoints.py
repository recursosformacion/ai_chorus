import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find group members endpoints
import re
pattern = r'@app\.(get|post|patch|delete)\(\"/api/v1/groups/\{group_id\}/members'
for m in re.finditer(pattern, content):
    idx = m.start()
    next_app = content.find('@app.', idx + 50)
    if next_app == -1:
        next_app = idx + 3000
    print(content[idx:next_app])
    print('---')