import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find the first preparation_works endpoint
idx = content.find('@app.get("/api/v1/groups/{group_id}/preparation-works")')
if idx >= 0:
    print(content[idx:idx+3000])