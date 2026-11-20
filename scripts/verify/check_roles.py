import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT DISTINCT scope FROM amigos_role_templates')
    for row in cur.fetchall():
        print(f'scope: {row["scope"]}')
    
    cur.execute('SELECT type_code, scope, code FROM amigos_role_templates')
    rows = cur.fetchall()
    pairs = [(r['type_code'], r['scope'], r['code']) for r in rows]
    print(f'Total records: {len(pairs)}')
    print(f'Unique (type_code, scope, code): {len(set(pairs))}')
    
    # Check orphaned type_codes
    cur.execute('SELECT DISTINCT type_code FROM amigos_role_templates')
    role_types = {r['type_code'] for r in cur.fetchall()}
    print(f'Distinct type_codes in roles: {len(role_types)}')
    for t in sorted(role_types):
        print(f'  {t}')