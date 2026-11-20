import pymysql

conn = pymysql.connect(
    host='127.0.0.1',
    port=3306,
    user='osap2027',
    password='2027osapdb',
    database='osap_api',
    cursorclass=pymysql.cursors.DictCursor
)

cur = conn.cursor()
cur.execute('SHOW TABLES LIKE "amigos_%%"')
tables = cur.fetchall()
print('=== Tablas amigos_* en osap_api ===')
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