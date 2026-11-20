import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("DESCRIBE amigos_group_catalog")
    for row in cur.fetchall():
        print(f'{row["Field"]} {row["Type"]} Null={row["Null"]} Key={row["Key"]}')