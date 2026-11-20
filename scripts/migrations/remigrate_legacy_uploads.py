#!/usr/bin/env python3
"""Re-migrate legacy_uploads with groups present"""

import pymysql
from datetime import datetime
import uuid

SRC = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
TGT = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, autocommit=False)

def dt_to_str(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()

print("=== Re-migrando legacy_uploads ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    # Clear legacy_uploads
    tcur.execute("DELETE FROM legacy_uploads")
    TGT.commit()
    
    scur.execute("SELECT * FROM amigos_uploads")
    uploads = scur.fetchall()
    
    for u in uploads:
        try:
            group_id = u.get('group_id')
            if group_id == '':
                group_id = None
            
            # Verify group exists
            if group_id:
                tcur.execute("SELECT 1 FROM groups WHERE id=%s", (group_id,))
                if not tcur.fetchone():
                    print(f"  WARNING: group {group_id} not found for file_id {u['file_id']}")
                    group_id = None
            
            upload_id = str(uuid.uuid4()).replace('-', '')
            
            tcur.execute("""
                INSERT INTO legacy_uploads (id, legacy_file_id, group_id, mime_type, size_bytes, created_by, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                upload_id,
                u['file_id'],
                group_id,
                u['mime_type'],
                u['size_bytes'],
                u['created_by'],
                dt_to_str(u.get('created_at')),
            ))
            print(f"  INSERT legacy_upload file_id={u['file_id']} group={group_id}")
        except Exception as e:
            print(f"  ERROR {u['file_id']}: {e}")
    TGT.commit()

print("\n=== Verificando ===")
with TGT.cursor() as cur:
    cur.execute("""
        SELECT lu.legacy_file_id, lu.group_id, g.id as group_exists
        FROM legacy_uploads lu
        LEFT JOIN groups g ON lu.group_id = g.id
        ORDER BY lu.legacy_file_id
    """)
    for row in cur.fetchall():
        print(f"  file_id={row['legacy_file_id']} group_id={row['group_id']} group_exists={row['group_exists']}")

SRC.close()
TGT.close()