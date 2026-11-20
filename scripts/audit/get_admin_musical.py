import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT * FROM amigos_group_catalog WHERE scope IN ("admin", "musical")')
    for row in cur.fetchall():
        print(row)