import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find the group_members GET endpoint to add POST before it
idx = content.find('@app.get("/api/v1/groups/{group_id}/members")')
if idx >= 0:
    print(f"Found at {idx}")
    # Show context before it
    print(content[max(0,idx-200):idx+100])