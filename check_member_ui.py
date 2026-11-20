import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('web/app.js', 'rb') as f:
    content = f.read().decode('utf-8', errors='replace')

# Find member management UI
import re
for m in re.finditer(r'(members|miembros|gesti.n de miembros|administraci.n de miembros)', content, re.IGNORECASE):
    idx = m.start()
    print(f'At {idx}: {content[max(0,idx-100):idx+200]}')
    print('---')