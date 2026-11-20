import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    # Check articles
    cur.execute("SELECT COUNT(*) as c FROM amigos_articles")
    print(f"amigos_articles: {cur.fetchone()['c']}")
    cur.execute("SELECT * FROM amigos_articles")
    for row in cur.fetchall():
        # Convert to string safely
        safe_row = {}
        for k, v in row.items():
            if isinstance(v, str):
                safe_row[k] = v.encode('ascii', 'replace').decode('ascii')
            else:
                safe_row[k] = v
        print(safe_row)
    print()
    
    # Check media
    cur.execute("SELECT COUNT(*) as c FROM amigos_media")
    print(f"amigos_media: {cur.fetchone()['c']}")
    cur.execute("SELECT * FROM amigos_media")
    for row in cur.fetchall():
        safe_row = {}
        for k, v in row.items():
            if isinstance(v, str):
                safe_row[k] = v.encode('ascii', 'replace').decode('ascii')
            else:
                safe_row[k] = v
        print(safe_row)