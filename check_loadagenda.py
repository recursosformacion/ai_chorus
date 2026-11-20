import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('web/app.js', 'rb') as f:
    content = f.read().decode('utf-8', errors='replace')

# Find loadAgenda function
idx = content.find('async function loadAgenda')
if idx >= 0:
    print(content[idx:idx+500])
else:
    print('Not found')

print('---')

# Also find where agendaState.groups is set
for m in re.finditer(r'agendaState\.groups\s*=', content):
    idx = m.start()
    print(f'At {idx}: {content[max(0,idx-50):idx+100]}')
    print('---')