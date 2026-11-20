import json
with open('audit_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
total = 0
for table, info in data.items():
    count = info.get('count', 0)
    total += count
    print(f'{table}: {count}')
print(f'TOTAL: {total}')