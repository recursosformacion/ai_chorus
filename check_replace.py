with open('insert_prep_works.py', 'r') as f:
    content = f.read()

# Find all occurrences of replace
import re
for m in re.finditer(r'replace', content):
    idx = m.start()
    print(f'At {idx}: {repr(content[idx:idx+50])}')