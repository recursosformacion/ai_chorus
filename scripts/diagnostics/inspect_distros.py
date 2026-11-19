import pymysql

conn = pymysql.connect(
    host='127.0.0.1',
    port=3306,
    user='osap2027',
    password='2027osapdb',
    database='osap_api',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

print("=== DISTRIBUCIONES CLAVE ===")

with conn.cursor() as cur:
    # amigos_groups
    cur.execute("SELECT status, kind, COUNT(*) as c FROM amigos_groups GROUP BY status, kind")
    for row in cur.fetchall():
        print("groups: " + str(row))
    
    # amigos_members
    cur.execute("SELECT role, status, COUNT(*) as c FROM amigos_members GROUP BY role, status")
    for row in cur.fetchall():
        print("members: " + str(row))
    
    # amigos_articles
    cur.execute("SELECT scope, status, COUNT(*) as c FROM amigos_articles GROUP BY scope, status")
    for row in cur.fetchall():
        print("articles: " + str(row))
    cur.execute("SELECT COUNT(*) as c FROM amigos_articles WHERE scope='group' AND group_id IS NOT NULL")
    row = cur.fetchone()
    print("articles scope=group with group_id: " + str(row['c']))
    cur.execute("SELECT COUNT(*) as c FROM amigos_articles WHERE scope='general' OR group_id IS NULL")
    row = cur.fetchone()
    print("articles scope!=group or group_id NULL: " + str(row['c']))
    
    # amigos_media
    cur.execute("SELECT kind, COUNT(*) as c FROM amigos_media GROUP BY kind")
    for row in cur.fetchall():
        print("media: " + str(row))
    cur.execute("""
        SELECT COUNT(*) as c FROM amigos_media m
        LEFT JOIN amigos_articles a ON m.article_id = a.id
        WHERE a.id IS NULL OR a.scope != 'group'
    """)
    row = cur.fetchone()
    print("media without valid group article: " + str(row['c']))
    
    # amigos_coral_attributes
    cur.execute("SELECT facet, COUNT(*) as c FROM amigos_coral_attributes GROUP BY facet")
    for row in cur.fetchall():
        print("coral_attr: " + str(row))
    
    # amigos_coral_details
    cur.execute("SELECT COUNT(*) as c FROM amigos_coral_details")
    row = cur.fetchone()
    print("coral_details count: " + str(row['c']))
    
    # amigos_group_types
    cur.execute("SELECT kind, COUNT(*) as c FROM amigos_group_types GROUP BY kind")
    for row in cur.fetchall():
        print("group_types: " + str(row))
    
    # amigos_role_templates
    cur.execute("SELECT scope, COUNT(*) as c FROM amigos_role_templates GROUP BY scope")
    for row in cur.fetchall():
        print("role_templates: " + str(row))
    
    # amigos_section_templates
    cur.execute("SELECT COUNT(*) as c FROM amigos_section_templates")
    row = cur.fetchone()
    print("section_templates count: " + str(row['c']))

conn.close()