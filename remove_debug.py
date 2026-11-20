with open('app/main.py', 'r') as f:
    content = f.read()

# Remove the debug print
content = content.replace('        print("DEBUG: returning app")\n', '')

with open('app/main.py', 'w') as f:
    f.write(content)
print('Removed debug print')