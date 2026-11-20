import pymysql

conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT * FROM amigos_group_types')
    rows = cur.fetchall()
    print(f'Total registros: {len(rows)}')
    codes = [r['code'] for r in rows]
    print(f'Codigos unicos: {len(set(codes))}')
    print(f'Duplicados: {len(codes) - len(set(codes))}')
    
    # Check parent_code references
    code_set = set(codes)
    invalid_parents = []
    for r in rows:
        if r['parent_code'] and r['parent_code'] not in code_set:
            invalid_parents.append((r['code'], r['parent_code']))
    print(f'Parent_code invalidos: {invalid_parents}')
    
    # Check sort_order
    print()
    print('sort_order por codigo:')
    for r in sorted(rows, key=lambda x: x['sort_order']):
        print(f'  {r["code"]}: sort_order={r["sort_order"]}, parent={r["parent_code"]}, kind={r["kind"]}')
    
    # Check vocal specifically
    vocal = [r for r in rows if r['code'] == 'vocal']
    print()
    print(f'vocal: {vocal}')
    
    # Check kind values
    kinds = set(r['kind'] for r in rows)
    print(f'Kinds unicos: {kinds}')
    
    # Check NULL parent_codes
    roots = [r for r in rows if r['parent_code'] is None]
    print(f'Raices (parent_code NULL): {[r["code"] for r in roots]}')