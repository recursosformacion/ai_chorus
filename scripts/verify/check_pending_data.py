import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    # group_catalog admin/musical
    cur.execute("SELECT * FROM amigos_group_catalog WHERE scope IN ('admin', 'musical')")
    print("=== amigos_group_catalog (admin/musical) ===")
    for row in cur.fetchall():
        print(row)
    print()
    
    # authorizations
    cur.execute("SELECT * FROM amigos_authorizations")
    print("=== amigos_authorizations ===")
    for row in cur.fetchall():
        print(row)
    print()
    
    # group_links
    cur.execute("SELECT * FROM amigos_group_links")
    print("=== amigos_group_links ===")
    for row in cur.fetchall():
        print(row)
    print()
    
    # uploads
    cur.execute("SELECT * FROM amigos_uploads")
    print("=== amigos_uploads ===")
    for row in cur.fetchall():
        print(row)
    print()
    
    # actuaciones
    cur.execute("SELECT * FROM amigos_actuaciones")
    print("=== amigos_actuaciones ===")
    for row in cur.fetchall():
        print(row)
    print()
    
    # events
    cur.execute("SELECT * FROM amigos_events")
    print("=== amigos_events ===")
    for row in cur.fetchall():
        # Truncate long fields
        safe = {}
        for k, v in row.items():
            if isinstance(v, str) and len(v) > 100:
                safe[k] = v[:100] + '...'
            else:
                safe[k] = v
        print(safe)
    print()

conn.close()