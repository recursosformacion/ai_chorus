#!/usr/bin/env python3
"""Fix: Update group_members with group-specific admin/musical role IDs"""

import pymysql

SRC = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
TGT = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, autocommit=False)

print("=== Actualizando group_members con group_roles ===")
updated = 0
skipped = 0
errors = []

with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_members")
    members = scur.fetchall()
    
    for m in members:
        try:
            # Resolve group_admin_role_id from group_roles
            group_admin_role_id = None
            if m.get('admin_role_id'):
                scur.execute("""
                    SELECT c.group_id, c.scope, c.code
                    FROM amigos_group_catalog c
                    WHERE c.id=%s
                """, (m['admin_role_id'],))
                cat = scur.fetchone()
                if cat:
                    tcur.execute("""
                        SELECT id FROM group_roles
                        WHERE group_id=%s AND scope=%s AND code=%s
                    """, (cat['group_id'], cat['scope'], cat['code']))
                    gr = tcur.fetchone()
                    if gr:
                        group_admin_role_id = gr['id']
                    else:
                        print(f"  WARNING: group_role no encontrado para admin_role_id {m['admin_role_id']} (group={cat['group_id']}, scope={cat['scope']}, code={cat['code']})")
                else:
                    print(f"  WARNING: catalog entry no encontrado para admin_role_id {m['admin_role_id']}")
            
            # Resolve group_musical_role_id from group_roles
            group_musical_role_id = None
            if m.get('musical_role_id'):
                scur.execute("""
                    SELECT c.group_id, c.scope, c.code
                    FROM amigos_group_catalog c
                    WHERE c.id=%s
                """, (m['musical_role_id'],))
                cat = scur.fetchone()
                if cat:
                    tcur.execute("""
                        SELECT id FROM group_roles
                        WHERE group_id=%s AND scope=%s AND code=%s
                    """, (cat['group_id'], cat['scope'], cat['code']))
                    gr = tcur.fetchone()
                    if gr:
                        group_musical_role_id = gr['id']
                    else:
                        print(f"  WARNING: group_role no encontrado para musical_role_id {m['musical_role_id']} (group={cat['group_id']}, scope={cat['scope']}, code={cat['code']})")
                else:
                    print(f"  WARNING: catalog entry no encontrado para musical_role_id {m['musical_role_id']}")
            
            if group_admin_role_id or group_musical_role_id:
                tcur.execute("""
                    UPDATE group_members
                    SET group_admin_role_id=%s, group_musical_role_id=%s
                    WHERE group_id=%s AND user_sub=%s
                """, (group_admin_role_id, group_musical_role_id, m['group_id'], m['user_id']))
                updated += 1
                print(f"  UPDATED member {m['group_id']}/{m['user_id']} admin={group_admin_role_id} musical={group_musical_role_id}")
            else:
                skipped += 1
        except Exception as e:
            errors.append(f"{m['group_id']}/{m['user_id']}: {e}")
            print(f"  ERROR {m['group_id']}/{m['user_id']}: {e}")
    TGT.commit()

print(f"\nActualizados: {updated}, Saltados: {skipped}, Errores: {len(errors)}")
for e in errors:
    print(f"  - {e}")

SRC.close()
TGT.close()