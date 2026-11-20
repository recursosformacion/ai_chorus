import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT file_id, group_id FROM amigos_uploads')
    for row in cur.fetchall():
        print(f'file_id={row["file_id"]} group_id="{row["group_id"]}"')