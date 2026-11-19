import pymysql

for db_name in ['osap_api', 'osap', 'osap_main', 'osap_database', 'amigos']:
    try:
        conn = pymysql.connect(
            host='127.0.0.1',
            port=3306,
            user='osap2027',
            password='2027osapdb',
            database=db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=3
        )
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES LIKE 'amigos_%'")
            tables = cur.fetchall()
            if tables:
                print('Database ' + db_name + ': FOUND amigos tables')
                for t in tables:
                    for k, v in t.items():
                        print('  ' + v)
            else:
                print('Database ' + db_name + ': no amigos tables')
        conn.close()
    except Exception as e:
        print('Database ' + db_name + ': ' + type(e).__name__ + ' - ' + str(e))