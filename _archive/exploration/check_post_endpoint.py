import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Check if the POST endpoint was added
idx = content.find('@app.post("/api/v1/groups/{group_id}/members"')
if idx >= 0:
    print('POST endpoint found at:', idx)
    print(content[idx:idx+500])
else:
    print('POST endpoint NOT FOUND')