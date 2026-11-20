import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT DATABASE()')
    print(f'Database: {cur.fetchone()["DATABASE()"]}')
    
    cur.execute('SELECT COUNT(*) as c FROM group_articles')
    print(f'group_articles: {cur.fetchone()["c"]}')
    
    cur.execute('SELECT COUNT(*) as c FROM group_article_media')
    print(f'group_article_media: {cur.fetchone()["c"]}')
    
    cur.execute('SELECT COUNT(*) as c FROM section_templates')
    print(f'section_templates: {cur.fetchone()["c"]}')
    
    cur.execute('SELECT COUNT(*) as c FROM role_templates')
    print(f'role_templates: {cur.fetchone()["c"]}')