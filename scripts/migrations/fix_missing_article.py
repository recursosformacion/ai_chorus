#!/usr/bin/env python3
"""Fix: Migrate the missing general article"""

import pymysql
from datetime import datetime

SRC = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
TGT = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, autocommit=False)

def dt_to_str(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()

def dt_to_date_str(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if hasattr(dt, 'date'):
        return dt.date().isoformat()
    return dt.isoformat()

print("=== Migrando artículo general faltante ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_articles WHERE id='1390c1967a480330'")
    a = scur.fetchone()
    
    if a:
        try:
            tcur.execute("SELECT 1 FROM group_articles WHERE legacy_id=%s", (a['id'],))
            if tcur.fetchone():
                print("  SKIP: ya existe")
            else:
                scope = 'public' if a.get('scope') == 'general' else 'group'
                group_id = a.get('group_id')
                
                author_id = a.get('author_user_id')
                publisher_id = a.get('publisher_user_id')
                reviewed_by = a.get('reviewed_by')
                
                tcur.execute("""
                    INSERT INTO group_articles (
                        id, legacy_id, group_id, title, slug, summary, body, cover_url,
                        event_date, status, author_user_id, publisher_user_id,
                        reviewed_by, reviewed_at, review_note, published_at,
                        created_at, updated_at, scope
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    a['id'],
                    a['id'],
                    group_id,
                    a['title'],
                    a['slug'],
                    a.get('summary'),
                    a.get('body'),
                    a.get('cover_url'),
                    dt_to_date_str(a.get('event_date')),
                    a.get('status') or 'draft',
                    author_id,
                    publisher_id,
                    reviewed_by,
                    dt_to_str(a.get('reviewed_at')),
                    a.get('review_note'),
                    dt_to_str(a.get('published_at')),
                    dt_to_str(a.get('created_at')),
                    dt_to_str(a.get('updated_at')),
                    scope,
                ))
                print(f"  INSERT article {a['id']} (scope={scope}, group_id={group_id})")
        except Exception as e:
            print(f"  ERROR: {e}")
        TGT.commit()

print("\n=== Verificando ===")
with TGT.cursor() as cur:
    cur.execute("SELECT legacy_id, group_id, scope, title FROM group_articles")
    for row in cur.fetchall():
        print(f"  {row['legacy_id']} | group_id={row['group_id']} | scope={row['scope']} | {row['title'][:50]}")

SRC.close()
TGT.close()