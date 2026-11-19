import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_chorus', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT VERSION()')
    row = cur.fetchone()
    print('MySQL version:', row)
    cur.execute('SHOW VARIABLES LIKE "sql_mode"')
    row = cur.fetchone()
    print('SQL mode:', row)
conn.close()