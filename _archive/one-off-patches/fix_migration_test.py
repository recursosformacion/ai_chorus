with open('tests/test_api_runtime.py', 'r') as f:
    content = f.read()

# Update the expected migration count
old = '''            # 001_schema.sql + 004-007 + 016 + 017 + 033 + 034 = 9 migraciones
            assert applied == 9'''

new = '''            # 001_schema.sql + 004-007 + 016 + 017 + 018-035 = 25 migraciones
            assert applied == 25'''

content = content.replace(old, new)

with open('tests/test_api_runtime.py', 'w') as f:
    f.write(content)

print('Updated test expectation')