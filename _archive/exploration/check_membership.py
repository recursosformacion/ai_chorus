import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

from app.db import connect as db_connect
from app.config import Settings

settings = Settings.load()
with db_connect(settings) as conn:
    # Check group_members with all data
    rows = conn.execute('SELECT * FROM group_members').fetchall()
    for row in rows:
        d = dict(row)
        print(f"user_sub: {d['user_sub']}, group_id: {d['group_id']}, role: {d['role']}, status: {d['status']}, section_id: {d['section_id']}, admin_role_id: {d['admin_role_id']}, musical_role_id: {d['musical_role_id']}")
    
    print()
    # Check group_sections
    rows = conn.execute('SELECT * FROM group_sections').fetchall()
    for row in rows:
        print(f"section: {dict(row)}")
    
    print()
    # Check group_roles
    rows = conn.execute('SELECT * FROM group_roles').fetchall()
    for row in rows:
        print(f"role: {dict(row)}")