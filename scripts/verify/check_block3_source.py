import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    # Check section_templates
    cur.execute("SELECT COUNT(*) as c FROM amigos_section_templates")
    print(f"amigos_section_templates: {cur.fetchone()['c']}")
    cur.execute("SELECT * FROM amigos_section_templates LIMIT 5")
    for row in cur.fetchall():
        print(row)
    print()
    
    # Check role_templates
    cur.execute("SELECT COUNT(*) as c FROM amigos_role_templates")
    print(f"amigos_role_templates: {cur.fetchone()['c']}")
    cur.execute("SELECT * FROM amigos_role_templates LIMIT 5")
    for row in cur.fetchall():
        print(row)
    print()
    
    # Check articles
    cur.execute("SELECT COUNT(*) as c FROM amigos_articles")
    print(f"amigos_articles: {cur.fetchone()['c']}")
    cur.execute("SELECT * FROM amigos_articles")
    for row in cur.fetchall():
        print(row)
    print()
    
    # Check media
    cur.execute("SELECT COUNT(*) as c FROM amigos_media")
    print(f"amigos_media: {cur.fetchone()['c']}")
    cur.execute("SELECT * FROM amigos_media LIMIT 5")
    for row in cur.fetchall():
        print(row)