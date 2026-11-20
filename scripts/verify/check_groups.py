import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('DESCRIBE groups')
    for row in cur.fetchall():
        print(f'{row["Field"]}: {row["Type"]} Null={row["Null"]} Key={row["Key"]} Default={row["Default"]}')