import pymysql
import json

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

audit = {}

for table in tables:
    print(f"Auditing {table}...")
    audit[table] = {}
    
    with src.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) as c FROM {table}")
        audit[table]['count'] = cur.fetchone()['c']
        
        cur.execute(f"SHOW CREATE TABLE {table}")
        for row in cur.fetchall():
            for k, v in row.items():
                if 'Create' in k:
                    audit[table]['ddl'] = v
        
        cur.execute(f"SELECT * FROM {table} LIMIT 3")
        rows = cur.fetchall()
        # Convert datetime to string for JSON serialization
        samples = []
        for r in rows:
            sample = {}
            for k, v in r.items():
                if hasattr(v, 'isoformat'):
                    sample[k] = v.isoformat()
                elif hasattr(v, 'total_seconds'):  # timedelta
                    sample[k] = str(v)
                elif isinstance(v, bytes):
                    sample[k] = v.decode('utf-8', errors='replace')
                else:
                    sample[k] = v
            samples.append(sample)
        audit[table]['samples'] = samples
    
    with tgt.cursor() as cur:
        cur.execute("SHOW TABLES LIKE %s", (table.replace('amigos_', ''),))
        audit[table]['target_exists'] = cur.fetchone() is not None

src.close()
tgt.close()

# Save to JSON
with open('audit_results.json', 'w', encoding='utf-8') as f:
    json.dump(audit, f, ensure_ascii=False, indent=2)

print("Audit complete. Results saved to audit_results.json")