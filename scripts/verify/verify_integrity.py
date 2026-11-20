import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    # Verify group_members FK references
    cur.execute('''
        SELECT gm.id, gm.group_id, gm.user_sub, gm.section_id,
               gs.id as section_exists
        FROM group_members gm
        LEFT JOIN group_sections gs ON gm.section_id = gs.id
    ''')
    print("=== group_members -> group_sections ===")
    for row in cur.fetchall():
        print(f"  member={row['id']} group={row['group_id']} user={row['user_sub']} section_id={row['section_id']} section_exists={row['section_exists']}")
    
    # Verify group_sections -> groups
    cur.execute('''
        SELECT gs.id, gs.group_id, gs.code, g.id as group_exists
        FROM group_sections gs
        LEFT JOIN groups g ON gs.group_id = g.id
    ''')
    print("\n=== group_sections -> groups ===")
    for row in cur.fetchall():
        print(f"  section={row['id']} group={row['group_id']} code={row['code']} group_exists={row['group_exists']}")
    
    # Verify group_history -> groups
    cur.execute('''
        SELECT gh.id, gh.group_id, g.id as group_exists
        FROM group_history gh
        LEFT JOIN groups g ON gh.group_id = g.id
    ''')
    print("\n=== group_history -> groups ===")
    for row in cur.fetchall():
        print(f"  history={row['id']} group={row['group_id']} group_exists={row['group_exists']}")
    
    # Verify group_members -> groups
    cur.execute('''
        SELECT gm.id, gm.group_id, g.id as group_exists
        FROM group_members gm
        LEFT JOIN groups g ON gm.group_id = g.id
    ''')
    print("\n=== group_members -> groups ===")
    for row in cur.fetchall():
        print(f"  member={row['id']} group={row['group_id']} group_exists={row['group_exists']}")