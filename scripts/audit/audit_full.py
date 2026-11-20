import pymysql

src = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
tgt = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)

tables = [
    'amigos_groups',
    'amigos_members',
    'amigos_group_history',
    'amigos_group_catalog',
    'amigos_group_links',
    'amigos_group_types',
    'amigos_section_templates',
    'amigos_role_templates',
    'amigos_articles',
    'amigos_media',
    'amigos_coral_details',
    'amigos_coral_attributes',
    'amigos_authorizations',
    'amigos_uploads',
    'amigos_actuaciones',
    'amigos_actuacion_groups',
    'amigos_events',
]

print("=== AUDITORIA COMPLETA OSAP -> CHORUS ===\n")

for table in tables:
    print(f"\n{'='*80}")
    print(f"TABLA: {table}")
    print(f"{'='*80}")
    
    # Count
    with src.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) as c FROM {table}")
        cnt = cur.fetchone()['c']
        print(f"Registros origen: {cnt}")
    
    # Schema
    with src.cursor() as cur:
        cur.execute(f"SHOW CREATE TABLE {table}")
        for row in cur.fetchall():
            for k, v in row.items():
                if 'Create' in k:
                    print(f"DDL origen:\n{v}")
    
    # Sample data
    with src.cursor() as cur:
        cur.execute(f"SELECT * FROM {table} LIMIT 3")
        rows = cur.fetchall()
        if rows:
            print(f"Muestras (hasta 3):")
            for r in rows:
                print(f"  {r}")
    
    # Check target table exists
    with tgt.cursor() as cur:
        cur.execute(f"SHOW TABLES LIKE %s", (table.replace('amigos_', ''),))
        exists = cur.fetchone()
        print(f"Tabla destino existe: {'Sí' if exists else 'No'}")

src.close()
tgt.close()