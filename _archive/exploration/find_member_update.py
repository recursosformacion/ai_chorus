import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

with open('app/main.py', 'r') as f:
    content = f.read()

# Find MemberUpdateBody to add MemberCreateBody after it
idx = content.find('class MemberUpdateBody')
if idx >= 0:
    print(content[idx:idx+500])