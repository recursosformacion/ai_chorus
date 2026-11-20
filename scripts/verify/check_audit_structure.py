import json
with open('audit_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(type(data))
if isinstance(data, dict):
    print(data.keys())
    for k, v in data.items():
        print(f'{k}: {type(v)}')
        if isinstance(v, dict):
            print(f'  keys: {v.keys()}')