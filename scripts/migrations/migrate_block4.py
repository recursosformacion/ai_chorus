#!/usr/bin/env python3
"""
Bloque 4: Migración completa de datos pendientes OSAP -> Chorus
- group_roles (admin/musical from group_catalog)
- authorizations
- group_social_links
- legacy_uploads
- performances + performance_groups
- activity_log
- Update group_members with admin_role_id/musical_role_id from role_templates
"""

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

def dt_to_date_str(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if hasattr(dt, 'date'):
        return dt.date().isoformat()
    return dt.isoformat()

def td_to_time_str(td):
    """Convert timedelta to HH:MM:SS string"""
    if td is None:
        return None
    if isinstance(td, str):
        return td
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

stats = {
    'group_roles': {'inserted': 0, 'skipped': 0, 'errors': []},
    'authorizations': {'inserted': 0, 'skipped': 0, 'errors': []},
    'group_social_links': {'inserted': 0, 'skipped': 0, 'errors': []},
    'legacy_uploads': {'inserted': 0, 'skipped': 0, 'errors': []},
    'performances': {'inserted': 0, 'skipped': 0, 'errors': []},
    'performance_groups': {'inserted': 0, 'skipped': 0, 'errors': []},
    'activity_log': {'inserted': 0, 'skipped': 0, 'errors': []},
    'group_members_update': {'updated': 0, 'skipped': 0, 'errors': []},
}

# ============================================================
# 1. MIGRAR GROUP_ROLES (admin/musical from amigos_group_catalog) - 16 records
# ============================================================
print("\n=== Migrando group_roles (admin/musical) ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_group_catalog WHERE scope IN ('admin', 'musical')")
    roles = scur.fetchall()
    
    for r in roles:
        try:
            tcur.execute("SELECT 1 FROM group_roles WHERE legacy_id=%s", (r['id'],))
            if tcur.fetchone():
                stats['group_roles']['skipped'] += 1
                continue
            
            # Use group's created_at as fallback for created_at/updated_at
            tcur.execute("SELECT created_at FROM groups WHERE id=%s", (r['group_id'],))
            group_row = tcur.fetchone()
            default_dt = group_row['created_at'] if group_row else datetime.now().isoformat()
            
            tcur.execute("""
                INSERT INTO group_roles (id, legacy_id, group_id, scope, code, name, parent_id, sort_order, active, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                r['id'],  # legacy_id as PK
                r['id'],
                r['group_id'],
                r['scope'],
                r['code'],
                r['name'],
                r.get('parent_id'),  # all NULL in source
                r.get('sort_order') or 0,
                1 if r.get('active') else 0,
                default_dt,
                default_dt,
            ))
            stats['group_roles']['inserted'] += 1
            print(f"  INSERT group_role {r['group_id']}/{r['scope']}/{r['code']} ({r['name']})")
        except Exception as e:
            stats['group_roles']['errors'].append(f"{r['id']}: {e}")
            print(f"  ERROR {r['id']}: {e}")
    TGT.commit()

print(f"group_roles: {stats['group_roles']['inserted']} insertados, {stats['group_roles']['skipped']} saltados, {len(stats['group_roles']['errors'])} errores")

# ============================================================
# 2. MIGRAR AUTHORIZATIONS (2 records)
# ============================================================
print("\n=== Migrando authorizations ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_authorizations")
    auths = scur.fetchall()
    
    for a in auths:
        try:
            tcur.execute("SELECT 1 FROM authorizations WHERE user_id=%s AND scope=%s", (a['user_id'], a['scope']))
            if tcur.fetchone():
                stats['authorizations']['skipped'] += 1
                continue
            
            tcur.execute("""
                INSERT INTO authorizations (user_id, scope, direct_publish, granted_by, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                a['user_id'],
                a['scope'],
                1 if a.get('direct_publish') else 0,
                a.get('granted_by'),
                dt_to_str(a.get('created_at')),
                dt_to_str(a.get('updated_at')),
            ))
            stats['authorizations']['inserted'] += 1
            print(f"  INSERT authorization {a['user_id']}/{a['scope']}")
        except Exception as e:
            stats['authorizations']['errors'].append(f"{a['id']}: {e}")
            print(f"  ERROR {a['id']}: {e}")
    TGT.commit()

print(f"authorizations: {stats['authorizations']['inserted']} insertados, {stats['authorizations']['skipped']} saltados, {len(stats['authorizations']['errors'])} errores")

# ============================================================
# 3. MIGRAR GROUP_SOCIAL_LINKS (1 record)
# ============================================================
print("\n=== Migrando group_social_links ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_group_links")
    links = scur.fetchall()
    
    for l in links:
        try:
            tcur.execute("SELECT 1 FROM group_social_links WHERE legacy_id=%s", (str(l['id']),))
            if tcur.fetchone():
                stats['group_social_links']['skipped'] += 1
                continue
            
            link_id = str(uuid.uuid4()).replace('-', '')
            
            tcur.execute("""
                INSERT INTO group_social_links (id, legacy_id, group_id, kind, label, url, position, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                link_id,
                str(l['id']),
                l['group_id'],
                l['kind'],
                l.get('label'),
                l['url'],
                l.get('position') or 0,
                dt_to_str(l.get('created_at')),
            ))
            stats['group_social_links']['inserted'] += 1
            print(f"  INSERT social_link {l['group_id']}/{l['kind']}")
        except Exception as e:
            stats['group_social_links']['errors'].append(f"{l['id']}: {e}")
            print(f"  ERROR {l['id']}: {e}")
    TGT.commit()

print(f"group_social_links: {stats['group_social_links']['inserted']} insertados, {stats['group_social_links']['skipped']} saltados, {len(stats['group_social_links']['errors'])} errores")

# ============================================================
# 4. MIGRAR LEGACY_UPLOADS (13 records)
# ============================================================
print("\n=== Migrando legacy_uploads ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_uploads")
    uploads = scur.fetchall()
    
    for u in uploads:
        try:
            tcur.execute("SELECT 1 FROM legacy_uploads WHERE legacy_file_id=%s", (u['file_id'],))
            if tcur.fetchone():
                stats['legacy_uploads']['skipped'] += 1
                continue
            
            group_id = u.get('group_id')
            if group_id == '':
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
            stats['legacy_uploads']['inserted'] += 1
            print(f"  INSERT legacy_upload file_id={u['file_id']} group={group_id}")
        except Exception as e:
            stats['legacy_uploads']['errors'].append(f"{u['file_id']}: {e}")
            print(f"  ERROR {u['file_id']}: {e}")
    TGT.commit()

print(f"legacy_uploads: {stats['legacy_uploads']['inserted']} insertados, {stats['legacy_uploads']['skipped']} saltados, {len(stats['legacy_uploads']['errors'])} errores")

# ============================================================
# 5. MIGRAR PERFORMANCES (1 record) - amigos_actuaciones
# ============================================================
print("\n=== Migrando performances ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_actuaciones")
    performances = scur.fetchall()
    
    for p in performances:
        try:
            tcur.execute("SELECT 1 FROM performances WHERE id=%s", (p['id'],))
            if tcur.fetchone():
                stats['performances']['skipped'] += 1
                continue
            
            # Map fields from amigos_actuaciones to performances
            # Note: starts_at is timedelta in source, need to convert to time string
            starts_at_str = td_to_time_str(p.get('starts_at'))
            ends_at_str = td_to_time_str(p.get('ends_at'))
            ends_on_str = dt_to_date_str(p.get('ends_on'))
            
            tcur.execute("""
                INSERT INTO performances (
                    id, slug, title, summary, description, image_url, kind, modality,
                    event_status, editorial_status, starts_on, starts_at, ends_at,
                    venue_address, latitude, longitude, map_url,
                    organizer_name, organizer_website, event_url, tickets_url,
                    price, access_info, public_contact, registration_deadline,
                    weight, views, expands, buys, source_email, source_note,
                    created_at, updated_at, published_at, cancelled_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                p['id'],
                p['slug'],
                p['title'],
                p.get('summary'),
                p.get('description'),
                p.get('image_url'),
                p.get('kind') or 'concert',
                p.get('modality') or 'onsite',
                p.get('event_status') or 'scheduled',
                p.get('editorial_status') or 'draft',
                dt_to_date_str(p.get('starts_on')),
                starts_at_str,
                ends_at_str,
                p.get('venue_address'),
                p.get('latitude'),
                p.get('longitude'),
                p.get('map_url'),
                p.get('organizer_name'),
                p.get('organizer_website'),
                p.get('event_url'),
                p.get('tickets_url'),
                p.get('price'),
                p.get('access_info'),
                p.get('public_contact'),
                dt_to_str(p.get('registration_deadline')),
                p.get('weight'),
                p.get('views') or 0,
                p.get('expands') or 0,
                p.get('buys') or 0,
                p.get('source_email'),
                p.get('source_note'),
                dt_to_str(p.get('created_at')),
                dt_to_str(p.get('updated_at')),
                dt_to_str(p.get('published_at')),
                dt_to_str(p.get('cancelled_at')),
            ))
            stats['performances']['inserted'] += 1
            print(f"  INSERT performance {p['id']} ({p['title']})")
        except Exception as e:
            stats['performances']['errors'].append(f"{p['id']}: {e}")
            print(f"  ERROR {p['id']}: {e}")
    TGT.commit()

print(f"performances: {stats['performances']['inserted']} insertados, {stats['performances']['skipped']} saltados, {len(stats['performances']['errors'])} errores")

# ============================================================
# 6. MIGRAR PERFORMANCE_GROUPS (0 records) - amigos_actuacion_groups
# ============================================================
print("\n=== Migrando performance_groups ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_actuacion_groups")
    perf_groups = scur.fetchall()
    
    for pg in perf_groups:
        try:
            tcur.execute("SELECT 1 FROM performance_groups WHERE performance_id=%s AND group_id=%s", (pg['performance_id'], pg['group_id']))
            if tcur.fetchone():
                stats['performance_groups']['skipped'] += 1
                continue
            
            tcur.execute("""
                INSERT INTO performance_groups (performance_id, group_id, role)
                VALUES (%s,%s,%s)
            """, (
                pg['performance_id'],
                pg['group_id'],
                pg.get('role') or 'participant',
            ))
            stats['performance_groups']['inserted'] += 1
            print(f"  INSERT performance_group {pg['performance_id']}/{pg['group_id']}")
        except Exception as e:
            stats['performance_groups']['errors'].append(f"{pg['performance_id']}/{pg['group_id']}: {e}")
            print(f"  ERROR {pg['performance_id']}/{pg['group_id']}: {e}")
    TGT.commit()

print(f"performance_groups: {stats['performance_groups']['inserted']} insertados, {stats['performance_groups']['skipped']} saltados, {len(stats['performance_groups']['errors'])} errores")

# ============================================================
# 7. MIGRAR ACTIVITY_LOG (57 records) - amigos_events
# ============================================================
print("\n=== Migrando activity_log ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_events")
    events = scur.fetchall()
    
    for e in events:
        try:
            tcur.execute("SELECT 1 FROM activity_log WHERE legacy_id=%s", (str(e['id']),))
            if tcur.fetchone():
                stats['activity_log']['skipped'] += 1
                continue
            
            group_id = e.get('group_id')
            if group_id == '' or group_id == 'None':
                group_id = None
            
            article_id = e.get('article_id')
            if article_id:
                # Resolve to group_articles.id (legacy_id)
                tcur.execute("SELECT id FROM group_articles WHERE legacy_id=%s", (article_id,))
                article = tcur.fetchone()
                if article:
                    article_id = article['id']
                else:
                    article_id = None
            
            tcur.execute("""
                INSERT INTO activity_log (legacy_id, group_id, article_id, event_type, actor, from_status, to_status, detail_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                str(e['id']),
                group_id,
                article_id,
                e['event_type'],
                e['actor'],
                e.get('from_status'),
                e.get('to_status'),
                e.get('detail_json'),
                dt_to_str(e.get('created_at')),
            ))
            stats['activity_log']['inserted'] += 1
            print(f"  INSERT activity_log {e['id']} ({e['event_type']})")
        except Exception as e:
            stats['activity_log']['errors'].append(f"{e['id']}: {e}")
            print(f"  ERROR {e['id']}: {e}")
    TGT.commit()

print(f"activity_log: {stats['activity_log']['inserted']} insertados, {stats['activity_log']['skipped']} saltados, {len(stats['activity_log']['errors'])} errores")

# ============================================================
# 8. ACTUALIZAR GROUP_MEMBERS con admin_role_id/musical_role_id desde role_templates
# ============================================================
print("\n=== Actualizando group_members con role_templates ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_members")
    members = scur.fetchall()
    
    for m in members:
        try:
            # Resolve admin_role_id
            admin_role_id = None
            if m.get('admin_role_id'):
                scur.execute("""
                    SELECT c.type_code, c.code, c.scope
                    FROM amigos_group_catalog c
                    WHERE c.id=%s
                """, (m['admin_role_id'],))
                cat = scur.fetchone()
                if cat:
                    tcur.execute("""
                        SELECT id FROM role_templates
                        WHERE type_code=%s AND scope=%s AND code=%s
                    """, (cat['type_code'], cat['scope'], cat['code']))
                    rt = tcur.fetchone()
                    if rt:
                        admin_role_id = rt['id']
                    else:
                        print(f"  WARNING: role_template no encontrado para admin_role_id {m['admin_role_id']} (type_code={cat['type_code']}, scope={cat['scope']}, code={cat['code']})")
                else:
                    print(f"  WARNING: catalog entry no encontrado para admin_role_id {m['admin_role_id']}")
            
            # Resolve musical_role_id
            musical_role_id = None
            if m.get('musical_role_id'):
                scur.execute("""
                    SELECT c.type_code, c.code, c.scope
                    FROM amigos_group_catalog c
                    WHERE c.id=%s
                """, (m['musical_role_id'],))
                cat = scur.fetchone()
                if cat:
                    tcur.execute("""
                        SELECT id FROM role_templates
                        WHERE type_code=%s AND scope=%s AND code=%s
                    """, (cat['type_code'], cat['scope'], cat['code']))
                    rt = tcur.fetchone()
                    if rt:
                        musical_role_id = rt['id']
                    else:
                        print(f"  WARNING: role_template no encontrado para musical_role_id {m['musical_role_id']} (type_code={cat['type_code']}, scope={cat['scope']}, code={cat['code']})")
                else:
                    print(f"  WARNING: catalog entry no encontrado para musical_role_id {m['musical_role_id']}")
            
            if admin_role_id or musical_role_id:
                tcur.execute("""
                    UPDATE group_members
                    SET admin_role_id=%s, musical_role_id=%s
                    WHERE group_id=%s AND user_sub=%s
                """, (admin_role_id, musical_role_id, m['group_id'], m['user_id']))
                stats['group_members_update']['updated'] += 1
                print(f"  UPDATED member {m['group_id']}/{m['user_id']} admin={admin_role_id} musical={musical_role_id}")
            else:
                stats['group_members_update']['skipped'] += 1
        except Exception as e:
            stats['group_members_update']['errors'].append(f"{m['group_id']}/{m['user_id']}: {e}")
            print(f"  ERROR {m['group_id']}/{m['user_id']}: {e}")
    TGT.commit()

print(f"group_members_update: {stats['group_members_update']['updated']} actualizados, {stats['group_members_update']['skipped']} saltados, {len(stats['group_members_update']['errors'])} errores")

# ============================================================
# RESUMEN
# ============================================================
print("\n" + "="*70)
print("RESUMEN BLOQUE 4")
print("="*70)
for table, s in stats.items():
    if 'inserted' in s:
        print(f"{table:25s} | insertados={s['inserted']:4d} | saltados={s['skipped']:4d} | errores={len(s['errors']):3d}")
    else:
        print(f"{table:25s} | actualizados={s['updated']:4d} | saltados={s['skipped']:4d} | errores={len(s['errors']):3d}")
    for e in s['errors'][:3]:
        print(f"  - {e}")
    if len(s['errors']) > 3:
        print(f"  ... y {len(s['errors']) - 3} errores mas")

SRC.close()
TGT.close()