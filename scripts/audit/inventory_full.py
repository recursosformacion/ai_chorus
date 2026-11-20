import pymysql

def get_table_counts(db_config, table_pattern=None):
    conn = pymysql.connect(**db_config, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
    counts = {}
    try:
        with conn.cursor() as cur:
            if table_pattern:
                cur.execute(f"SHOW TABLES LIKE '{table_pattern}'")
                tables = [row[f'Tables_in_{db_config["database"]} ({table_pattern})'] for row in cur.fetchall()]
            else:
                cur.execute("SHOW TABLES")
                tables = [row[f'Tables_in_{db_config["database"]}'] for row in cur.fetchall()]
            
            for t in tables:
                cur.execute(f"SELECT COUNT(*) as c FROM {t}")
                counts[t] = cur.fetchone()['c']
    finally:
        conn.close()
    return counts

SRC_CONFIG = {'host': '127.0.0.1', 'port': 3306, 'user': 'osap2027', 'password': '2027osapdb', 'database': 'osap_api'}
TGT_CONFIG = {'host': '127.0.0.1', 'port': 3306, 'user': 'osap2027_test', 'password': 'testpass', 'database': 'osap_chorus_test'}

print("=" * 80)
print("INVENTARIO COMPLETO OSAP -> CHORUS")
print("=" * 80)

src_counts = get_table_counts(SRC_CONFIG, 'amigos_%')
print(f"\nTablas amigos_* en OSAP: {len(src_counts)}")
total_src = 0
for t, c in sorted(src_counts.items()):
    print(f"  {t}: {c}")
    total_src += c
print(f"  TOTAL: {total_src}")

tgt_counts = get_table_counts(TGT_CONFIG)
print(f"\nTablas en Chorus (osap_chorus_test): {len(tgt_counts)}")
total_tgt = 0
for t, c in sorted(tgt_counts.items()):
    print(f"  {t}: {c}")
    total_tgt += c
print(f"  TOTAL: {total_tgt}")