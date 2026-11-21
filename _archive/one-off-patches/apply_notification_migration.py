import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

from app.db import connect as db_connect, _execute_sql_script
from app.config import Settings

settings = Settings.load()
with db_connect(settings) as conn:
    script = open('migrations/mysql/036_add_notification_preferences.sql').read()
    _execute_sql_script(conn, script, is_mysql=True)
    conn.commit()
    
    # Register migration
    from app.utils import utcnow
    conn.execute(
        "INSERT INTO chorus_schema_migrations (name, applied_at) VALUES (?, ?)",
        ("036_add_notification_preferences.sql", utcnow())
    )
    conn.commit()
    print("Migration applied successfully")
    
    # Verify
    rows = conn.execute('DESCRIBE group_members').fetchall()
    for row in rows:
        if 'notify' in row['Field']:
            print(dict(row))