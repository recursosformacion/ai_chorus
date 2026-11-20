import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find the exact text between group_members function and group_roles CRUD
idx = content.find('# ===== group_roles CRUD =====')
if idx >= 0:
    print(content[max(0,idx-500):idx+100])