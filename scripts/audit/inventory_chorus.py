import os
os.environ['CHORUS_DATABASE_URL'] = 'mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test'
import pymysql

conn = pymysql.connect(
    host='127.0.0.1',
    port=3306,
    user='osap2027_test',
    password='testpass',
    database='osap_chorus_test',
    cursorclass=pymysql.cursors.DictCursor
)

cur = conn.cursor()
cur.execute('SHOW TABLES')
tables = cur.fetchall()
print('=== Tablas en osap_chorus_test ===')
for t in tables:
    print(t)

# Para cada tabla, mostrar estructura
for t in tables:
    tname = list(t.values())[0]
    print(f'\n=== {tname} ===')
    cur.execute(f'DESCRIBE {tname}')
    for c in cur.fetchall():
        print(f"  {c['Field']}: {c['Type']} {'NOT NULL' if c['Null']=='NO' else 'NULL'} {c['Key']} {c['Default']}")

conn.close()