import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SHOW FULL COLUMNS FROM groups WHERE Field = "id"')
    for row in cur.fetchall():
        print(f'Field: {row["Field"]}')
        print(f'Type: {row["Type"]}')
        print(f'Collation: {row["Collation"]}')
        print(f'Null: {row["Null"]}')
        print(f'Key: {row["Key"]}')