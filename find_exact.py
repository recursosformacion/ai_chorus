import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find the exact text to replace
idx = content.find('return _group_dto(group, role, role == "manager")')
if idx >= 0:
    print(f'Found at {idx}')
    print(repr(content[idx:idx+200]))