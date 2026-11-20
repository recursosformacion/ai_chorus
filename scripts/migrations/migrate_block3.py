#!/usr/bin/env python3
"""
Bloque 3: Migración plantillas, artículos y medios
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

stats = {
    'section_templates': {'inserted': 0, 'skipped': 0, 'errors': []},
    'role_templates': {'inserted': 0, 'skipped': 0, 'errors': []},
    'group_articles': {'inserted': 0, 'skipped': 0, 'errors': []},
    'group_article_media': {'inserted': 0, 'skipped': 0, 'errors': []},
}

# ============================================================
# 1. MIGRAR PLANTILLAS DE SECCIONES (273)
# ============================================================
print("\n=== Migrando section_templates (273) ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_section_templates")
    templates = scur.fetchall()
    
    for t in templates:
        try:
            tcur.execute("SELECT 1 FROM section_templates WHERE id=%s", (t['id'],))
            if tcur.fetchone():
                stats['section_templates']['skipped'] += 1
                continue
            
            # Verificar que type_code existe en group_types
            tcur.execute("SELECT 1 FROM group_types WHERE code=%s", (t['type_code'],))
            if not tcur.fetchone():
                stats['section_templates']['errors'].append(f"{t['id']}: type_code {t['type_code']} no existe en group_types")
                print(f"  ERROR: type_code {t['type_code']} no existe en group_types")
                continue
            
            tcur.execute("""
                INSERT INTO section_templates (id, type_code, code, name, sort_order)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                t['id'],
                t['type_code'],
                t['code'],
                t['name'],
                t.get('sort_order') or 0,
            ))
            stats['section_templates']['inserted'] += 1
        except Exception as e:
            stats['section_templates']['errors'].append(f"{t['id']}: {e}")
            print(f"  ERROR {t['id']}: {e}")
    TGT.commit()

print(f"section_templates: {stats['section_templates']['inserted']} insertados, {stats['section_templates']['skipped']} saltados, {len(stats['section_templates']['errors'])} errores")

# ============================================================
# 2. MIGRAR PLANTILLAS DE ROLES (409)
# ============================================================
print("\n=== Migrando role_templates (409) ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_role_templates")
    templates = scur.fetchall()
    
    for t in templates:
        try:
            tcur.execute("SELECT 1 FROM role_templates WHERE id=%s", (t['id'],))
            if tcur.fetchone():
                stats['role_templates']['skipped'] += 1
                continue
            
            # Verificar que type_code existe en group_types
            tcur.execute("SELECT 1 FROM group_types WHERE code=%s", (t['type_code'],))
            if not tcur.fetchone():
                stats['role_templates']['errors'].append(f"{t['id']}: type_code {t['type_code']} no existe en group_types")
                print(f"  ERROR: type_code {t['type_code']} no existe en group_types")
                continue
            
            tcur.execute("""
                INSERT INTO role_templates (id, type_code, scope, code, name, sort_order)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                t['id'],
                t['type_code'],
                t['scope'],
                t['code'],
                t['name'],
                t.get('sort_order') or 0,
            ))
            stats['role_templates']['inserted'] += 1
        except Exception as e:
            stats['role_templates']['errors'].append(f"{t['id']}: {e}")
            print(f"  ERROR {t['id']}: {e}")
    TGT.commit()

print(f"role_templates: {stats['role_templates']['inserted']} insertados, {stats['role_templates']['skipped']} saltados, {len(stats['role_templates']['errors'])} errores")

# ============================================================
# 3. MIGRAR ARTÍCULOS (18)
# ============================================================
print("\n=== Migrando group_articles (18) ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_articles")
    articles = scur.fetchall()
    
    for a in articles:
        try:
            tcur.execute("SELECT 1 FROM group_articles WHERE legacy_id=%s", (a['id'],))
            if tcur.fetchone():
                stats['group_articles']['skipped'] += 1
                continue
            
            # Mapear scope: general -> public, group -> group
            scope = 'public' if a.get('scope') == 'general' else 'group'
            
            # group_id: NULL para artículos generales
            group_id = a.get('group_id')
            
            # Verificar que group_id existe si no es NULL
            if group_id:
                tcur.execute("SELECT 1 FROM groups WHERE id=%s", (group_id,))
                if not tcur.fetchone():
                    stats['group_articles']['errors'].append(f"{a['id']}: group_id {group_id} no existe en groups")
                    print(f"  ERROR: group_id {group_id} no existe")
                    continue
            
            # Verificar author_user_id (no validamos contra osap-auth, solo formato UUID)
            author_id = a.get('author_user_id')
            
            # publisher_user_id y reviewed_by (pueden ser NULL)
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
                a['id'],  # PK = legacy id
                a['id'],  # legacy_id para trazabilidad
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
            stats['group_articles']['inserted'] += 1
        except Exception as e:
            stats['group_articles']['errors'].append(f"{a['id']}: {e}")
            print(f"  ERROR {a['id']}: {e}")
    TGT.commit()

print(f"group_articles: {stats['group_articles']['inserted']} insertados, {stats['group_articles']['skipped']} saltados, {len(stats['group_articles']['errors'])} errores")

# ============================================================
# 4. MIGRAR MEDIOS (16)
# ============================================================
print("\n=== Migrando group_article_media (16) ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    scur.execute("SELECT * FROM amigos_media")
    media = scur.fetchall()
    
    for m in media:
        try:
            tcur.execute("SELECT 1 FROM group_article_media WHERE legacy_id=%s", (str(m['id']),))
            if tcur.fetchone():
                stats['group_article_media']['skipped'] += 1
                continue
            
            # Resolver article_id: buscar por legacy_id en group_articles
            article_legacy_id = m['article_id']
            tcur.execute("SELECT id FROM group_articles WHERE legacy_id=%s", (article_legacy_id,))
            article = tcur.fetchone()
            
            if not article:
                stats['group_article_media']['errors'].append(f"{m['id']}: article_id {article_legacy_id} no encontrado en group_articles migrados")
                print(f"  ERROR: article {article_legacy_id} no migrado")
                continue
            
            article_id = article['id']
            
            # Convertir BIGINT id a UUID string para PK
            # Usar legacy_id como trazabilidad, generar UUID para PK
            media_id = str(uuid.uuid4()).replace('-', '')
            legacy_id = str(m['id'])
            
            tcur.execute("""
                INSERT INTO group_article_media (
                    id, legacy_id, article_id, kind, url, provider,
                    video_id, caption, credit, position, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                media_id,
                legacy_id,
                article_id,
                m['kind'],
                m['url'],
                m.get('provider'),
                m.get('video_id'),
                m.get('caption'),
                m.get('credit'),
                m.get('position') or 0,
                dt_to_str(m.get('created_at')),
            ))
            stats['group_article_media']['inserted'] += 1
        except Exception as e:
            stats['group_article_media']['errors'].append(f"{m['id']}: {e}")
            print(f"  ERROR {m['id']}: {e}")
    TGT.commit()

print(f"group_article_media: {stats['group_article_media']['inserted']} insertados, {stats['group_article_media']['skipped']} saltados, {len(stats['group_article_media']['errors'])} errores")

# ============================================================
# RESUMEN
# ============================================================
print("\n" + "="*60)
print("RESUMEN BLOQUE 3")
print("="*60)
for table, s in stats.items():
    print(f"{table:25s} | insertados={s['inserted']:4d} | saltados={s['skipped']:4d} | errores={len(s['errors']):3d}")
    for e in s['errors'][:5]:
        print(f"  - {e}")
    if len(s['errors']) > 5:
        print(f"  ... y {len(s['errors']) - 5} errores más")

SRC.close()
TGT.close()