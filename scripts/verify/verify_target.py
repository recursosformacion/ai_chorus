import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT COUNT(*) as c FROM group_types')
    print(f'Count: {cur.fetchone()["c"]}')
    
    cur.execute('''
        SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = "group_types"
          AND REFERENCED_TABLE_NAME IS NOT NULL
    ''')
    for row in cur.fetchall():
        print(f'FK: {row}')
    
    cur.execute('SHOW INDEX FROM group_types')
    for row in cur.fetchall():
        print(f'Index: {row["Key_name"]} on {row["Column_name"]}')
    
    cur.execute('SELECT * FROM group_types WHERE code IN ("vocal", "coral", "bandas")')
    for row in cur.fetchall():
        print(f'Record: {row}')