import pymysql
import sqlparse

conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    with open('migrations/mysql/021_group_history.sql', encoding='utf-8') as f:
        sql = f.read()
    statements = sqlparse.split(sql)
    for stmt in statements:
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    print('Migration 021 executed')

    # Verify columns
    cur.execute('DESCRIBE group_history')
    for row in cur.fetchall():
        print(f'Column: {row["Field"]}: {row["Type"]} Null={row["Null"]} Key={row["Key"]}')

    # Verify PK
    cur.execute('SHOW KEYS FROM group_history WHERE Key_name = "PRIMARY"')
    for row in cur.fetchall():
        print(f'PK: {row["Column_name"]}')

    # Verify FK
    cur.execute('''
        SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = "group_history"
          AND REFERENCED_TABLE_NAME IS NOT NULL
    ''')
    for row in cur.fetchall():
        print(f'FK: {row}')

    # Verify indexes
    cur.execute('SHOW INDEX FROM group_history')
    for row in cur.fetchall():
        print(f'Index: {row["Key_name"]} on {row["Column_name"]}')