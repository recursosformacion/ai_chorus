import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find the first preparation_works endpoint
idx = content.find('@app.get("/api/v1/groups/{group_id}/preparation-works")')
if idx >= 0:
    # Check what function it's in by looking backwards for 'def '
    before = content[:idx]
    last_def = before.rfind('def ')
    print(f'Last def before endpoint: {content[last_def:last_def+100]}')
    print(f'Endpoint at: {idx}')
    
    # Also check if create_app ends before this
    create_app_end = content.find('def _can_manage_preparation_work')
    print(f'create_app ends at: {create_app_end}')
    print(f'Is endpoint after create_app? {idx > create_app_end}')