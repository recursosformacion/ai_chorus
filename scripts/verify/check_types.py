import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SHOW FULL COLUMNS FROM group_types WHERE Field = "code"')
    for row in cur.fetchall():
        print(f'group_types.code: {row["Type"]} Collation={row["Collation"]}')