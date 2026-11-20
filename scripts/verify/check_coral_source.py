import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    print("=== amigos_coral_details ===")
    cur.execute("SELECT * FROM amigos_coral_details")
    for row in cur.fetchall():
        print(row)
    
    print("\n=== amigos_coral_attributes ===")
    cur.execute("SELECT * FROM amigos_coral_attributes")
    for row in cur.fetchall():
        print(row)