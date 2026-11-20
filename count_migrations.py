with open('scripts/rebuild_test_db.py', 'r') as f:
    content = f.read()

# Count migrations in MIGRATIONS list
import re
migrations = re.findall(r'"(0\d+_.*?)"', content)
print(f'Total migrations in rebuild script: {len(migrations)}')
for m in migrations:
    print(f'  {m}')