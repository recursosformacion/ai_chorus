import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find both PATCH endpoints
import re
for m in re.finditer(r'@app\.patch\("/api/v1/groups/\{group_id\}/members', content):
    idx = m.start()
    print(f'At {idx}: {content[idx:idx+100]}')
    print('---')