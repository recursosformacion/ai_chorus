import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    # Check the article that failed
    cur.execute("SELECT * FROM group_articles WHERE legacy_id='1390c1967a480330'")
    print(cur.fetchone())
    
    # Check all group_articles
    cur.execute("SELECT legacy_id, group_id, scope, title FROM group_articles")
    for row in cur.fetchall():
        print(f"  {row['legacy_id']} | group_id={row['group_id']} | scope={row['scope']} | {row['title'][:50]}")
    
    # Check group_article_media
    cur.execute("SELECT legacy_id, article_id, kind FROM group_article_media")
    for row in cur.fetchall():
        print(f"  {row['legacy_id']} -> article_id={row['article_id']} kind={row['kind']}")