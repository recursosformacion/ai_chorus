#!/usr/bin/env python3
"""
Bloque 2: Migración OSAP -> Chorus (grupos, catálogo, miembros, historial)
Idempotente: verifica existencia antes de insertar.
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

def iso_now():
    return datetime.now().isoformat()

stats = {
    'groups': {'inserted': 0, 'skipped': 0, 'errors': []},
    'group_sections': {'inserted': 0, 'skipped': 0, 'errors': []},
    'group_members': {'inserted': 0, 'skipped': 0, 'errors': []},
    'group_history': {'inserted': 0, 'skipped': 0, 'errors': []},
}

# ============================================================
# 1. MIGRAR GRUPOS (3) - cachear created_at para sections
# ============================================================
print("\n=== Migrando grupos ===")
group_created_at = {}  # group_id -> created_at
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_groups")
    groups = scur.fetchall()
    
    for g in groups:
        try:
            tcur.execute("SELECT 1 FROM groups WHERE id=%s", (g['id'],))
            if tcur.fetchone():
                stats['groups']['skipped'] += 1
                print(f"  SKIP grupo {g['id']} (ya existe)")
                continue
            
            created_at_str = dt_to_str(g.get('created_at'))
            updated_at_str = dt_to_str(g.get('updated_at'))
            group_created_at[g['id']] = created_at_str or iso_now()
            
            tcur.execute("""
                INSERT INTO groups (
                    id, entity_id, name, timezone, created_by, join_code,
                    created_at, updated_at, slug, kind, description,
                    image_url, website, email, logo_url, status,
                    editorial_mode, technical_description,
                    foundation_date, dissolution_date, locality, region,
                    country_code, venue, formation_type, member_count,
                    public_email, language, repertoire, venues
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                g['id'],
                g['id'],
                g['name'],
                g.get('timezone') or 'Europe/Madrid',
                g.get('created_by') or 'system',
                g.get('join_code') or '',
                created_at_str,
                updated_at_str,
                g.get('slug'),
                g.get('kind') or 'grupo',
                g.get('description'),
                g.get('image_url'),
                g.get('website'),
                g.get('email'),
                g.get('logo_url'),
                g.get('status') or 'active',
                g.get('editorial_mode') or 'moderated',
                g.get('technical_description'),
                dt_to_date_str(g.get('foundation_date')),
                dt_to_date_str(g.get('dissolution_date')),
                g.get('locality'),
                g.get('region'),
                g.get('country_code'),
                g.get('venue'),
                g.get('formation_type'),
                g.get('member_count'),
                g.get('public_email'),
                None,
                None,
                None,
            ))
            stats['groups']['inserted'] += 1
            print(f"  INSERT grupo {g['id']} ({g['name']})")
        except Exception as e:
            stats['groups']['errors'].append(f"{g['id']}: {e}")
            print(f"  ERROR grupo {g['id']}: {e}")
    TGT.commit()

print(f"Grupos: {stats['groups']['inserted']} insertados, {stats['groups']['skipped']} saltados, {len(stats['groups']['errors'])} errores")

# ============================================================
# 2. MIGRAR CATÁLOGO scope='section' -> group_sections (8)
# ============================================================
print("\n=== Migrando group_sections (scope=section) ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_group_catalog WHERE scope='section'")
    sections = scur.fetchall()
    
    for s in sections:
        try:
            tcur.execute("SELECT 1 FROM group_sections WHERE group_id=%s AND code=%s", (s['group_id'], s['code']))
            if tcur.fetchone():
                stats['group_sections']['skipped'] += 1
                print(f"  SKIP section {s['group_id']}/{s['code']} (ya existe)")
                continue
            
            parent_id = s.get('parent_id')
            # Usar created_at del grupo como fallback
            default_dt = group_created_at.get(s['group_id'], iso_now())
            
            tcur.execute("""
                INSERT INTO group_sections (id, group_id, code, name, scope, parent_id, sort_order, active, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                s['id'],
                s['group_id'],
                s['code'],
                s['name'],
                'section',
                parent_id,
                s.get('sort_order') or 0,
                1 if s.get('active') else 0,
                default_dt,
                default_dt,
            ))
            stats['group_sections']['inserted'] += 1
            print(f"  INSERT section {s['group_id']}/{s['code']} ({s['name']})")
        except Exception as e:
            stats['group_sections']['errors'].append(f"{s['group_id']}/{s['code']}: {e}")
            print(f"  ERROR section {s['group_id']}/{s['code']}: {e}")
    TGT.commit()

print(f"Sections: {stats['group_sections']['inserted']} insertados, {stats['group_sections']['skipped']} saltados, {len(stats['group_sections']['errors'])} errores")

# ============================================================
# 3. MIGRAR MIEMBROS (3) - resolver referencias
# ============================================================
print("\n=== Migrando group_members ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_members")
    members = scur.fetchall()
    
    for m in members:
        try:
            tcur.execute("SELECT 1 FROM group_members WHERE group_id=%s AND user_sub=%s", (m['group_id'], m['user_id']))
            if tcur.fetchone():
                stats['group_members']['skipped'] += 1
                print(f"  SKIP member {m['group_id']}/{m['user_id']} (ya existe)")
                continue
            
            # created_at -> joined_at
            joined_at = dt_to_str(m.get('created_at'))
            
            # granted_by directo
            granted_by = m.get('granted_by')
            
            # admin_role_id: NO resolver (role_templates vacío, no inventar equivalencias)
            admin_role_id = None
            if m.get('admin_role_id'):
                print(f"  WARNING: admin_role_id {m['admin_role_id']} presente pero role_templates vacío - dejando NULL")
            
            # musical_role_id: NO resolver
            musical_role_id = None
            if m.get('musical_role_id'):
                print(f"  WARNING: musical_role_id {m['musical_role_id']} presente pero role_templates vacío - dejando NULL")
            
            # section_id: resolver a group_sections.id (catálogo scope='section' del mismo grupo)
            section_id = None
            if m.get('section_id'):
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
                        print(f"  RESUELTO section_id -> {section_id}")
                    else:
                        print(f"  WARNING: group_section no encontrada para section_id {m['section_id']} (group={cat['group_id']}, code={cat['code']})")
                else:
                    print(f"  WARNING: catalog entry no encontrado para section_id {m['section_id']}")
            
            # Generar UUID para id (PK en destino)
            member_id = str(uuid.uuid4()).replace('-', '')
            
            tcur.execute("""
                INSERT INTO group_members (
                    id, group_id, user_sub, role, status,
                    voice_code, voice_label, section,
                    joined_at, updated_at,
                    display_name, granted_by,
                    admin_role_id, musical_role_id, section_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                member_id,
                m['group_id'],
                m['user_id'],
                m.get('role') or 'member',
                m.get('status') or 'active',
                None,
                None,
                None,
                joined_at,
                dt_to_str(m.get('updated_at')),
                None,
                granted_by,
                admin_role_id,
                musical_role_id,
                section_id,
            ))
            stats['group_members']['inserted'] += 1
            print(f"  INSERT member {m['group_id']}/{m['user_id']} (section_id={section_id})")
        except Exception as e:
            stats['group_members']['errors'].append(f"{m['group_id']}/{m['user_id']}: {e}")
            print(f"  ERROR member {m['group_id']}/{m['user_id']}: {e}")
    TGT.commit()

print(f"Members: {stats['group_members']['inserted']} insertados, {stats['group_members']['skipped']} saltados, {len(stats['group_members']['errors'])} errores")

# ============================================================
# 4. MIGRAR HISTORIAL (6)
# ============================================================
print("\n=== Migrando group_history ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_group_history")
    history = scur.fetchall()
    
    for h in history:
        try:
            tcur.execute("SELECT 1 FROM group_history WHERE id=%s", (h['id'],))
            if tcur.fetchone():
                stats['group_history']['skipped'] += 1
                print(f"  SKIP history {h['id']} (ya existe)")
                continue
            
            tcur.execute("""
                INSERT INTO group_history (id, group_id, event_type, member_user_id, person_name, role, start_date, end_date, notes, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                h['id'],
                h['group_id'],
                h.get('event_type'),
                h.get('member_user_id'),
                h.get('person_name'),
                h.get('role'),
                dt_to_date_str(h.get('start_date')),
                dt_to_date_str(h.get('end_date')),
                h.get('notes'),
                dt_to_str(h.get('created_at')),
            ))
            stats['group_history']['inserted'] += 1
            print(f"  INSERT history {h['id']} ({h['event_type']})")
        except Exception as e:
            stats['group_history']['errors'].append(f"{h['id']}: {e}")
            print(f"  ERROR history {h['id']}: {e}")
    TGT.commit()

print(f"History: {stats['group_history']['inserted']} insertados, {stats['group_history']['skipped']} saltados, {len(stats['group_history']['errors'])} errores")

# ============================================================
# RESUMEN
# ============================================================
print("\n" + "="*60)
print("RESUMEN BLOQUE 2")
print("="*60)
for table, s in stats.items():
    print(f"{table:20s} | insertados={s['inserted']:3d} | saltados={s['skipped']:3d} | errores={len(s['errors']):3d}")
    for e in s['errors']:
        print(f"  - {e}")

SRC.close()
TGT.close()