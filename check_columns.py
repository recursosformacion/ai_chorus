import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

from app.db import connect as db_connect
from app.config import Settings

settings = Settings.load()
with db_connect(settings) as conn:
    # Check current group_members columns
    rows = conn.execute('DESCRIBE group_members').fetchall()
    for row in rows:
        print(dict(row))