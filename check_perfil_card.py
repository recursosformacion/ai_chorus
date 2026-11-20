import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('web/index.html', 'rb') as f:
    content = f.read().decode('utf-8', errors='replace')

# Find the profile card
idx = content.find('id="perfil"')
if idx >= 0:
    print(content[idx:idx+3000])