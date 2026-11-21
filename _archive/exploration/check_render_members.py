import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('web/app.js', 'rb') as f:
    content = f.read().decode('utf-8', errors='replace')

# Find renderGroupMembers function
idx = content.find('function renderGroupMembers()')
if idx >= 0:
    print(content[idx:idx+3000])