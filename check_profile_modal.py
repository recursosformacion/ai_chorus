import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('web/app.js', 'rb') as f:
    content = f.read().decode('utf-8', errors='replace')

# Find profile modal or form
import re
for m in re.finditer(r'(profile-modal|profile-form|editar-perfil|mi-perfil|my-profile)', content, re.IGNORECASE):
    idx = m.start()
    print(f'At {idx}: {content[max(0,idx-50):idx+300]}')
    print('---')