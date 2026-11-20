import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    # Count group_articles
    cur.execute('SELECT COUNT(*) as c FROM group_articles')
    total_articles = cur.fetchone()['c']
    print(f'total group_articles: {total_articles}')
    
    cur.execute('SELECT COUNT(*) as c FROM group_articles WHERE group_id IS NOT NULL')
    with_group = cur.fetchone()['c']
    print(f'con group_id: {with_group}')
    
    cur.execute('SELECT COUNT(*) as c FROM group_articles WHERE group_id IS NULL')
    without_group = cur.fetchone()['c']
    print(f'sin group_id: {without_group}')
    
    # Validate group_id references
    cur.execute('''
        SELECT COUNT(*) as c FROM group_articles ga
        LEFT JOIN groups g ON ga.group_id = g.id
        WHERE ga.group_id IS NOT NULL AND g.id IS NULL
    ''')
    invalid_refs = cur.fetchone()['c']
    print(f'referencias group_id invalidas: {invalid_refs}')
    
    # group_article_media
    cur.execute('SELECT COUNT(*) as c FROM group_article_media')
    total_media = cur.fetchone()['c']
    print(f'total group_article_media: {total_media}')
    
    cur.execute('''
        SELECT COUNT(*) as c FROM group_article_media gam
        LEFT JOIN group_articles ga ON gam.article_id = ga.id
        WHERE ga.id IS NULL
    ''')
    orphan_media = cur.fetchone()['c']
    print(f'media huerfanas: {orphan_media}')
    
    # Check duplicates
    cur.execute('SELECT COUNT(*) as c FROM (SELECT legacy_id FROM group_articles GROUP BY legacy_id HAVING COUNT(*) > 1) t')
    print(f'group_articles legacy_id duplicados: {cur.fetchone()["c"]}')
    
    cur.execute('SELECT COUNT(*) as c FROM (SELECT legacy_id FROM group_article_media GROUP BY legacy_id HAVING COUNT(*) > 1) t')
    print(f'group_article_media legacy_id duplicados: {cur.fetchone()["c"]}')