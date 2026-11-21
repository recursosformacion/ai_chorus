import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from app.config import Settings
from app.db import connect as db_connect

settings = Settings.load()
print("Settings loaded:", settings.database_url[:50])

conn = db_connect(settings)
try:
    row = conn.execute("SELECT 1").fetchone()
    print("DB connection OK:", row)
finally:
    conn.close()

# Test initialise_database
from app.main import initialise_database
try:
    initialise_database(settings)
    print("initialise_database OK")
except Exception as e:
    print("initialise_database ERROR:", e)
    import traceback
    traceback.print_exc()