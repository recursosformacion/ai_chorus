import pymysql
import sqlparse

conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    with open('migrations/mysql/020_group_members_granted_by.sql', encoding='utf-8') as f:
        sql = f.read()
    # Parse statements properly with sqlparse
    statements = sqlparse.split(sql)
    for stmt in statements:
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    print('Migration 020 executed')
    
    # Verify columns
    cur.execute('DESCRIBE group_members')
    for row in cur.fetchall():
        if row['Field'] in ('granted_by', 'joined_at', 'section', 'section_id'):
            print(f'Column: {row["Field"]}: {row["Type"]} Null={row["Null"]} Key={row["Key"]}')
    
    # Verify index
    cur.execute('SHOW INDEX FROM group_members WHERE Key_name = "idx_group_members_granted_by"')
    for row in cur.fetchall():
        print(f'Index: {row["Key_name"]} on {row["Column_name"]}')
    
    # Verify members preserved
    cur.execute('SELECT COUNT(*) as c FROM group_members')
    print(f'Members count: {cur.fetchone()["c"]}')
    cur.execute('SELECT COUNT(*) as c FROM group_members WHERE granted_by IS NOT NULL')
    print(f'Members with granted_by set: {cur.fetchone()["c"]}')