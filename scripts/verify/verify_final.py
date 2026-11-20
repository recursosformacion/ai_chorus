import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    for table in ['groups', 'group_sections', 'group_members', 'group_history']:
        cur.execute(f'SELECT COUNT(*) as c FROM {table}')
        print(f'{table}: {cur.fetchone()["c"]}')
    print()
    cur.execute('SELECT * FROM group_history')
    for row in cur.fetchall():
        print(row)