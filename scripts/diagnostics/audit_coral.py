import pymysql

conn = pymysql.connect(
    host='127.0.0.1',
    port=3306,
    user='osap2027',
    password='2027osapdb',
    database='osap_api',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

print("=== amigos_coral_attributes - TODOS LOS REGISTROS ===")
with conn.cursor() as cur:
    cur.execute("SELECT * FROM amigos_coral_attributes")
    for row in cur.fetchall():
        print(row)

print("\n=== amigos_coral_details - TODOS LOS REGISTROS ===")
with conn.cursor() as cur:
    cur.execute("SELECT * FROM amigos_coral_details")
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")
        print("---")

print("\n=== Chorus groups (osap_chorus) ===")
conn2 = pymysql.connect(
    host='127.0.0.1',
    port=3306,
    user='osap2027',
    password='2027osapdb',
    database='osap_chorus',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)
with conn2.cursor() as cur:
    cur.execute("SELECT * FROM groups")
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")
        print("---")

conn.close()
conn2.close()