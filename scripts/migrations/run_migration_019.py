import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    with open('migrations/mysql/019_groups_type_code.sql', encoding='utf-8') as f:
        sql = f.read()
    for stmt in sql.split(';'):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    print('Migration 019 executed')
    
    # Verify columns
    cur.execute('DESCRIBE groups')
    for row in cur.fetchall():
        if row['Field'] in ('type_code', 'join_code_expires_at'):
            print(f'Column: {row["Field"]}: {row["Type"]} Null={row["Null"]}')
    
    # Verify FK
    cur.execute('''
        SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = "groups"
          AND REFERENCED_TABLE_NAME IS NOT NULL
    ''')
    for row in cur.fetchall():
        print(f'FK: {row}')
    
    # Verify index
    cur.execute('SHOW INDEX FROM groups WHERE Key_name = "idx_groups_type_code"')
    for row in cur.fetchall():
        print(f'Index: {row["Key_name"]} on {row["Column_name"]}')
    
    # Verify groups preserved, type_code NULL
    cur.execute('SELECT COUNT(*) as c FROM groups')
    print(f'Groups count: {cur.fetchone()["c"]}')
    cur.execute('SELECT COUNT(*) as c FROM groups WHERE type_code IS NOT NULL')
    print(f'Groups with type_code set: {cur.fetchone()["c"]}')