#!/usr/bin/env python3
"""Fix group_members section_id now that group_sections exist"""

import pymysql

SRC = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
TGT = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, autocommit=False)

print("=== Fixing group_members section_id ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    # Get the one member that has section_id in source
    scur.execute("SELECT * FROM amigos_members WHERE section_id IS NOT NULL")
    members_with_section = scur.fetchall()
    
    for m in members_with_section:
        print(f"Processing member {m['group_id']}/{m['user_id']} with section_id {m['section_id']}")
        
        # Resolve section_id from catalog
        scur.execute("""
            SELECT c.group_id, c.code
            FROM amigos_group_catalog c
            WHERE c.id=%s
        """, (m['section_id'],))
        cat = scur.fetchone()
        
        if cat:
            tcur.execute("""
                SELECT id FROM group_sections
                WHERE group_id=%s AND code=%s
            """, (cat['group_id'], cat['code']))
            gs = tcur.fetchone()
            
            if gs:
                section_id = gs['id']
                tcur.execute("""
                    UPDATE group_members
                    SET section_id=%s
                    WHERE group_id=%s AND user_sub=%s
                """, (section_id, m['group_id'], m['user_id']))
                print(f"  UPDATED section_id -> {section_id}")
            else:
                print(f"  ERROR: group_section not found for {cat['group_id']}/{cat['code']}")
        else:
            print(f"  ERROR: catalog entry not found for section_id {m['section_id']}")
    
    TGT.commit()

print("\n=== Verifying ===")
with TGT.cursor() as cur:
    cur.execute('SELECT id, group_id, user_sub, section_id FROM group_members')
    for row in cur.fetchall():
        print(row)

SRC.close()
TGT.close()