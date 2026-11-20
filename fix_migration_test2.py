with open('tests/test_api_runtime.py', 'r') as f:
    content = f.read()

# Find and replace the exact line
old = '''        # 001_schema.sql + 004-007 + 016 + 017 + 033 + 034 = 9 migraciones
        assert applied == 9'''

new = '''        # 001_schema.sql + 004-007 + 016 + 017 + 018-035 = 25 migraciones
        assert applied == 25'''

if old in content:
    content = content.replace(old, new)
    with open('tests/test_api_runtime.py', 'w') as f:
        f.write(content)
    print('Replaced successfully')
else:
    print('Pattern not found, trying alternative...')
    # Try with different whitespace
    import re
    content = re.sub(r'# 001_schema\.sql \+ 004-007 \+ 016 \+ 017 \+ 033 \+ 034 = 9 migraciones', 
                     '# 001_schema.sql + 004-007 + 016 + 017 + 018-035 = 25 migraciones', content)
    content = re.sub(r'assert applied == 9', 'assert applied == 25', content)
    with open('tests/test_api_runtime.py', 'w') as f:
        f.write(content)
    print('Replaced with regex')