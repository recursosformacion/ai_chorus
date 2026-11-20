import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find the self-update endpoint
idx = content.find('@app.patch("/api/v1/groups/{group_id}/members/me")')
if idx >= 0:
    print(f'Found at {idx}')
else:
    print('NOT FOUND')
    
# Find the group_members function area
idx = content.find('def group_members(')
if idx >= 0:
    print(f'group_members at {idx}')
    # Print area around it
    print(content[max(0,idx-200):idx+1000])