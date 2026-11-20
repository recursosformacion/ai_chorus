with open('insert_prep_works.py', 'r') as f:
    content = f.read()

# Fix all replace patterns - need 8 backslashes in script to get 4 in output
content = content.replace('replace("\\\\", "/")', 'replace("\\\\\\\\", "/")')

with open('insert_prep_works.py', 'w') as f:
    f.write(content)
print('Fixed backslashes in insert script')