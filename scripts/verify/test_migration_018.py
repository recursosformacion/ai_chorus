import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    with open('migrations/mysql/018_group_types.sql', encoding='utf-8') as f:
        sql = f.read()
    for stmt in sql.split(';'):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    print('Migration 018 executed')
    cur.execute('DESCRIBE group_types')
    for row in cur.fetchall():
        print(row)