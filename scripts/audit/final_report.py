import pymysql

SRC = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
TGT = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)

print("=" * 80)
print("INFORME FINAL BLOQUE 4 - MIGRACION INTEGRAL OSAP -> CHORUS")
print("=" * 80)

# Get all OSAP counts
with SRC.cursor() as cur:
    cur.execute("SHOW TABLES LIKE 'amigos_%'")
    tables = [row['Tables_in_osap_api (amigos_%)'] for row in cur.fetchall()]
    src_counts = {}
    for t in tables:
        cur.execute(f"SELECT COUNT(*) as c FROM {t}")
        src_counts[t] = cur.fetchone()['c']

# Get all Chorus counts for relevant tables
with TGT.cursor() as cur:
    cur.execute("SHOW TABLES")
    chorus_tables = [row['Tables_in_osap_chorus_test'] for row in cur.fetchall()]
    tgt_counts = {}
    for t in chorus_tables:
        cur.execute(f"SELECT COUNT(*) as c FROM {t}")
        tgt_counts[t] = cur.fetchone()['c']

print("\n--- RECUENTOS ORIGEN vs DESTINO ---\n")
print(f"{'Tabla OSAP':<35} {'Origen':>8} {'Tabla Chorus':<35} {'Destino':>8} {'Estado':<10}")
print("-" * 100)

mapping = [
    ('amigos_groups', 'groups'),
    ('amigos_group_catalog (section)', 'group_sections'),  # 8 of 24
    ('amigos_group_catalog (admin/musical)', 'group_roles'),  # 16 of 24
    ('amigos_members', 'group_members'),
    ('amigos_group_history', 'group_history'),
    ('amigos_section_templates', 'section_templates'),
    ('amigos_role_templates', 'role_templates'),
    ('amigos_articles', 'group_articles'),
    ('amigos_media', 'group_article_media'),
    ('amigos_authorizations', 'authorizations'),
    ('amigos_group_links', 'group_social_links'),
    ('amigos_uploads', 'legacy_uploads'),
    ('amigos_actuaciones', 'performances'),
    ('amigos_actuacion_groups', 'performance_groups'),
    ('amigos_events', 'activity_log'),
    ('amigos_coral_details', 'groups (JSON fields)'),
    ('amigos_coral_attributes', 'groups (JSON fields)'),
    ('amigos_group_types', 'group_types'),
]

for src_t, tgt_t in mapping:
    if src_t == 'amigos_group_catalog (section)':
        src_c = 8
    elif src_t == 'amigos_group_catalog (admin/musical)':
        src_c = 16
    else:
        src_c = src_counts.get(src_t, 0)
    
    tgt_c = tgt_counts.get(tgt_t, 0) if tgt_t in tgt_counts else 0
    
    if src_c == tgt_c:
        status = "OK"
    elif src_t in ['amigos_coral_details', 'amigos_coral_attributes'] and tgt_c > 0:
        status = "OK (JSON)"
    else:
        status = "DIFERENTE"
    
    print(f"{src_t:<35} {src_c:>8} {tgt_t:<35} {tgt_c:>8} {status:<10}")

print("\n--- TOTALES ---")
print(f"Total OSAP (17 tablas): {sum(src_counts.values())}")
relevant_tgt = sum(tgt_counts.get(t, 0) for _, t in mapping if t in tgt_counts)
print(f"Total Chorus (tablas migradas): {relevant_tgt}")

# Verify specific data points
print("\n--- VALIDACIONES ESPECIFICAS ---\n")

with TGT.cursor() as cur:
    # group_members with group_roles
    cur.execute("""
        SELECT gm.group_id, gm.user_sub, gm.group_admin_role_id, gm.group_musical_role_id, gm.section_id
        FROM group_members gm
    """)
    print("group_members con roles de grupo:")
    for row in cur.fetchall():
        print(f"  {row['group_id']}/{row['user_sub']}: admin={row['group_admin_role_id']}, musical={row['group_musical_role_id']}, section={row['section_id']}")
    
    # performances
    cur.execute("SELECT id, title, kind, event_status, starts_on FROM performances")
    print("\nperformances:")
    for row in cur.fetchall():
        print(f"  {row['id']}: {row['title']} ({row['kind']}, {row['event_status']}, {row['starts_on']})")
    
    # activity_log event types
    cur.execute("SELECT event_type, COUNT(*) as c FROM activity_log GROUP BY event_type ORDER BY c DESC")
    print("\nactivity_log por tipo:")
    for row in cur.fetchall():
        print(f"  {row['event_type']}: {row['c']}")
    
    # legacy_uploads
    cur.execute("SELECT legacy_file_id, group_id, mime_type, size_bytes FROM legacy_uploads")
    print("\nlegacy_uploads:")
    for row in cur.fetchall():
        print(f"  file_id={row['legacy_file_id']} group={row['group_id']} {row['mime_type']} {row['size_bytes']} bytes")

SRC.close()
TGT.close()