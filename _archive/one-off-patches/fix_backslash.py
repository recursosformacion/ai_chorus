with open('insert_prep_works.py', 'r') as f:
    content = f.read()

# Fix the remaining quadruple backslash
content = content.replace('replace("\\\\\\\\", "/")', 'replace("\\\\", "/")')

with open('insert_prep_works.py', 'w') as f:
    f.write(content)
print('Fixed')