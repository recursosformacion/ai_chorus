import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    # Verify all FK relationships
    checks = [
        ("group_roles -> groups", "group_roles", "group_id", "groups", "id"),
        ("group_social_links -> groups", "group_social_links", "group_id", "groups", "id"),
        ("legacy_uploads -> groups", "legacy_uploads", "group_id", "groups", "id"),
        ("activity_log -> groups", "activity_log", "group_id", "groups", "id"),
        ("activity_log -> group_articles", "activity_log", "article_id", "group_articles", "id"),
        ("performances -> (no FK)", "performances", "id", None, None),
        ("group_members -> group_roles (admin)", "group_members", "group_admin_role_id", "group_roles", "id"),
        ("group_members -> group_roles (musical)", "group_members", "group_musical_role_id", "group_roles", "id"),
        ("group_members -> group_sections", "group_members", "section_id", "group_sections", "id"),
        ("group_members -> groups", "group_members", "group_id", "groups", "id"),
        ("group_articles -> groups", "group_articles", "group_id", "groups", "id"),
        ("group_article_media -> group_articles", "group_article_media", "article_id", "group_articles", "id"),
        ("group_history -> groups", "group_history", "group_id", "groups", "id"),
        ("group_sections -> groups", "group_sections", "group_id", "groups", "id"),
    ]
    
    print("=== Integridad Referencial ===")
    for name, table, col, ref_table, ref_col in checks:
        if ref_table is None:
            cur.execute(f"SELECT COUNT(*) as c FROM {table}")
            total = cur.fetchone()['c']
            print(f"{name}: {total} registros (sin FK)")
            continue
        
        cur.execute(f'''
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN r.{ref_col} IS NOT NULL THEN 1 ELSE 0 END) as valid,
                   SUM(CASE WHEN t.{col} IS NOT NULL AND r.{ref_col} IS NULL THEN 1 ELSE 0 END) as invalid
            FROM {table} t
            LEFT JOIN {ref_table} r ON t.{col} = r.{ref_col}
        ''')
        row = cur.fetchone()
        print(f"{name}: total={row['total']} validos={row['valid']} invalidos={row['invalid']}")
    
    # Check duplicates
    print("\n=== Unicidad ===")
    for table, col in [
        ('group_roles', 'legacy_id'),
        ('group_social_links', 'legacy_id'),
        ('legacy_uploads', 'legacy_file_id'),
        ('activity_log', 'legacy_id'),
        ('performances', 'id'),
        ('group_articles', 'legacy_id'),
        ('group_article_media', 'legacy_id'),
        ('authorizations', 'user_id, scope'),
    ]:
        if ',' in col:
            cur.execute(f"SELECT COUNT(*) as c FROM (SELECT {col} FROM {table} GROUP BY {col} HAVING COUNT(*) > 1) t")
        else:
            cur.execute(f"SELECT COUNT(*) as c FROM (SELECT {col} FROM {table} GROUP BY {col} HAVING COUNT(*) > 1) t")
        print(f"{table}.{col} duplicados: {cur.fetchone()['c']}")

conn.close()