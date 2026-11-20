import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    # Verify counts
    for table in ['section_templates', 'role_templates', 'group_articles', 'group_article_media']:
        cur.execute(f'SELECT COUNT(*) as c FROM {table}')
        print(f'{table}: {cur.fetchone()["c"]}')
    
    print("\n=== Articles by scope ===")
    cur.execute("SELECT scope, COUNT(*) as c FROM group_articles GROUP BY scope")
    for row in cur.fetchall():
        print(f"  {row['scope']}: {row['c']}")
    
    print("\n=== Articles by group ===")
    cur.execute("SELECT group_id, COUNT(*) as c FROM group_articles GROUP BY group_id")
    for row in cur.fetchall():
        print(f"  {row['group_id']}: {row['c']}")
    
    print("\n=== Media linked to articles ===")
    cur.execute("""
        SELECT gam.legacy_id, ga.title, gam.kind, gam.provider
        FROM group_article_media gam
        JOIN group_articles ga ON gam.article_id = ga.id
    """)
    for row in cur.fetchall():
        print(f"  {row['legacy_id']} -> {row['title'][:40]} ({row['kind']}/{row['provider']})")
    
    print("\n=== Media with article not found ===")
    cur.execute("""
        SELECT gam.legacy_id, gam.article_id
        FROM group_article_media gam
        LEFT JOIN group_articles ga ON gam.article_id = ga.id
        WHERE ga.id IS NULL
    """)
    for row in cur.fetchall():
        print(f"  ORPHAN: {row['legacy_id']} -> article_id={row['article_id']}")