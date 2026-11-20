import pymysql
import sqlparse

conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    with open('migrations/mysql/022_group_articles_scope.sql', encoding='utf-8') as f:
        sql = f.read()
    statements = sqlparse.split(sql)
    for stmt in statements:
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    print('Migration 022 executed')

    # Verify column
    cur.execute('DESCRIBE group_articles')
    for row in cur.fetchall():
        if row['Field'] == 'scope':
            print(f'Column: {row["Field"]}: {row["Type"]} Null={row["Null"]} Key={row["Key"]} Default={row["Default"]}')

    # Verify check constraint
    cur.execute('''
        SELECT CONSTRAINT_NAME FROM information_schema.CHECK_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_NAME = "ck_group_articles_scope"
    ''')
    for row in cur.fetchall():
        print(f'Check constraint: {row}')

    # Verify index
    cur.execute('SHOW INDEX FROM group_articles WHERE Key_name = "idx_group_articles_scope_published"')
    for row in cur.fetchall():
        print(f'Index: {row["Key_name"]} on {row["Column_name"]}')