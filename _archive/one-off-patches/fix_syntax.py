with open('app/main.py', 'r') as f:
    lines = f.readlines()

# Fix line 2823 (index 2822)
lines[2822] = '            relative = str(upload.filename or "archivo").replace("\\\\", "/")\n'

with open('app/main.py', 'w') as f:
    f.writelines(lines)
print('Fixed')