import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('''
        SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE REFERENCED_TABLE_SCHEMA = 'osap_chorus_test'
        AND TABLE_SCHEMA = 'osap_chorus_test'
        AND REFERENCED_TABLE_NAME IS NOT NULL
    ''')
    for row in cur.fetchall():
        print(f'{row["TABLE_NAME"]}.{row["COLUMN_NAME"]} -> {row["REFERENCED_TABLE_NAME"]}.{row["REFERENCED_COLUMN_NAME"]} ({row["CONSTRAINT_NAME"]})')