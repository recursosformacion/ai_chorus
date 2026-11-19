import pymysql

conn = pymysql.connect(
    host='127.0.0.1',
    port=3306,
    user='osap2027',
    password='2027osapdb',
    database='osap_api',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

print("=== INVENTARIO TABLAS AMIGOS ===")
with conn.cursor() as cur:
    cur.execute("SHOW TABLES LIKE 'amigos_%'")
    for row in cur.fetchall():
        for k, v in row.items():
            print(v)

print("\n=== ESTRUCTURA Y CONTEOS ===")
tablas = [
    'amigos_groups', 'amigos_members', 'amigos_group_catalog', 'amigos_articles',
    'amigos_media', 'amigos_coral_attributes', 'amigos_coral_details',
    'amigos_group_history', 'amigos_group_links', 'amigos_group_types',
    'amigos_role_templates', 'amigos_section_templates',
    'amigos_actuacion_groups', 'amigos_actuaciones', 'amigos_authorizations',
    'amigos_uploads', 'amigos_events'
]

for t in tablas:
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW CREATE TABLE " + t)
            create = cur.fetchone()
            for k, v in create.items():
                if 'Create Table' in k:
                    print("\n--- " + t + " ---")
                    print(v[:500] + "..." if len(v) > 500 else v)
            cur.execute("SELECT COUNT(*) as c FROM " + t)
            cnt = cur.fetchone()
            print("  Registros: " + str(cnt['c']))
    except Exception as e:
        print("  Error en " + t + ": " + str(e))

conn.close()