import pymysql
import sqlparse

conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)

migrations = [
    ('025_authorizations.sql', 'authorizations'),
    ('026_performances.sql', 'performances'),
    ('027_performance_groups.sql', 'performance_groups'),
]

for filename, table_name in migrations:
    print(f'\n=== Executing {filename} ===')
    with conn.cursor() as cur:
        with open(f'migrations/mysql/{filename}', encoding='utf-8') as f:
            sql = f.read()
        statements = sqlparse.split(sql)
        for stmt in statements:
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        conn.commit()
        print(f'{table_name} executed')

        # Verify columns
        cur.execute(f'DESCRIBE {table_name}')
        for row in cur.fetchall():
            print(f'  Column: {row["Field"]}: {row["Type"]} Null={row["Null"]} Key={row["Key"]} Default={row["Default"]}')

        # Verify PK
        cur.execute(f'SHOW KEYS FROM {table_name} WHERE Key_name = "PRIMARY"')
        for row in cur.fetchall():
            print(f'  PK: {row["Column_name"]}')

        # Verify unique keys
        cur.execute(f'SHOW KEYS FROM {table_name} WHERE Non_unique = 0 AND Key_name != "PRIMARY"')
        for row in cur.fetchall():
            print(f'  Unique: {row["Key_name"]} on {row["Column_name"]}')

        # Verify FKs
        cur.execute(f'''
            SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = "{table_name}"
              AND REFERENCED_TABLE_NAME IS NOT NULL
        ''')
        for row in cur.fetchall():
            print(f'  FK: {row}')

        # Verify indexes
        cur.execute(f'SHOW INDEX FROM {table_name}')
        for row in cur.fetchall():
            if row['Key_name'] != 'PRIMARY':
                print(f'  Index: {row["Key_name"]} on {row["Column_name"]}')

print('\n=== All migrations executed ===')