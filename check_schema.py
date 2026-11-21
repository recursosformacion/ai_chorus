import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'

from app.config import Settings
from app.db import connect as db_connect

settings = Settings.load()
conn = db_connect(settings)

# Check columns
print("=== preparation_works columns ===")
rows = conn.execute("DESCRIBE preparation_works").fetchall()
for row in rows:
    print(f"  {row['Field']} ({row['Type']}) - Null: {row['Null']}, Default: {row['Default']}")

# Check foreign keys
print("\n=== preparation_works foreign keys ===")
rows = conn.execute("""
    SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = 'osap_chorus_test'
      AND TABLE_NAME = 'preparation_works'
      AND REFERENCED_TABLE_NAME IS NOT NULL
""").fetchall()
for row in rows:
    print(f"  {row['CONSTRAINT_NAME']}: {row['COLUMN_NAME']} -> {row['REFERENCED_TABLE_NAME']}.{row['REFERENCED_COLUMN_NAME']}")

# Check spaces table
print("\n=== spaces table ===")
rows = conn.execute("DESCRIBE spaces").fetchall()
for row in rows:
    print(f"  {row['Field']} ({row['Type']}) - Null: {row['Null']}")

conn.close()