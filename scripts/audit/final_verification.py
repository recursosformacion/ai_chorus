import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    print("=" * 80)
    print("1. LEGACY_UPLOADS - 13 registros")
    print("=" * 80)
    cur.execute("""
        SELECT lu.id, lu.legacy_file_id, lu.group_id, lu.mime_type, lu.size_bytes, lu.created_by,
               g.id as group_exists
        FROM legacy_uploads lu
        LEFT JOIN groups g ON lu.group_id = g.id
        ORDER BY lu.legacy_file_id
    """)
    for row in cur.fetchall():
        print(f"  file_id={row['legacy_file_id']} group_id={row['group_id']} group_exists={row['group_exists']} {row['mime_type']} {row['size_bytes']} bytes by={row['created_by']}")

    print("\n--- FK legacy_uploads.group_id -> groups.id ---")
    cur.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN g.id IS NOT NULL THEN 1 ELSE 0 END) as valid,
               SUM(CASE WHEN lu.group_id IS NOT NULL AND g.id IS NULL THEN 1 ELSE 0 END) as invalid
        FROM legacy_uploads lu
        LEFT JOIN groups g ON lu.group_id = g.id
    """)
    r = cur.fetchone()
    print(f"  total={r['total']} validos={r['valid']} invalidos={r['invalid']} (11 con group_id en origen pero BD limpia)")

    print("\n" + "=" * 80)
    print("2. GROUP_MEMBERS - 3 miembros")
    print("=" * 80)
    cur.execute("""
        SELECT gm.id, gm.group_id, gm.user_sub, gm.role, gm.status,
               gm.group_admin_role_id, gr_admin.code as admin_code, gr_admin.name as admin_name,
               gm.group_musical_role_id, gr_mus.code as musical_code, gr_mus.name as musical_name,
               gm.section_id, gs.code as section_code
        FROM group_members gm
        LEFT JOIN group_roles gr_admin ON gm.group_admin_role_id = gr_admin.id
        LEFT JOIN group_roles gr_mus ON gm.group_musical_role_id = gr_mus.id
        LEFT JOIN group_sections gs ON gm.section_id = gs.id
    """)
    for row in cur.fetchall():
        print(f"  {row['group_id']}/{row['user_sub']}: role={row['role']} status={row['status']}")
        print(f"    admin_role: {row['admin_code']} ({row['admin_name']})" if row['group_admin_role_id'] else "    admin_role: NULL (sin admin_role_id en origen)")
        print(f"    musical_role: {row['musical_code']} ({row['musical_name']})" if row['group_musical_role_id'] else "    musical_role: NULL (sin musical_role_id en origen)")
        print(f"    section: {row['section_code']}" if row['section_id'] else "    section: NULL")

    print("\n--- Explicación NULLs ---")
    print("  Member 1 (df72ae26985011a4): admin_role_id=NULL, musical_role_id=NULL en origen -> NULL en destino")
    print("  Member 2 (719c3051fab035e1): admin_role_id=NULL, musical_role_id=NULL en origen -> NULL en destino")
    print("  Member 3 (1809b94b243a5f46): RESUELTO -> admin=Secretaría, musical=Coralista, section=Bajo")

    print("\n" + "=" * 80)
    print("3. NUEVAS ESTRUCTURAS - Servicios/API")
    print("=" * 80)
    cur.execute("SHOW TABLES")
    tables = [row['Tables_in_osap_chorus_test'] for row in cur.fetchall()]
    for t in ['group_roles', 'group_social_links', 'legacy_uploads', 'activity_log']:
        exists = t in tables
        cur.execute(f"SELECT COUNT(*) as c FROM {t}")
        count = cur.fetchone()['c']
        print(f"  {t}: {'EXISTE' if exists else 'FALTA'} - {count} registros")

    print("\n--- Verificar endpoints en app/api ---")
    import os
    api_dir = 'D:\\Proyectos\\AI_OSAP\\Chorus\\app\\api'
    if os.path.exists(api_dir):
        for f in os.listdir(api_dir):
            if f.endswith('.py'):
                print(f"  app/api/{f}")

    print("\n" + "=" * 80)
    print("4. TESTS - Cobertura migraciones 029-033")
    print("=" * 80)
    import subprocess
    result = subprocess.run(['python', '-m', 'pytest', 'tests/', '-v', '--collect-only', '-q'], 
                          capture_output=True, text=True, cwd='D:\\Proyectos\\AI_OSAP\\Chorus', timeout=60)
    print("Tests encontrados:")
    for line in result.stdout.split('\n'):
        if 'test_' in line and any(kw in line.lower() for kw in ['group_role', 'social_link', 'legacy_upload', 'activity_log', 'authorization', 'performance']):
            print(f"  {line.strip()}")

    print("\n" + "=" * 80)
    print("5. REGISTROS CORALES EN JSON - groups")
    print("=" * 80)
    cur.execute("SELECT id, name, language, repertoire, venues FROM groups")
    for row in cur.fetchall():
        print(f"  {row['id']} ({row['name']}):")
        print(f"    language: {row['language']}")
        print(f"    repertoire: {row['repertoire']}")
        print(f"    venues: {row['venues']}")

    # Check coral_details migrated
    print("\n--- Verificar migración coral_details (Phase 2) ---")
    cur.execute("SELECT id, formation_type, member_count, venue FROM groups")
    for row in cur.fetchall():
        print(f"  {row['id']}: formation_type={row['formation_type']} member_count={row['member_count']} venue={row['venue']}")

conn.close()