import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_chorus', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("DESCRIBE group_members")
    for row in cur.fetchall():
        print(row)
    print("---")
    cur.execute("SELECT role, status, COUNT(*) as c FROM group_members GROUP BY role, status")
    for row in cur.fetchall():
        print(row)
conn.close()