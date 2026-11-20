import pymysql
import sqlparse

conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    with open('migrations/mysql/023_section_templates.sql', encoding='utf-8') as f:
        sql = f.read()
    statements = sqlparse.split(sql)
    for stmt in statements:
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    print('Migration 023 executed')

    # Verify columns
    cur.execute('DESCRIBE section_templates')
    for row in cur.fetchall():
        print(f'Column: {row["Field"]}: {row["Type"]} Null={row["Null"]} Key={row["Key"]} Default={row["Default"]}')

    # Verify PK
    cur.execute('SHOW KEYS FROM section_templates WHERE Key_name = "PRIMARY"')
    for row in cur.fetchall():
        print(f'PK: {row["Column_name"]}')

    # Verify unique
    cur.execute('SHOW KEYS FROM section_templates WHERE Key_name = "uq_section_templates_type_code"')
    for row in cur.fetchall():
        print(f'Unique: {row["Column_name"]}')

    # Verify FK
    cur.execute('''
        SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = "section_templates"
          AND REFERENCED_TABLE_NAME IS NOT NULL
    ''')
    for row in cur.fetchall():
        print(f'FK: {row}')

    # Verify indexes
    cur.execute('SHOW INDEX FROM section_templates')
    for row in cur.fetchall():
        print(f'Index: {row["Key_name"]} on {row["Column_name"]}')