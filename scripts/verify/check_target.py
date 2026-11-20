import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    for table in ['groups', 'group_members', 'group_history', 'group_sections', 'group_types', 'section_templates', 'role_templates']:
        cur.execute(f'SELECT COUNT(*) as c FROM {table}')
        print(f'{table}: {cur.fetchone()["c"]}')
    cur.execute('DESCRIBE group_sections')
    for row in cur.fetchall():
        print(f'group_sections: {row["Field"]} {row["Type"]} Null={row["Null"]} Key={row["Key"]}')